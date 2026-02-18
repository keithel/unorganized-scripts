#!/usr/bin/env bash

set -e # Terminate with failure if any command returns nonzero
set -u # Terminate with failure any time an undefined variable is expanded

SCRIPT_DIR="$(cd -P "$(dirname "$BASH_SOURCE")" >/dev/null 2>&1 && pwd)"

echo -n "Start timestamp: "; date

isMacOS=0
isLinux=0
isWin=0
case $OSTYPE in
  darwin*)
    isMacOS=1
    ;;
  linux*)
    isLinux=1
    ;;
  msys*|cygwin*)
    isWin=1
    echo >&2 "error: Windows builds using this script is not supported yet"
    # Need a way to source vcvarsall.
    exit 1
    ;;
  *)
    echo >&2 "error: running on unknown OS"
    exit 1
esac

# Parameter 1 - Absolute path to workspace directory
if [ $# -eq 0 ]; then
    echo "Need to pass workspace directory to the script"
    exit 1
fi

set +u
# Environment Variable - QTVERSION - Version of Qt to build
if [[ -z "${QTVERSION}" ]]; then
    echo "QTVERSION is undefined. Example: export QTVERSION=6.2.3"
    exit 1
else
    echo "QTVERSION=${QTVERSION}"
fi
set -u

# Process command line arguments.
# Location of the workspace directory (root of the folder structure)
export WORKSPACE_DIR=$1
shift

DO_CONFIGURE=1
DO_BUILD=1
DO_INSTALL=1
ARGS=()
while [[ $# -gt 0 ]]; do
  case $1 in
    -b|--build)
      DO_CONFIGURE=
      DO_INSTALL=
      shift
      ;;
    -i|--install)
      DO_CONFIGURE=
      DO_BUILD=
      shift
      ;;
    -z)
      DO_CONFIGURE=
      DO_BUILD=
      DO_INSTALL=
      ARGS+=("$1") # save arg
      shift
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
    *)
      ARGS+=("$1") # save arg
      shift
      ;;
  esac
done
set -- "${ARGS[@]: }" # restore args

# Location where the final build will be located, as defined by the -prefix option
export INSTALL_DIR=$WORKSPACE_DIR/install/qt_$QTVERSION
export BUILD_DIR=$WORKSPACE_DIR/build

# Location of the source code directory (top of git tree - qt5.git)
export SOURCE_DIR=$(readlink -f "$SCRIPT_DIR/..")

if [[ ! "${QTVERSION}" =~ [0-9]\.[0-9]+\.[0-9]* ]]; then
    set +e
    python --version >/dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        echo >&2 "QTVERSION is not a version number. Example: export QTVERSION=6.2.3"
        exit 1
    fi
    set -e
    echo "QTVERSION is not a version number, figuring it out from the codebase..."
    QTVERSION=$(python $SCRIPT_DIR/fetch-qt-version.py ${SOURCE_DIR})
    echo "QTVERSION=$QTVERSION"
fi

# MacOS uses system python3
export PYTHON_DIR=""
if [[ $isMacOS -ne 1 ]]; then
    set +u
    if [[ ! -x "$PYTHONEXE" ]]; then
        if [[ -z "$PYTHONEXE" ]]; then
            echo >&2 "PYTHONEXE is undefined."
        elif [[ ! -e "$PYTHONEXE" ]]; then
            echo >&2 "PYTHONEXE ${PYTHONEXE} doesn't exist."
        elif [[ ! -x "$PYTHONEXE" ]]; then
            echo >&2 "PYTHONEXE ${PYTHONEXE} isn't executable."
        fi
        echo >&2 "Example: export PYTHONEXE=${WORKSPACE_DIR}/external_dependencies/cpython/3.10.6/RelWithDebInfo/bin/python3.10"
        exit 1
    else
        # make python symlinks: python, python3
        export PYTHON_DIR=$(dirname $PYTHONEXE)
        for py_link in "python3" "python"; do
            if [[ ! -e "$PYTHON_DIR/$py_link" ]]; then
                ln -s $(basename "$PYTHONEXE") "$PYTHON_DIR/$py_link"
                echo "Symlink $PYTHON_DIR/$py_link made"
            fi
        done
        echo "PYTHONEXE=${PYTHONEXE}"
    fi
    set -u
fi

export OPENSSL_BIN_DIR=""
if [[ $isMacOS -eq 1 ]]; then
    export CMAKE_DIR=$WORKSPACE_DIR/external_dependencies/cmake-3.24.2-macos10.10-universal/CMake.app/Contents
    export NINJA_DIR=$WORKSPACE_DIR/external_dependencies/ninja
    export NODE_DIR=$WORKSPACE_DIR/external_dependencies/node-v16.14.0-darwin-x64
elif [[ $isLinux -eq 1 ]]; then
    # Location of openssl include directory (optional) within the external dependencies directory
    # Update with artifact build of recent OpenSSL 1.1.1 release when available.
    # ... and add -DOPENSSL_ROOT_DIR=$OPENSSL_ROOT_DIR to configure line below. (?)
    # Maya includes a newer version of OpenSSL - which Qt will take into use.
    export OPENSSL_ROOT_DIR="$WORKSPACE_DIR/external_dependencies/openssl/1.1.1g/RelWithDebInfo"
    export OPENSSL_BIN_DIR="$OPENSSL_ROOT_DIR/bin"
    export CMAKE_DIR=$WORKSPACE_DIR/external_dependencies/cmake-3.22.1-linux-x86_64
    export NINJA_DIR=$WORKSPACE_DIR/external_dependencies/ninja
    export NODE_DIR=$WORKSPACE_DIR/external_dependencies/node-v16.14.0-linux-x64
fi
export PATH=$OPENSSL_BIN_DIR:$CMAKE_DIR/bin:$NINJA_DIR:$NODE_DIR/bin:$PYTHON_DIR:$PATH

echo "PATH=$PATH"

# Print compiler info, Python, patchelf (linux), cmake, ninja, nodejs, and openssl (when used) versions
set +e
patchelf_ret=0
openssl_ret=0
if [[ $isMacOS -eq 1 ]]; then
    xcodebuild -version
    compiler_ret=$?
elif [[ $isLinux -eq 1 ]]; then
    gcc --version | head -1
    gcc --version >/dev/null 2>&1
    compiler_ret=$?

    patchelf --version
    patchelf_ret=$?
fi
if [[ $isLinux -eq 1 || $isWin -eq 1 ]]; then
    openssl version
    openssl_ret=$?
fi
python --version
python_ret=$?
cmake --version | head -1
echo -n "ninja "
ninja --version
ninja_ret=$?
echo -n "node "
node --version
node_ret=$?
set -e

if [ $compiler_ret -ne 0 ]; then
    echo "Compiler (xcode, gcc, msvc) not present. Aborting."
    exit 1
fi

# Only applies to Windows and Linux
if [ $openssl_ret -ne 0 ]; then
    echo "OpenSSL not present. Aborting."
    exit 1
fi

if [ $python_ret -ne 0 ]; then
    echo "python not present. Aborting."
    exit 1
fi

# Only applies to Linux
if [ $patchelf_ret -ne 0 ]; then
    echo "patchelf not present. Aborting."
    exit 1
fi

set +e
cmake --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "cmake not present. Aborting."
    exit 1
fi
set -e

if [ $ninja_ret -ne 0 ]; then
    echo "ninja not present. Aborting."
    exit 1
fi

if [ $node_ret -ne 0 ]; then
    echo "nodejs not present. Aborting."
    exit 1
fi

set +e
html5lib_installed=$(python3 -m pip list installed | grep html5lib | wc -l)
if [ $html5lib_installed -eq 0 ]; then
    echo "python3 html5lib not installed. Installing it."
    python3 -m pip install --no-input html5lib
    if [[ $? -ne 0 ]]; then
        echo "Install of python html5lib failed. aborting."
        exit 1
    fi
fi
set -e

# Only used for building docs. We don't need docs.
#if [ -z "$LLVM_INSTALL_DIR" ]; then
#    echo "libclang not installed. Aborting"
#    exit 1
#fi

function exitIfFailed
{

  # $1 return code of command
  # $2 Last operation string

  if [ $1 -ne 0 ]; then
    echo "***** Failed to ${2} *****"
    exit 1
  fi
  return 0
}

if [[ -n "$DO_CONFIGURE" && -e "$BUILD_DIR" ]]; then
    echo >&2 "Build dir $BUILD_DIR already exists. This is unexpected."
    echo >&2 "Removing $BUILD_DIR."
    rm -Rf "$BUILD_DIR"
    if [[ $? -ne 0 ]]; then
        echo >&2 "Failed to remove $BUILD_DIR. aborting."
        exit 1
    fi
fi

set -e
mkdir "$BUILD_DIR"
BUILD_DIR=$(cd "${BUILD_DIR}" && pwd -P)
cd "$BUILD_DIR"
echo -n "BUILD_DIR PWD == "
pwd
set +e

CONFIGURE_RETURNCODE=0
if [ -n "$DO_CONFIGURE" ]; then
    # Configure the build
    # Configure options: https://wiki.qt.io/Qt_6.2_Tools_and_Versions
    # coin/platform_configs/cmake_platforms.yaml

    # Define the modules to skip (because they are under commercial license)
    export MODULES_TO_SKIP="-skip qtnetworkauth -skip qtpurchasing -skip qtquickcontrols -skip qtquick3d -skip qtlottie -skip qtcharts -skip qtdatavis3d -skip qtvirtualkeyboard -skip qtscript -skip qtwayland -skip qtwebglplugin"

    PLAT_ARGS=""
    PLAT_CMAKE_DEFS=""
    if [[ $isMacOS -eq 1 ]]; then
        #PLAT_ARGS="-debug-and-release -plugin-sql-sqlite -no-strip -no-framework"
        #PLAT_CMAKE_DEFS='-DCMAKE_OSX_ARCHITECTURES="x86_64;arm64" -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0'
        $SOURCE_DIR/configure -opensource -confirm-license -prefix $INSTALL_DIR -nomake tests -nomake examples -force-debug-info -separate-debug-info -opengl desktop -feature-qtwebengine-build -debug-and-release -plugin-sql-sqlite -no-strip -no-framework $MODULES_TO_SKIP -- -DCMAKE_OSX_ARCHITECTURES="x86_64;arm64" -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0
        CONFIGURE_RETURNCODE=$?
    elif [[ $isLinux -eq 1 ]]; then
        # https://cmake.org/cmake/help/latest/module/FindOpenGL.html
        PLAT_ARGS="-release -qt-libjpeg -qt-libpng -qt-pcre -qt-harfbuzz -qt-doubleconversion -no-libudev -bundled-xcb-xinput -sysconfdir /etc/xdg -R . -icu -qt-qt3d-assimp -openssl-runtime"
        PLAT_CMAKE_DEFS="-DOpenGL_GL_PREFERENCE=LEGACY"
    elif [[ $isWin -eq 1 ]]; then
        PLAT_ARGS="-debug-and-release -optimized-tools -openssl-runtime -qt-zlib"
        PLAT_CMAKE_DEFS="-DOPENSSL_ROOT_DIR=$OPENSSL_ROOT_DIR"
    fi

    if [[ $isMacOS -ne 1 ]]; then
        $SOURCE_DIR/configure -opensource -confirm-license -prefix $INSTALL_DIR -nomake tests -nomake examples -force-debug-info -separate-debug-info -opengl desktop -feature-qtwebengine-build $PLAT_ARGS $MODULES_TO_SKIP -- $PLAT_CMAKE_DEFS
        CONFIGURE_RETURNCODE=$?
    fi
    echo -n "End Configure timestamp: "; date
fi

BUILD_RETURNCODE=0
if [ -n "$DO_BUILD" -a $CONFIGURE_RETURNCODE -eq 0 ]; then
    # pass `-- -v` to make ninja verbose
    cmake --build . --parallel
    BUILD_RETURNCODE=$?
    echo -n "End Build timestamp: "; date
fi

INSTALL_RETURNCODE=0
COMPRESS_RETURNCODE=0
if [ -n "$DO_INSTALL" -a $BUILD_RETURNCODE -eq 0 ]; then
    cmake --install .
    INSTALL_RETURNCODE=$?
    echo -n "End cmake install timestamp: "; date
    if [ $INSTALL_RETURNCODE -eq 0 ]; then
        set -e
        cd $INSTALL_DIR
        if [[ $isMacOS -eq 1 ]]; then
            # Generate and compress debug symbols in install directory

            for x in $(ls ./**/*.dylib); do
                if ! [ -L $x ]; then
                    echo Generating debug symbols for $x
                    dsymutil $x;
                    tar -czf $x.dSYM.tgz --directory $(dirname $x) $(basename $x).dSYM ;
                    rm -rf $x.dSYM;
                fi
            done

            for x in $(ls ./**/**/*.dylib); do
                if ! [ -L $x ]; then
                    echo Generating debug symbols for $x
                    dsymutil $x;
                    tar -czf $x.dSYM.tgz --directory $(dirname $x) $(basename $x).dSYM ;
                    rm -rf $x.dSYM;
                fi
            done

            # Remove the webkit webengine debug symbols because they are incredibly heavy,
            # more than half of the artifact.
            rm -vf lib/libQt5Web*.dSYM.tgz
        elif [[ $isLinux -eq 1 ]]; then
            # Adjust RUNPATHS of libraries in install directory

            # Copy system ICU libs into the package.
            for iculib in icui18n icuuc icudata ; do
                cp --preserve=mode -P /lib64/lib${iculib}.so.* lib/
            done

            set +e
            find . -name libQt?Core.so.$QTVERSION | xargs patchelf --set-rpath "\$ORIGIN"
            if [ $? -ne 0 ]; then
                echo "**** Failed to set qtbase/core rpath ****"
                exit 1
            fi

            find . -name libQt?WebEngineCore.so.$QTVERSION | xargs patchelf --set-rpath "\$ORIGIN"
            if [ $? -ne 0 ]; then
                echo "**** Failed to set qtwebengine/core rpath ****"
                exit 1
            fi
            set -e
        fi

        # Compress folders for Maya devkit
        tar -czf qt_$QTVERSION-include.tar.gz --directory=include/ . && \
        tar -czf qt_$QTVERSION-cmake.tar.gz --directory=lib/cmake/ . && \
        tar -czf qt_$QTVERSION-mkspecs.tar.gz --directory=mkspecs/ .
        COMPRESS_RETURNCODE=$?
        if [ $COMPRESS_RETURNCODE -eq 0 ]; then
            echo "==== Tar files created ===="
        fi
    fi
fi

exitIfFailed $CONFIGURE_RETURNCODE "configure build"
exitIfFailed $BUILD_RETURNCODE  "build"
exitIfFailed $INSTALL_RETURNCODE "create install"
exitIfFailed $COMPRESS_RETURNCODE "create tar files"

echo -n "End timestamp: "; date
echo "==== Success ===="
