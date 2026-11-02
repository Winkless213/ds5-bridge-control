import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property string title: ""
    property string desc: ""
    // True while the row differs from what is saved on the receiver.
    property bool changed: false
    // Config key, e.g. "speakerGain". Set it to get the "原厂默认 X · 还原"
    // line whenever this row no longer matches the factory value.
    property string field: ""
    // Touching changedKeys makes QML re-evaluate this whenever the draft moves;
    // a bare method call would never be re-run.
    readonly property string defaultHint: root.field === "" || bridge.changedKeys === undefined
        ? "" : bridge.defaultHint(root.field)
    default property alias control: controlHost.data

    implicitHeight: root.defaultHint === "" ? 52 : 70
    Layout.fillWidth: true

    // The explanation is a hover tooltip rather than a permanent line: still
    // one pointer away, but off the page the rest of the time.
    MouseArea {
        id: rowHover
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }

    ToolTip {
        objectName: "rowTip"
        visible: root.desc !== "" && rowHover.containsMouse
        delay: 400
        text: root.desc
    }

    RowLayout {
        anchors.fill: parent
        anchors.bottomMargin: 1
        spacing: 16

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1

            RowLayout {
                spacing: 7

                Rectangle {
                    objectName: "changedDot"
                    visible: root.changed
                    width: 7
                    height: 7
                    radius: 3.5
                    color: theme.amber
                }

                Text {
                    objectName: "rowTitle"
                    text: root.title
                    color: root.changed ? theme.amber : theme.text
                    font.pixelSize: 15
                    font.bold: true
                    Behavior on color { ColorAnimation { duration: 150 } }
                }

                Text {
                    visible: root.changed
                    text: "未保存"
                    color: theme.amber
                    opacity: 0.8
                    font.pixelSize: 11
                }
            }

            RowLayout {
                objectName: "defaultHintRow"
                visible: root.defaultHint !== ""
                spacing: 8

                Text {
                    text: root.defaultHint
                    color: theme.muted2
                    font.pixelSize: 12
                }

                Text {
                    objectName: "restoreLink"
                    text: "还原"
                    color: restoreMouse.containsMouse ? theme.text : theme.accent
                    font.pixelSize: 12
                    font.bold: true

                    MouseArea {
                        id: restoreMouse
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: bridge.restoreDefault(root.field)
                    }
                }
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
