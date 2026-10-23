import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string title: ""
    property string subtitle: ""
    property string summary: ""
    property bool open: true
    property int contentHeight: 200
    property bool hovered: false
    property real targetHeight: open ? 84 + contentHeight : 84
    default property alias content: body.data
    signal toggleRequested()

    Layout.fillWidth: true
    Layout.preferredHeight: targetHeight
    radius: 16
    color: theme.card2
    border.width: 1
    border.color: open
        ? "#2A4052"
        : hovered
            ? "#24384A"
            : theme.border
    clip: true
    scale: headerMouse.pressed ? 0.996 : 1

    Behavior on targetHeight { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
    Behavior on border.color { ColorAnimation { duration: 170 } }
    Behavior on scale { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 44

            RowLayout {
                anchors.fill: parent
                spacing: 12

                Rectangle {
                    width: 4
                    height: 20
                    radius: 1
                    color: theme.accent
                }

                ColumnLayout {
                    spacing: 1
                    Text {
                        text: root.title
                        color: theme.textSoft
                        font.pixelSize: 16
                        font.bold: true
                        font.letterSpacing: 0.5
                    }
                    Text {
                        text: root.subtitle
                        color: theme.muted
                        font.pixelSize: 13
                    }
                }

                Item { Layout.fillWidth: true }

                Text {
                    Layout.maximumWidth: 300
                    text: root.summary
                    color: "#C7D6E1"
                    font.pixelSize: 13
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignRight
                }

                Text {
                    text: "⌄"
                    color: theme.textSoft
                    font.pixelSize: 20
                    rotation: root.open ? 180 : 0
                    scale: headerMouse.pressed ? 0.86 : 1
                    Behavior on rotation { NumberAnimation { duration: 220; easing.type: Easing.InOutCubic } }
                    Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
                }
            }

            MouseArea {
                id: headerMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onEntered: root.hovered = true
                onExited: root.hovered = false
                onClicked: root.toggleRequested()
            }
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            Layout.preferredHeight: root.contentHeight
            spacing: 0
            clip: true
            enabled: root.open
            opacity: root.open ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 190 } }
        }
    }
}
