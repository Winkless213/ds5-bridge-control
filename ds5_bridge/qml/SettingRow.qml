import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property string title: ""
    property string desc: ""
    default property alias control: controlHost.data

    implicitHeight: 68
    Layout.fillWidth: true

    RowLayout {
        anchors.fill: parent
        anchors.bottomMargin: 1
        spacing: 16

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1

            Text {
                objectName: "rowTitle"
                text: root.title
                color: theme.text
                font.pixelSize: 15
                font.bold: true
            }

            Text {
                Layout.fillWidth: true
                text: root.desc
                color: theme.muted
                font.pixelSize: 14
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }

        Item {
            id: controlHost
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            implicitWidth: childrenRect.width
            implicitHeight: childrenRect.height
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: theme.borderSoft
    }
}
