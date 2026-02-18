#!/usr/bin/env python
"""
A tool to manually mirror the Qt for Python repository (branches and tags) to
another remote repository store.
"""

import os
import os.path
import sys
import argparse
import getpass
import itertools
import shutil
from typing import List, Union
from tempfile import TemporaryDirectory
from git import Repo, RemoteReference

mirror = {
    "name": "myfork",
    "base_url": "github.com/keithel",
    "repo_name": "pyside-setup.git"
}

def init_test():
    print("Testing mode.", file=sys.stderr)
    mirror["name"] = "local"
    mirror["base_url"] = "/tmp/pyside-mirror"

    mirror_dir = f"{mirror['base_url']}/{mirror['repo_name']}"
    try:
        os.makedirs(mirror_dir)
    except FileExistsError:
        shutil.rmtree(mirror_dir)
        os.makedirs(mirror_dir)
    test_repo = Repo.init(mirror_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--username", metavar="username", type=str,
        default=getpass.getuser().replace("admin", ""),
        help=f"Username to use to authenticate with {mirror['base_url']}")
    parser.add_argument("--reference", metavar="pyside_reference", type=str,
        help="Provide a pyside-setup clone to use as a reference repo when "
            "cloning pyside-setup. This speeds up the cloning process, reusing "
            "the objects in the reference repository. For example "
            "'/build/tmp/pyside-setup'")
    parser.add_argument("--test", action="store_true",
        help=f"Test mirroring to a local repository in /tmp")
    args = parser.parse_args()
    username=args.username

    if args.test:
        init_test()
    print(f"mirror: {str(mirror)}")

    print(f"Using username {username}")
    print()

    PYSIDE_DIRNAME = "pyside-setup"
    orig_cwd = os.getcwd()
    with TemporaryDirectory(prefix="pyside-setup-mirror") as temp_dirname:
        os.chdir(temp_dirname)
        multi_opts = [f"--reference={args.reference}"] if args.reference else None
        if not os.path.exists(PYSIDE_DIRNAME):
            repo = Repo.clone_from("https://code.qt.io/pyside/pyside-setup.git",
                PYSIDE_DIRNAME, multi_options=multi_opts)
        else:
            repo = Repo(PYSIDE_DIRNAME)

        mirror_url = f"{mirror['base_url']}/pyside-setup.git"
        if not mirror['base_url'].startswith("/"):
            mirror_url = f"https://{username}@{mirror['base_url']}/pyside-setup.git"
        mirror_remote = repo.create_remote(mirror["name"], url=mirror_url)
        mirror_remote.fetch(recurse_submodules='no')
        qt_remote = repo.remotes.origin



        protected_branch_failures : List[Union[RemoteReference, str]] = []
        print(f"Pushing pyside-setup refs/remotes/{qt_remote.name}/*:refs/heads"
            f"/* to {mirror_remote.name}")
        wrote_pushinfo=False
        pushinfos = mirror_remote.push(refspec=f"refs/remotes/{qt_remote.name}/"
            "*:refs/heads/*")
        for info in pushinfos:
            if "up to date" not in info.summary:
                wrote_pushinfo=True
                if "protected branch hook declined" in info.summary:
                    assert isinstance(info.local_ref, RemoteReference)
                    protected_branch_failures.append(info.local_ref)
                sys.stdout.write(f"    {info.local_ref} -> "
                    f"{info.remote_ref_string}: {info.summary}")
        if not wrote_pushinfo:
            print("    All up to date")
        print(f"\nPushing pyside-setup refs/tags/*:refs/tags/* to "
            f"{mirror_remote.name}")
        wrote_pushinfo=False
        pushinfos = mirror_remote.push(refspec="refs/tags/*:refs/tags/*")
        for info in pushinfos:
            if "up to date" not in info.summary:
                wrote_pushinfo=True
                sys.stdout.write(f"    {info.local_ref} -> "
                    f"{info.remote_ref_string}: {info.summary}")
        if not wrote_pushinfo:
            print("    All up to date")

        failures=len(protected_branch_failures) > 0
        if failures:
            print("pyside-setup errors syncing repository or specific "
                "branches:", file=sys.stderr)
        for failed_ref in protected_branch_failures:
            failed_ref_str = failed_ref.remote_head if hasattr(failed_ref,
                "remote_head") else failed_ref
            print(f"    {failed_ref_str}, file=sys.stderr")
    os.chdir(orig_cwd)

    sys.exit(1 if failures else 0)
