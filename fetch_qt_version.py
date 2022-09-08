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
import sys
import re
import argparse

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

            qt6_version = ""
            for line in cmake_conf_file:
                if "QT_REPO_MODULE_VERSION" in line:
                    qt6_version = line.split('"')[1]
                    break
            if qt6_version:
                versions.append(qt6_version)

        versions.sort(key=lambda s: list(map(int, s.split('.'))))
        last_version = versions[-1]
    except:
        print("qtbase doesn't exist. Please pass the path to a qt5 repo.", file=sys.stderr)
        raise

    return last_version


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("srcdir", metavar='source-dir', type=str,
                        nargs="?", default=os.getcwd(),
                        help="Path to the base of a qt5 repository")
    args = parser.parse_args()

    try:
        print(qt_version(args.srcdir))
    except FileNotFoundError:
        print("aborting.", file=sys.stderr)
