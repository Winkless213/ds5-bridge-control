import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property int value: 0
    property int from: 0
    property int to: 10
    property var labels: []
    property string zeroLabel: ""
    property string suffix: ""
    signal changed(int value)

    implicitWidth: 132
    implicitHeight: 34
    radius: 9
    color: Qt.rgba(1, 1, 1, 0.035)
    border.color: Qt.rgba(1, 1, 1, 0.08)

    function textFor(v) {
        if (zeroLabel !== "" && v === 0)
            return zeroLabel
        if (labels && labels.length > v && labels[v] !== undefined)
            return labels[v]
        return String(v) + suffix
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 2
        spacing: 0

        Item {
            Layout.preferredWidth: 32
            Layout.fillHeight: true
            Rectangle {
                anchors.fill: parent
                anchors.margins: 2
                radius: 7
                color: minusMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.07) : "transparent"
            }
            Text {
                anchors.centerIn: parent
                text: "−"
                color: root.value > root.from ? theme.textSoft : theme.muted2
                font.pixelSize: 18
            }
            MouseArea {
                id: minusMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                enabled: root.enabled && root.value > root.from
                onClicked: root.changed(Math.max(root.from, root.value - 1))
            }
        }

        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: root.textFor(root.value)
            color: theme.textSoft
            font.pixelSize: 13
            font.bold: true
        }

        Item {
            Layout.preferredWidth: 32
            Layout.fillHeight: true
            Rectangle {
                anchors.fill: parent
                anchors.margins: 2
                radius: 7
                color: plusMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.07) : "transparent"
            }
            Text {
                anchors.centerIn: parent
                text: "+"
                color: root.value < root.to ? theme.textSoft : theme.muted2
                font.pixelSize: 17
            }
            MouseArea {
                id: plusMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                enabled: root.enabled && root.value < root.to
                onClicked: root.changed(Math.min(root.to, root.value + 1))
            }
        }
    }
}
