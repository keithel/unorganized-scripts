import QtQuick 2.7
import QtQuick.Layouts 1.3
import QtQuick.Controls 1.4

//ListView {
//    model: ListModel {
//        ListElement { bgcolor: "blue" }
//        ListElement { bgcolor: "purple" }
//    }
//    delegate: Rectangle {
//        anchors.left: parent.left
//        anchors.right: parent.right
//        height: delegateText.implicitHeight
//        
//        color: bgcolor
//        Text { id: delegateText; anchors.centerIn: parent; text: index }
//    }
//}

Item {
    id: root
    MouseArea {
        anchors.fill: parent
        onClicked: console.log("MouseArea pressed")
    ListView {
        id: listview
        anchors.fill: parent
        property int someModel: 1
        spacing: 2
        model: someModel
        delegate: Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            height: text.implicitHeight
            color: "#7F00FF"

            // or any other custom widget
            Text {
                id: text
                anchors.centerIn: parent
                text: index*10
            }
        }

        ListView.onAdd: {
            hitMeButton.enabled = (height < parent.height)
        }
        ListView.onRemove: {
            hitMeButton.enabled = (height < parent.height)
        }

        headerPositioning: ListView.PullBackHeader
        header: RowLayout {
                z: 5
                height: Math.max(hitMeButton.implicitHeight, resetButton.implicitHeight) + 5
                clip: true
                spacing: 10

                Button {
                    id: hitMeButton
                    text: "hit me"

                    onClicked: {
                        listview.someModel += 1
                    }
                }

                Button {
                    id: resetButton
                    text: "reset"

                    onClicked: {
                        listview.someModel = 1
                    }
                }
        }
    }
    }
}
