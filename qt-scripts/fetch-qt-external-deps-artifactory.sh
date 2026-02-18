#!/usr/bin/env bash
# Fetch external dependencies needed by Qt6 build (Fetched from artifactory)

set -e
set -u

startingPwd=$PWD

# Parameter 1 - Absolute path to workspace directory
if [ $# -eq 0 ]; then
    echo >&2 "Need to pass workspace directory to the script"
    exit 1
fi

ONLY_DELETE=""
if [[ $# -gt 1 && "$2" == "-d" ]]; then
    ONLY_DELETE=1
    echo "Deleting expanded archives"
fi

# Location of the workspace directory (root)
export WORKSPACE_DIR=$1

OS=
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    PYTHON=python3
    echo "Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    PYTHON=python3
    echo "macOS"
else
    OS="windows"
    PYTHON=python
    echo "Empty OSTYPE, assuming Windows."
fi

# Location of external dependencies directory
export EXTERNAL_DEPENDENCIES_DIR=$WORKSPACE_DIR/external_dependencies
if [[ ! -e $EXTERNAL_DEPENDENCIES_DIR ]]; then
    mkdir $EXTERNAL_DEPENDENCIES_DIR
fi


# First fetch the name of the artifacts we are going to use.
curlCmdSilent="curl -s -S"
artifactoryRoot="https://artifactory.example.com/artifactory/"

# Test connection to artifactory
set +e
testOut=$($curlCmdSilent $artifactoryRoot 2>&1)
set -e
if [[ "$testOut" =~ "Could not resolve host" ]]; then
    echo >&2 "Couldn't connect to $artifactoryRoot, verify connection to VPN. Aborting."
    exit 1
fi

# Which cmake artifact to use
if [[ $OS == "windows" ]]; then
	cmakeUri="team--generic/Cmake/cmake-3.22.1-windows-x86_64.zip"
elif [[ $OS == "linux" ]]; then
	cmakeUri="team--generic/Cmake/cmake-3.22.1-linux-x86_64.tar.gz"
elif [[ $OS == "macos" ]]; then
	cmakeUri="team--generic/Cmake/cmake-3.22.1-macos-universal.tar.gz"
fi

# Which ninja artifact to use
if [[ $OS == "windows" ]]; then
	ninjaUri="team--generic/ninja/1.10.2/ninja-1.10.2-win.zip"
elif [[ $OS == "linux" ]]; then
	ninjaUri="team--generic/ninja/1.10.2/ninja-linux.tar.gz"
elif [[ $OS == "macos" ]]; then
	ninjaUri="team--generic/ninja/1.10.2/ninja-mac.tar.gz"
fi

# Which node artifact to use
if [[ $OS == "windows" ]]; then
	nodeUri="team--generic/node.js/16.14.0/node-v16.14.0-win-x64.zip"
elif [[ $OS == "linux" ]]; then
	nodeUri="team--generic/node.js/16.14.0/node-v16.14.0-linux-x64.tar.xz"
elif [[ $OS == "macos" ]]; then
	nodeUri="team--generic/node.js/16.14.0/node-v16.14.0-darwin-x64.tar.gz"
fi

# Which python artifact to use
if [[ $OS == "windows" ]]; then
	pythonUri="team--generic/python/3.10.6/cpython-3.10.6-win-MANUAL-2022_08_31_1430.zip"
elif [[ $OS == "linux" ]]; then
	pythonUri="team--generic/python/3.10.6/cpython-3.10.6-gcc-9.3.1-openssl-1.1.1k_MANUAL.zip"
elif [[ $OS == "macos" ]]; then
    # System python3 now used on macOS
	pythonUri=""
fi

# Which OpenSSL artifact to use - not used on all platforms
if [[ $OS == "windows" ]]; then
	opensslArtifactDownloadUri="team--generic/openssl/1.1.1g/openssl-1.1.1g-win-vc140.zip"
elif [[ $OS == "linux" ]]; then
	opensslArtifactDownloadUri="team--generic/openssl/1.1.1g/openssl-1.1.1g-lnx-centos76-gcc485.tar.gz"
elif [[ $OS == "macos" ]]; then
	opensslArtifactDownloadUri=""
fi

gnuwin32ArtifactDownloadUri=""
if [[ $OS == "windows" ]]; then
	gnuwin32ArtifactDownloadUri="team--generic/gnuwin32/gnuwin32.zip"
fi
artifactDownloadUris=($cmakeUri $ninjaUri $nodeUri $pythonUri $opensslArtifactDownloadUri $gnuwin32ArtifactDownloadUri)



# Download artifacts from artifactory
cd $EXTERNAL_DEPENDENCIES_DIR

for artifactDownloadUri in ${artifactDownloadUris[@]}; do
    artifactBasename=$(basename $artifactDownloadUri)
    if [ -n "$artifactDownloadUri" ]; then
        # Fetch the md5sum of the artifact from Artifactory
        artifactls=$($curlCmdSilent ${artifactoryRoot}api/storage/${artifactDownloadUri})
        artifactls=$(echo $artifactls)
        artifactDownloadMd5=$($PYTHON -c "import json; print(json.loads('$artifactls')['checksums']['md5'])")

        if [[ -e "$artifactBasename" ]]; then
            echo >&2 "$artifactBasename exists."
	    if [[ $OS == "macos" ]]; then
                localMd5=$(md5 -q $artifactBasename)
            else
                localMd5=$(md5sum $artifactBasename | awk '{print $1}')
            fi
            if [[ $localMd5 == $artifactDownloadMd5 ]]; then
                echo "md5sums match, using cached artifact package."
            else
                mv -f "$artifactBasename" "$artifactBasename.bak"
            fi
        fi

        if [[ ! -e "$artifactBasename" ]]; then
            artifactDownloadUri="${artifactoryRoot}${artifactDownloadUri}"
            echo "Downloading artifact $artifactDownloadUri"
            curl -O $artifactDownloadUri
            if [ $? -gt 0 ]; then
                echo >&2 "Failed to download artifact $artifactDownloadUri. Aborting."
                exit 1
            fi
        fi
    fi
done

# Remove artifact dirs if they exist (these ones we remove because there may be contamination in the
# expanded python dir)
# Just delete all directories, leave files, as those will most likely be the artifact packages.
find . -maxdepth 1 -type d -a -not -name "." -exec rm -Rf {} \;

if [[ $ONLY_DELETE -eq 1 ]]; then exit 0; fi

# Expand artifacts to the external_dependencies directory
for artifactDownloadUri in ${artifactDownloadUris[@]}; do
    artifactBasename=$(basename $artifactDownloadUri)
    if [ -n "$artifactDownloadUri" ]; then
        echo -n "Expanding artifact $artifactBasename"
        if [ $OS == "windows" ]; then
            7z x "$artifactBasename"
            if [ $? -gt 0 ]; then
                echo >&2 "Failed to unpack artifact $artifactBasename with 7zip. Aborting."
                exit 1
            fi
        else
            case $artifactBasename in
              *.tar.gz)
                unc_cmd="tar zxvf $artifactBasename"
                ;;
              *.tar.xz)
                unc_cmd="tar Jxvf $artifactBasename"
                ;;
              *.zip)
                unc_cmd="unzip $artifactBasename"
                ;;
              *)
                echo >&2 "error: $artifactBasename extension unknown."
                exit 1
            esac
            pwd
            $unc_cmd 2>&1 | python -c "
import sys
for line in sys.stdin:
    sys.stdout.write('.')
    sys.stdout.flush()
sys.stdout.write('\n')"
            if [ $? -gt 0 ]; then
                echo >&2 "Failed to unpack artifact $artifactBasename. Aborting."
                exit 1
            fi
        fi
    fi
done

echo "---- Success Finished ----"
