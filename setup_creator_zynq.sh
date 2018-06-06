#!/bin/bash

SCRIPTPATH="$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )"

ARG1=$1
set -e -u
trap "echo >&2 'ERROR: Script failed.'" ERR

QTCREATOR_PATH="/tmp"

function get_labserver_ip()
{
    iface=$(ip a show to '192.168.1.0/24' | awk 'NR==1{print substr($2,0,length($2)-1)}')
    labserver_ip=192.168.1.12
    if [ -z "$iface" ]; then
        iface=$(ip a show to '10.1.10.0/24' | awk 'NR==1{print substr($2,0,length($2)-1)}')
        if [ -z "$iface" ]; then
            echo >&2 "You are not on a supported network! Please connect to either MIFI1234, MIFI4321, or the L-3 Guest network to continue."
            exit 1
        fi
        labserver_ip=10.1.10.33
    fi
}

function findQtCreator() 
{
    candidate_paths=(
        "$HOME/Qt5.9.0/Tools/QtCreator"
        "/opt/Qt5.9.0/Tools/QtCreator"
        "$HOME/Qt/Tools/QtCreator"
        "/opt/Qt5.8.1/Tools/QtCreator"
        "/opt/Qt5.8.0/Tools/QtCreator"
        "$HOME/Qt-OpenSource/Tools/QtCreator"
    )
    for path in ${candidate_paths[*]}; do
        if [ -x "$path/bin/qtcreator" ]; then
            QTCREATOR_PATH=$path
            break
        fi
    done
}

function updateQtChooser()
{
    if [ -e "${QTCREATOR_PATH}/../../5.9/gcc_64/bin/qmake" ] ; then
        QTVER=5.9
    elif [ -e "${QTCREATOR_PATH}/../../5.8/gcc_64/bin/qmake" ] ; then
        QTVER=5.8
    else
        echo "Could not find Qt Desktop version, skipping qtchooser selection."
        return
    fi
    set +e
    qtchooser -l | grep qt${QTVER} >/dev/null 2>&1 ; ret=$?
    set -e
    if [ ${ret} -eq 0 ]; then
       echo >&2 "Warning: Already found qt${QTVER} qtchooser config, skipping qtchooser config."
    else
       qtchooser -install qt${QTVER} ${QTCREATOR_PATH}/../../${QTVER}/gcc_64/bin/qmake
       grep -qF "export QT_SELECT=qt${QTVER}" $HOME/.profile || echo "export QT_SELECT=qt${QTVER}" >> $HOME/.profile
       echo
       echo "To use proper qt command line tools before a graphical logout/login, run this in your shell: "
       echo "  $ export QT_SELECT=qt${QTVER}"
    fi
}

function checkForTC()
{
    get_labserver_ip
    tcpath="/opt/linaro/toolchains/gcc-linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf"
    for tool in gcc g++ gdb; do
        if [ ! -x "$tcpath/bin/arm-linux-gnueabihf-${tool}" ]; then
            echo >&2 "ERROR: Linaro arm-linux-gnueabihf-${tool} not found!"
            echo >&2 "Please download the 6.3.1 2017.02 x86_64 arm-linux-gnueabihf Linaro toolchain"
            echo >&2 "and extract it to /opt/linaro/toolchains:"
            echo >&2 "    $ curl -O http://${labserver_ip}/downloads/ares2_platform/gcc-linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf.tar.xz"
            echo >&2 "    $ sudo mkdir -p /opt/linaro/toolchains"
            echo >&2 "    $ sudo tar -Jxvf gcc-linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf.tar.xz -C /opt/linaro/toolchains"
            echo >&2 "aborting."
            exit 1
        fi
    done
}

findQtCreator
checkForTC
SDKTOOL="$QTCREATOR_PATH/libexec/qtcreator/sdktool"
if [[ ! "$QTCREATOR_PATH" =~ ^$HOME/ ]] ; then
    SDKTOOL="sudo $SDKTOOL"
fi
echo "Using Qt Creator at $QTCREATOR_PATH, sdktool $SDKTOOL"

if [ -n "$ARG1" ]; then
    if [ "$ARG1" == "--help" -o "$ARG1" == "-?" ]; then
        echo "Configures or deconfigures Qt Creator for use with ARES platform, including setting up Xilinx toolchain and ARES X86 to ARM Cross-Qt build."
        echo "    -d    Remove prior configuration of Qt Creator for ARES."
    elif [ "$ARG1" == "-d" ]; then
        set +e
        $SDKTOOL rmKit --id "Ares_Debian_Armhf_(GCC,_Qt_%{Qt:Version})" && echo "Ares Kit removed"
        $SDKTOOL rmQt --id "Qt_%{Qt:Version}_(Ares_Debian_ARM)" && echo "Ares Qt removed"
        $SDKTOOL rmDebugger --id "Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_GDB" && echo "GDB toolchain removed"
        $SDKTOOL rmTC --id "ProjectExplorer.ToolChain.Gcc:Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_G++" && echo "Linaro G++ toolchain removed"
        $SDKTOOL rmTC --id "ProjectExplorer.ToolChain.Gcc:Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_GCC" && echo "Linaro GCC toolchain removed"
        set -e
        echo "All removed"
    fi
    exit 0
fi

BUILDROOT="$( cd "$SCRIPTPATH/../system"; pwd -P)"
echo "Adding configurations to Qt Creator to allow building for the ARES 2 Platform"
$SDKTOOL rmTC --id "ProjectExplorer.ToolChain.Gcc:Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_GCC"
$SDKTOOL addTC --id "ProjectExplorer.ToolChain.Gcc:Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_GCC" --name "GCC (Linaro 6.3.1 2017.02 Armhf)" --path /opt/linaro/toolchains/gcc-linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-gcc --abi arm-linux-generic-elf-32bit --supportedAbis arm-linux-generic-elf-32bit --language 1
echo "Linaro toolchain GCC added"
$SDKTOOL rmTC --id "ProjectExplorer.ToolChain.Gcc:Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_G++"
$SDKTOOL addTC --id "ProjectExplorer.ToolChain.Gcc:Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_G++" --name "G++ (Linaro 6.3.1 2017.02 Armhf)" --path /opt/linaro/toolchains/gcc-linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-g++ --abi arm-linux-generic-elf-32bit --supportedAbis arm-linux-generic-elf-32bit --language 2
echo "Linaro toolchain G++ added"
$SDKTOOL rmDebugger --id "Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_GDB"
$SDKTOOL addDebugger --id "Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_GDB" --name "GDB (Linaro 6.3.1 2017.02 Armhf)" --engine 1 --binary /opt/linaro/toolchains/gcc-linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-gdb
echo "Linaro toolchain GDB added"
$SDKTOOL rmQt --id "Qt_%{Qt:Version}_(Ares_Debian_ARM)"
$SDKTOOL addQt --id "Qt_%{Qt:Version}_(Ares_Debian_ARM)" --name "Qt %{Qt:Version} (Ares Debian ARM)" --qmake $BUILDROOT/qt/build/host-tools/usr/bin/qmake --type RemoteLinux.EmbeddedLinuxQt
echo "Ares Qt added"
$SDKTOOL rmKit --id "Ares_Debian_Armhf_(GCC,_Qt_%{Qt:Version})"
$SDKTOOL addKit --id "Ares_Debian_Armhf_(GCC,_Qt_%{Qt:Version})" --name "Ares Debian Armhf (GCC, Qt %{Qt:Version})" --devicetype "GenericLinuxOsType" --sysroot $BUILDROOT/stretch/root --Ctoolchain "ProjectExplorer.ToolChain.Gcc:Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_GCC" --Cxxtoolchain "ProjectExplorer.ToolChain.Gcc:Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_G++" --debuggerid "Linaro-6.3.1-2017.02-x86_64_arm-linux-gnueabihf_GDB" --qt "Qt_%{Qt:Version}_(Ares_Debian_ARM)"
echo "Kit that binds GCC, G++, GDB, and Qt version together into a usable config for ARES 2 added."
updateQtChooser
echo "All done!"
