import QtQuick

Rectangle {
    id: root
    property string text: ""
    property bool primary: false
    property bool danger: false
    signal clicked()

    implicitWidth: 112
    implicitHeight: 38
    radius: 10
    opacity: enabled ? 1 : 0.42
    color: primary
        ? (mouse.pressed ? "#4F8CFF" : mouse.containsMouse ? "#7FB2FF" : "#5E9BFF")
        : mouse.containsMouse
            ? Qt.rgba(1, 1, 1, 0.07)
            : Qt.rgba(1, 1, 1, 0.035)
    border.color: primary
        ? "transparent"
        : danger
            ? Qt.rgba(1, 0.42, 0.48, 0.30)
            : Qt.rgba(1, 1, 1, 0.09)
    border.width: 1
    scale: mouse.pressed ? 0.985 : 1

    Behavior on color { ColorAnimation { duration: 140 } }
    Behavior on scale { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }

    Text {
        anchors.centerIn: parent
        text: root.text
        color: root.primary ? "#06111E" : root.danger ? theme.red : theme.textSoft
        font.pixelSize: 13
        font.bold: root.primary
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
