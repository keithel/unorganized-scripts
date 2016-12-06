import QtQuick 2.6
import QtQuick.Window 2.2
import QtQuick.Layouts 1.1

Window {
    visible: true
    width: 400
    height: 400

    ColumnLayout {
        id: layout

        anchors.centerIn: parent
        width: parent.width * 0.8
        height: parent.height * 0.8

        spacing: 10

        Text {
            Layout.fillWidth: true
            text: "Lorem Ipsum is simply dummy text of the printing and typesetting industry."
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: "Lorem Ipsum is simply dummy text of the printing and typesetting industry."
        }

        Text {
            Layout.fillWidth: true
            elide: Text.ElideRight
            text: "Lorem Ipsum is simply dummy text of the printing and typesetting industry."
        }

        Text {
            Layout.fillWidth: true
            elide: Text.ElideRight
            wrapMode: Text.Wrap
            maximumLineCount: 4
            text: "Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. It has survived not only five centuries, but also the leap into electronic typesetting, remaining essentially unchanged. It was popularised in the 1960s with the release of Letraset sheets containing Lorem Ipsum passages, and more recently with desktop publishing software like Aldus PageMaker including versions of Lorem Ipsum."
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }

    Rectangle {
        anchors.fill: layout
        color: "yellow"
        z: -1
    }
}
