#!/bin/bash

set -u

git --version >/dev/null 2>&1
if [[ $? -ne 0 ]]; then
    echo >&2 "git is required"
    echo >&2 "aborting."
    exit 1
fi

set -e
gitlogbranch=$(git log -1 --oneline --decorate=short)
case $gitlogbranch in
    *"-> origin/6.8.3)"*)
        ;;
    *", origin/6.8.3,"*)
        ;;
    *", origin/6.8.3)"*)
        ;;
    *)
        echo >&2 "Please be on a new branch that is positioned at the tip of the origin/6.8 branch"
        exit 1
        ;;
esac

revert_msg="I am cherry-picking the new VxWorks specific evdev support from 6.9\n"
revert_msg="${revert_msg}and these commits are not present in Qt 6.9 (and I think conflict with\n"
revert_msg="${revert_msg}it)"
revert_commits="
    456037a4d3c
    af2cf8a67bb
    c4dfb8030c1
"
git_editor_bkup=""
if [[ -v GIT_EDITOR ]]; then
    git_editor_bkup="$GIT_EDITOR"
fi
for revert in $revert_commits; do
    echo "Reverting $revert"
    export GIT_EDITOR="sed -i '\$a\\\n\n$revert_msg'"
    git revert $revert
    echo
done
export GIT_EDITOR="$git_editor_bkup"

echo

# Some small fixes to make the cherry picks apply cleanly
#sed -ie '/^#include <QTimer>/d' src/platformsupport/input/evdevkeyboard/qevdevkeyboardhandler_p.h
sed -i -e 's/#include <QTimer>/#include <qloggingcategory.h>\n/ ; /QT_BEGIN_NAMESPACE/a\\nQ_DECLARE_LOGGING_CATEGORY(qLcEvdevKey)' src/platformsupport/input/evdevkeyboard/qevdevkeyboardhandler_p.h
sed -i -e '/Q_DECLARE_LOGGING_CATEGORY(qLcEvdevKey)/{N;d}' src/platformsupport/input/evdevkeyboard/qevdevkeyboardmanager.cpp
git add src/platformsupport/input/evdevkeyboard/qevdevkeyboardhandler_p.h src/platformsupport/input/evdevkeyboard/qevdevkeyboardmanager.cpp
git commit -m "Remove unused timer include, logging categories to headers"

cherry_pick_commits="
    b46e3cc34c3
    1d0ec32f71e
    1c7e72c8eba
    d5d67a7976d
    3bd189ab7b6cda5ee9f7b91178a8ad41fa7badc5
    6d49bd766f3
    35f0560a2d4
    3dc86e804bd
    ee912e89ba1
    156752917d7
    5e95e2df615d160666ce567705b60d39ededfc6f
    4ac20b3e5ae
"
for cherrypick in $cherry_pick_commits; do
    #echo "Please cherry-pick $cherrypick"
    echo "cherry-picking $cherrypick"
    if [[ $cherrypick == "6d49bd766f3" ]]; then
        set +e
        git cherry-pick $cherrypick
        if [[ $? -ne 0 ]]; then
            set -e
            sed -i -e 's/\(QT_FEATURE_xkbcommon)\))/\1/; /^<<<<<<< HEAD/d; s/^=======/    OR QT_FEATURE_vxworksevdev)/; /^if(QT_FEATURE_evdev OR QT_FEATURE_integrityhid/d; /^>>>>>>>/d' src/platformsupport/CMakeLists.txt
            git add src/platformsupport/CMakeLists.txt
            export GIT_EDITOR="sed -i '\$a\\\n\nResolved conflicts with sed. See 6.9-vxworks-evdev-patches-to-6.8.3.sh.'"
            git cherry-pick --continue
        fi
    else
        git cherry-pick $cherrypick
    fi
done

# Fix build for a small issue after cherry-picks:
# Q_STATIC_LOGGING_CATEGORY incomplete in Qt 6.8, so use Q_LOGGING_CATEGORY
static_logging_category_error_files="src/platformsupport/devicediscovery/qdevicediscovery_vxworks.cpp src/platformsupport/input/vxkeyboard/qvxkeyboardhandler.cpp src/platformsupport/input/vxtouch/qvxtouchhandler.cpp"
sed -i -e 's/Q_STATIC_LOGGING_CATEGORY/Q_LOGGING_CATEGORY/' $static_logging_category_error_files
git add src/platformsupport $static_logging_category_error_files
git commit -m "Q_STATIC_LOGGING_CATEGORY incomplete in Qt 6.8, so use Q_LOGGING_CATEGORY"
