#!/bin/bash

#    qtdeclarative
#    qt5compat
export modulestoskip="
    qtimageformats
    qtlanguageserver
    qtshadertools
    qtsvg
    qtquick3d
    qtmultimedia
    qt3d
    qtactiveqt
    qtbase.git
    qtconnectivity
    qtdeclarative.git
    qtgraphs
    qthttpserver
    qtserialport
    qtpositioning
    qtlocation
    qttools
    qtwebsockets
    qtdoc
    qtremoteobjects
    qtscxml
    qtsensors
    qtserialbus
    qtspeech
    qttranslations
    qtwayland
    qtwebchannel
    qtwebview
    qtwebengine"

skipmodopts=""
for skipmod in $modulestoskip ; do
    skipmodopts="$skipmodopts -DBUILD_${skipmod}=OFF"
done
cmake .. -GNinja -DQT_HOST_PATH=~/Qt/6.8.1/gcc_64 -DQT_NO_PACKAGE_VERSION_CHECK=TRUE -DQT_NO_PACKAGE_VERSION_INCOMPATIBLE_WARNING=TRUE $skipmodopts
