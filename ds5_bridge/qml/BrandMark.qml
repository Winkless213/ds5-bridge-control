import QtQuick

Rectangle {
    id: mark
    width: 38
    height: 38
    radius: 11

    gradient: Gradient {
        GradientStop { position: 0; color: theme.accent }
        GradientStop { position: 1; color: theme.accent2 }
    }

    Text {
        anchors.centerIn: parent
        text: "DS5"
        color: "#07111E"
        font.family: "Bahnschrift"
        font.pixelSize: 13
        font.bold: true
    }
}
