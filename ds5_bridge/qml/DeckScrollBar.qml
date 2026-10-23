import QtQuick
import QtQuick.Controls

ScrollBar {
    policy: ScrollBar.AsNeeded
    width: 8

    background: Rectangle {
        implicitWidth: 5
        radius: 2.5
        color: Qt.rgba(1, 1, 1, 0.04)
    }

    contentItem: Rectangle {
        implicitWidth: 5
        radius: 2.5
        color: theme.accent
        opacity: 0.28
    }
}
