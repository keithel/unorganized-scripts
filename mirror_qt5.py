#!/usr/bin/env python
"""
A tool to manually mirror Qt5 submodules (branches and tags) to another remote
repository store.
"""

import os
import os.path
import sys
import argparse
import getpass
import itertools
from typing import Tuple, List, Dict, Union
from tempfile import TemporaryDirectory
from git import Repo, InvalidGitRepositoryError, GitCommandError, RemoteReference
from git import Submodule # type: ignore[attr-defined]

mirror = {
    "name": "mirror",
    "base_url": "mygitmirror.com/qt"
}

def qt5_submodules(qt5_repo: Repo, alternates: str) -> Tuple[List[Submodule], List[Submodule]]:
    """
    Initialize a qt5 repository's submodules, and return two lists - one of the direct initialized
    qt5 submodules, and the other a list of the submodules of qt5's submodules (one level deep).
    """
    cwd = os.getcwd()
    try:
        os.chdir(str(qt5_repo.working_dir))
        alternates_cmd = f"--alternates {alternates}" if alternates else ""
        ret = os.system("perl ./init-repository --force --module-subset=default,-preview,"
            "-qtnetworkauth,-qtpurchasing,-qtquick3d,-qtlottie,-qtcharts,-qtdatavis3d,"
            "-qtvirtualkeyboard,-qtwayland,-qtwebglplugin,-qtactiveqt,-qtconnectivity,-qtcoap,"
            "-qtmqtt,-qtopcua,-qtquicktimeline,-qtquickeffectmaker,qthttpserver,qtquick3dphysics"
            f" {alternates_cmd}")
        #ret = os.system(f"perl ./init-repository --force --module-subset=qtbase {alternates_cmd}")
        exitcode = os.waitstatus_to_exitcode(ret)
        if exitcode != 0:
            print(f"perl ./init-repository exit code: {exitcode}")
            raise OSError(exitcode, "perl ./init-repository process failed.")
    finally:
        os.chdir(cwd)
    submodules = qt5_repo.submodules
    cloned_submodules = [ submodule for submodule in submodules if
        os.path.isdir(f"{qt5_repo.working_dir}/{submodule}/.git") ]
    print(f"{len(submodules)} submodules found, {len(cloned_submodules)} are cloned.")
    print()

    # make a flat list of the submodules of each of these submodules.
    # This flattens only one level deep - so if any of these have submodules themselves, they will
    # not be flattened.
    sub_submodules = [ sub_sub for subm in cloned_submodules for sub_sub in
        Repo(f"{qt5_repo.working_dir}/{subm}").submodules ]
    return cloned_submodules, sub_submodules

def resolve_relative_url(url: str) -> str:
    """
    This resolves a relative url by splitting it on directory separators, and removing parent
    entries when ".." enries are encountered. The filesystem is not hit when doing this process,
    so the file or URL does not need to exist.
    """
    split_url = url.split("/")
    split_url_res: List[str] = []
    for chunk in split_url:
        if chunk == "..":
            try:
                del split_url_res[-1]
            except IndexError:
                pass
        else:
            split_url_res.append(chunk)
    return "/".join(split_url_res)

def mirror_submodule(subm: Submodule) -> List[Union[RemoteReference, str]]:
    """
    Create a remote for the destination repository for mirroring and push all code.qt.io remote refs
    and all tags to the mirrored remote repository.
    Returns a list of remote refs (branches) that could not be mirrored due to the branches being
    protected.
    """
    sub_repo = Repo(subm.abspath)
    protected_branches: List[Union[RemoteReference, str]] = []
    if mirror["name"] not in sub_repo.remotes:
        submodule_url = (f"../{os.path.basename(subm.url)}" if subm.url.startswith("http")
            else subm.url)
        mirror_url = resolve_relative_url(f"https://{username}@{mirror['base_url']}/qt5.git/"
            f"{submodule_url}")
        mirror_remote = sub_repo.create_remote(mirror["name"], url=mirror_url)
        mirror_remote.fetch(recurse_submodules='no')
        qt_remote = sub_repo.remotes.origin
        print(f"Pushing {os.path.basename(submodule_url)} submodule refs/remotes/{qt_remote.name}/"
            f"*:refs/heads/* to {mirror_remote.name}")
        wrote_pushinfo=False
        pushinfos = mirror_remote.push(refspec=f"refs/remotes/{qt_remote.name}/*:refs/heads/*")
        for info in pushinfos:
            if "up to date" not in info.summary:
                wrote_pushinfo=True
                if "protected branch hook declined" in info.summary:
                    assert isinstance(info.local_ref, RemoteReference)
                    protected_branches.append(info.local_ref)
                sys.stdout.write(f"    {info.local_ref} -> {info.remote_ref_string}: "
                    f"{info.summary}")
        if not wrote_pushinfo:
            print("    All up to date")
        print(f"Pushing {os.path.basename(submodule_url)} submodule refs/tags/*:refs/tags/* to "
            f"{mirror_remote.name}")
        wrote_pushinfo=False
        pushinfos = mirror_remote.push(refspec="refs/tags/*:refs/tags/*")
        for info in pushinfos:
            if "up to date" not in info.summary:
                wrote_pushinfo=True
                sys.stdout.write(f"    {info.local_ref} -> {info.remote_ref_string}: "
                    f"{info.summary}")
        if not wrote_pushinfo:
            print("    All up to date")
    return protected_branches


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--username", metavar="username", type=str,
        default=getpass.getuser().replace("admin", ""),
        help=f"Username to use to authenticate with {mirror['base_url']}")
    parser.add_argument("--alternates", metavar="qt5_alternates", type=str,
        help="Provide a qt5 clone to use as alternate repositories when cloning qt5 submodules. "
            "This speeds up the cloning process, reusing the objects in the alternate "
            "repositories. For example '/build/tmp/qt5'")
    args = parser.parse_args()
    username=args.username

    print(f"Using username {username}")
    print()

    QT5_DIRNAME = "qt5"
    orig_cwd = os.getcwd()
    with TemporaryDirectory(prefix="qt5-mirror") as temp_dirname:
        os.chdir(temp_dirname)
        if not os.path.exists(QT5_DIRNAME):
            repo = Repo.clone_from("https://code.qt.io/qt/qt5.git", QT5_DIRNAME)
        else:
            repo = Repo(QT5_DIRNAME)

        ref_sync_failures: Dict[str, List[Union[RemoteReference, str]]] = {}
        subms, sub_subms = qt5_submodules(repo, args.alternates)
        for submodule in itertools.chain(sub_subms, subms):
            print(f"Mirroring {submodule}")
            try:
                pbranch_failures = mirror_submodule(submodule)
                if pbranch_failures:
                    ref_sync_failures[submodule.name] = pbranch_failures
            except InvalidGitRepositoryError:
                # Uninitialized submodule - just skip it.
                pass
            except GitCommandError as e:
                if "returned error: 403" in e.stderr:
                    print(f"No permission to push to {mirror['name']}", file=sys.stderr)
                    ref_sync_failures[submodule.name] = [ "403 Forbidden on repository" ]
                else:
                    raise

        if len(ref_sync_failures) > 0:
            print("The following submodules have permissions issues preventing mirroring:",
                file=sys.stderr)
        else:
            print("Mirroring successful!")
        for submodule, protected_branch_failures in ref_sync_failures.items():
            print(f"{submodule} errors syncing repository or specific branches:",
                file=sys.stderr)
            for failed_ref in protected_branch_failures:
                failed_ref_str = failed_ref.remote_head if hasattr(failed_ref,
                    "remote_head") else failed_ref
                print(f"    {failed_ref_str}, file=sys.stderr")
    os.chdir(orig_cwd)

    sys.exit(0 if len(ref_sync_failures) == 0 else 1)
