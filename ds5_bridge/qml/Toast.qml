import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property string kind: "info"
    property string title: ""
    property string message: ""
    width: 382
    height: 74
    opacity: 0
    y: -14
    visible: opacity > 0

    function accentColor() {
        if (kind === "warning")
            return theme.amber
        if (kind === "error")
            return theme.red
        return theme.accent
    }

    function show(kind, title, message) {
        root.kind = kind
        root.title = title
        root.message = message
        hideTimer.stop()
        showAnim.restart()
        hideTimer.start()
    }

    Rectangle {
        anchors.fill: parent
        radius: 14
        color: theme.card
        border.color: Qt.rgba(1, 1, 1, 0.09)
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.margins: 0
            spacing: 0

            Rectangle {
                Layout.preferredWidth: 4
                Layout.fillHeight: true
                Layout.topMargin: 12
                Layout.bottomMargin: 12
                radius: 2
                color: root.accentColor()
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.margins: 14
                spacing: 2

                Text {
                    text: root.title
                    color: theme.text
                    font.pixelSize: 14
                    font.bold: true
                }
                Text {
                    Layout.fillWidth: true
                    text: root.message
                    color: theme.muted
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
            }
        }
    }

    ParallelAnimation {
        id: showAnim
        NumberAnimation { target: root; property: "opacity"; to: 1; duration: 170; easing.type: Easing.OutCubic }
        NumberAnimation { target: root; property: "y"; to: 0; duration: 220; easing.type: Easing.OutCubic }
    }

    ParallelAnimation {
        id: hideAnim
        NumberAnimation { target: root; property: "opacity"; to: 0; duration: 150; easing.type: Easing.InCubic }
        NumberAnimation { target: root; property: "y"; to: -10; duration: 170; easing.type: Easing.InCubic }
    }

    Timer {
        id: hideTimer
        interval: 3200
        onTriggered: hideAnim.start()
    }
}
