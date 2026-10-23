import QtQuick

Item {
    id: root
    property bool checked: false
    signal toggled(bool on)

    width: 44
    height: 24
    opacity: enabled ? 1 : 0.45

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: root.checked ? theme.accent : "#22303A"
        Behavior on color { ColorAnimation { duration: 150 } }
    }

    Rectangle {
        objectName: "knob"
        x: root.checked ? 22 : 3
        y: 3
        width: 18
        height: 18
        radius: 9
        color: "#F2FBFF"
        Behavior on x { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: root.toggled(!root.checked)
    }
}
