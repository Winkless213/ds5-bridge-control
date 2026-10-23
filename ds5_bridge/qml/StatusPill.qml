import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string state: "off"
    property string text: ""

    implicitWidth: 168
    implicitHeight: 34
    radius: 17
    color: state === "busy"
        ? Qt.rgba(0.961, 0.718, 0.306, 0.08)
        : state === "ok"
            ? Qt.rgba(0.435, 0.659, 1, 0.07)
            : Qt.rgba(0.5, 0.58, 0.64, 0.08)
    border.color: state === "busy"
        ? Qt.rgba(0.961, 0.718, 0.306, 0.24)
        : state === "ok"
            ? Qt.rgba(0.435, 0.659, 1, 0.20)
            : Qt.rgba(0.5, 0.58, 0.64, 0.22)
    border.width: 1

    RowLayout {
        anchors.centerIn: parent
        spacing: 7

        Rectangle {
            id: dot
            width: 7
            height: 7
            radius: 4
            color: root.state === "busy"
                ? theme.amber
                : root.state === "ok"
                    ? theme.accent
                    : theme.muted2

            SequentialAnimation on opacity {
                id: pulse
                running: root.state === "busy"
                loops: Animation.Infinite
                NumberAnimation { to: 0.4; duration: 900; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutSine }
                onRunningChanged: {
                    if (!running)
                        dot.opacity = 1
                }
            }
        }

        Text {
            text: root.text
            color: theme.textSoft
            font.pixelSize: 13
        }
    }
}
