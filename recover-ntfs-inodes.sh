#!/bin/bash

# Script to recover multiple inodes of deleted files discovered in the NTFS MFT
# file of an NTFS volume

set -e
set -u

echo "$0 $@"

inode_file=${1:-""}
shift
if [[ ! -f "$inode_file" ]]; then
    echo >&2 "Please provide a file of inodes to undelete"
    exit 1
fi

device=${1:-""}
if [[ ! -b "$device" ]]; then
    echo >&2 "Please provide a block device file as the second parameter"
    exit 1
fi

inodes=$(cat ${inode_file})

# Check to see if they are all integers (we will assume inode)
re='^[0-9]+$'
for inode in $inodes; do
    if [[ ! $inode =~ $re ]] ; then
        echo >&2 "error: $inode is not a number"
        exit 1
    fi
done

set +e
# Now undelete them with remaining command line options going to ntfsundelete
for inode in $inodes; do
    echo "Undeleting inode $inode"
    sudo ntfsundelete $@ -u -i $inode
    if [[ $? -ne 0 ]]; then
        echo >&2 "**** Failed to undelete inode $inode ****"
    fi
done
