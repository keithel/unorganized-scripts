#!/usr/bin/env python3
"""Module to return the Qt version of a Qt codebase.

This module provides a function that returns the version of a Qt codebase, given
the toplevel qt5 repository directory. Note, the `qt5` directory applies to both
Qt 5.x and Qt 6.x

If it is run standalone with a python interpreter and not as part of another
Python module, it must be run from the toplevel directory of a qt5 repository
with the qtbase git submodule cloned and checked out.
"""

from __future__ import print_function # For python2 portability
import os
import os.path
import sys
import re
import argparse
from functools import reduce

def qt_version(qt5_dir):
    """Returns the Qt version of a Qt codebase"""

    last_version = None
    try:
        changesFiles = os.listdir(qt5_dir + "/qtbase/dist")

        # Every version released has a 'changes-<version #>' file describing what
        # changed - we will use that to figure out the closest version number to
        # this checked out code.
        # Only include versions that have version numbers that conform to standard
        # version numbering rules (major.minor.release)
        regex = r"^changes-([0-9.]*)"
        src = re.search

        versions = [m.group(1) for changesFile in changesFiles for m in [src(regex, changesFile)] if m]

        # Fetch version from qtbase/.cmake.conf
        cmake_conf_path = qt5_dir + "/qtbase/.cmake.conf"
        if os.path.exists(cmake_conf_path):
            # Qt6 uses CMake, and we can determine version from .cmake.conf
            cmake_conf_file = open(cmake_conf_path, 'r')

            regex = r"^\s*set\s*\(\s*QT_REPO_MODULE_VERSION\s*\"([0-9.]*)\""
            def reduce_func(value, element):
                match = re.search(regex, element)
                return match.group(1) if match else value

            qt6_version = reduce(reduce_func, cmake_conf_file, "")
            if qt6_version:
                versions.append(qt6_version)

        versions.sort(key=lambda s: list(map(int, s.split('.'))))
        last_version = versions[-1]
    except:
        print("qtbase doesn't exist. Please pass the path to a qt5 repo.", file=sys.stderr)
        raise

    return last_version

def pyside_version(pyside_setup_dir):
    # Fetch version from sources/pyside6/.cmake.conf
    cmake_conf_path = pyside_setup_dir + "/sources/pyside6/.cmake.conf"
    if os.path.exists(cmake_conf_path):
        # PySide6 uses CMake, and we can determine version from .cmake.conf
        cmake_conf_file = open(cmake_conf_path, 'r')

        regexes = (
            r"^\s*set\s*\(\s*pyside_MAJOR_VERSION\s*\"([0-9.]*)\"",
            r"^\s*set\s*\(\s*pyside_MINOR_VERSION\s*\"([0-9.]*)\"",
            r"^\s*set\s*\(\s*pyside_MICRO_VERSION\s*\"([0-9.]*)\"",
            r"^\s*set\s*\(\s*pyside_PRE_RELEASE_VERSION_TYPE\s*\"([a-z])\"",
            r"^\s*set\s*\(\s*pyside_PRE_RELEASE_VERSION\s*\"([0-9]*)\"")
        version = ["", "", "", "", ""]
        for line in cmake_conf_file:
            for (i, regex) in enumerate(regexes):
                match = re.search(regex, line)
                if match:
                    version[i] = match.group(1)
        return f"{version[0]}.{version[1]}.{version[2]}{version[3]}{version[4]}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("srcdir", metavar='source-dir', type=str,
                        nargs="?", default=os.getcwd(),
                        help="Path to the base of a qt5 or pyside-setup repository")
    args = parser.parse_args()

    try:
        if os.path.isfile("README.pyside6.md"):
            print(pyside_version(args.srcdir))
        else:
            print(qt_version(args.srcdir))
    except FileNotFoundError:
        print("aborting.", file=sys.stderr)
