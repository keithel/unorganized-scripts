#!/usr/bin/env python
import os
import os.path
import sys
from typing import Tuple, List
from tempfile import TemporaryDirectory
from git import Repo, Submodule, InvalidGitRepositoryError
import argparse
import getpass
import itertools

mirror = {
    "name": "mirror",
    "base_url": "mygitmirror.com/qt"
}

def submodules(qt5_repo, alternates) -> Tuple[List[Submodule], List[Submodule]]:
    orig_cwd = os.getcwd()
    try:
        os.chdir(qt5_repo.working_dir)
        alternates_cmd = f"--alternates {alternates}" if alternates else ""
        ret = os.system(f"perl ./init-repository --force --module-subset=default,-preview,-qtnetworkauth,-qtpurchasing,-qtquick3d,-qtlottie,-qtcharts,-qtdatavis3d,-qtvirtualkeyboard,-qtwayland,-qtwebglplugin,-qtactiveqt,-qtconnectivity,-qtcoap,-qtmqtt,-qtopcua,-qtquicktimeline,-qtquickeffectmaker,qthttpserver,qtquick3dphysics {alternates_cmd}")
        exitcode = os.waitstatus_to_exitcode(ret)
        if exitcode != 0:
            print(f"perl ./init-repository exit code: {exitcode}")
            raise OSError(exitcode, "perl ./init-repository process failed.")
    finally:
        os.chdir(orig_cwd)
    submodules = qt5_repo.submodules
    cloned_submodules = [ submodule for submodule in submodules if os.path.isdir(f"{qt5_repo.working_dir}/{submodule}/.git") ]
    print(f"{len(submodules)} submodules found, {len(cloned_submodules)} are cloned.")
    print()

    # make a flat list of the submodules of each of these submodules.
    # This flattens only one level deep - so if any of these have submodules
    # themselves, they will not be flattened.
    sub_submodules = [ sub_sub for subm in cloned_submodules for sub_sub in Repo(f"{qt5_repo.working_dir}/{subm}").submodules ]
    return cloned_submodules, sub_submodules

def resolve_relative_url(url) -> str:
    split_url = url.split("/")
    split_url_res=[]
    for chunk in split_url:
        if chunk == "..":
            try:
                del split_url_res[-1]
            except:
                pass
        else:
            split_url_res.append(chunk)
    return "/".join(split_url_res)

def mirror_submodule(subm: Submodule):
    repo = Repo(subm.abspath)
    ref_sync_failures={}
    protected_branch_failures=[]
    if mirror["name"] not in repo.remotes:
        submodule_url = f"../{os.path.basename(subm.url)}" if subm.url.startswith("http") else subm.url
        mirror_url = resolve_relative_url(f"https://{username}@{mirror['base_url']}/qt5.git/{submodule_url}")
        mirror_remote = repo.create_remote(mirror["name"], url=mirror_url)
        mirror_remote.fetch(recurse_submodules='no')
        qt_remote = repo.remotes.origin
        print(f"Pushing {os.path.basename(submodule_url)} submodule refs/remotes/{qt_remote.name}/*:refs/heads/* to {mirror_remote.name}")
        wrote_pushinfo=False
        pushinfos = mirror_remote.push(refspec=f"refs/remotes/{qt_remote.name}/*:refs/heads/*")
        for info in pushinfos:
            if "up to date" not in info.summary:
                wrote_pushinfo=True
                if "protected branch hook declined" in info.summary:
                    protected_branch_failures.append(info.local_ref)
                sys.stdout.write(f"    {info.local_ref} -> {info.remote_ref_string}: {info.summary}")
        if not wrote_pushinfo:
            print("    All up to date")
        if len(protected_branch_failures) > 0:
            ref_sync_failures[subm.name] = protected_branch_failures
        print(f"Pushing {os.path.basename(submodule_url)} submodule refs/tags/*:refs/tags/* to {mirror_remote.name}")
        wrote_pushinfo=False
        pushinfos = mirror_remote.push(refspec=f"refs/tags/*:refs/tags/*")
        for info in pushinfos:
            if "up to date" not in info.summary:
                wrote_pushinfo=True
                sys.stdout.write(f"    {info.local_ref} -> {info.remote_ref_string}: {info.summary}")
        if not wrote_pushinfo:
            print("    All up to date")
    return ref_sync_failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--username", metavar="username", type=str,
                        default=getpass.getuser().replace("admin", ""),
                        help=f"Username to use to authenticate with {mirror['base_url']}")
    parser.add_argument("--alternates", metavar="qt5_alternates", type=str,
                        help="Provide a qt5 clone to use as alternate repositories when cloning qt5 submodules. This speeds up the cloning process, reusing the objects in the alternate repositories. For example '/build/tmp/qt5'")
    args = parser.parse_args()
    username=args.username

    print(f"Using username {username}")
    print()

    qt5_dirname = "qt5"
    orig_cwd = os.getcwd()
    with TemporaryDirectory(prefix="qt5-mirror") as temp_dirname:
        os.chdir(temp_dirname)
        if not os.path.exists(qt5_dirname):
            qt5_repo = Repo.clone_from(f"https://code.qt.io/qt/qt5.git", qt5_dirname)
        else:
            qt5_repo = Repo(qt5_dirname)

        ref_sync_failures={}
        subms, sub_subms = submodules(qt5_repo, args.alternates)
        for submodule in itertools.chain(sub_subms, subms):
            print(f"Mirroring {submodule}")
            try:
                ref_sync_failures |= mirror_submodule(submodule)
            except InvalidGitRepositoryError:
                # Uninitialized submodule - just skip it.
                pass
            except git.GitCommandError as e:
                if "returned error: 403" in e.stderr:
                    print(f"No permission to push to {mirror['name']}", file=sys.stderr)
                    ref_sync_failures[submodule.name] = [ "403 Forbidden on repository" ]
                else:
                    raise

        if len(ref_sync_failures) > 0:
            print("The following submodules have permissions issues preventing mirroring:", file=sys.stderr)
        else:
            print("Mirroring successful!")
        for submodule, protected_branch_failures in ref_sync_failures.items():
            print(f"{submodule.name} errors syncing repository or specific branches:", file=sys.stderr)
            for failed_ref in protected_branch_failures:
                print(f"    {failed_ref.remote_head}, file=sys.stderr")
    os.chdir(orig_cwd)

    sys.exit(0 if len(ref_sync_failures) == 0 else 1)
