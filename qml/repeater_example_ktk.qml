import QtQuick 2.0
import QtQuick.Layouts 1.3
import QtQuick.Controls 1.4

ColumnLayout {
        anchors.fill: parent
        property int someModel: 1
        spacing: 5

        Repeater {
            model: parent.someModel
            delegate: Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#FF00FF"

                // or any other custom widget
                Text {
                    anchors.centerIn: parent
                    text: index
                }
            }
        }

        RowLayout {
            spacing: 10

            Button {
                text: "hit me"

                onClicked: {
                    parent.parent.someModel += 1
                }
            }

            Button {
                text: "reset"

                onClicked: {
                    parent.parent.someModel = 1
                }
            }
        }
    }
