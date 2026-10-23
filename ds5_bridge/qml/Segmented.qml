import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property var options: []
    property int currentIndex: 0
    signal changed(int index)

    implicitWidth: 240
    implicitHeight: 36
    opacity: enabled ? 1 : 0.45

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: Qt.rgba(1, 1, 1, 0.025)
        border.color: Qt.rgba(1, 1, 1, 0.06)
    }

    Rectangle {
        id: indicator
        width: (root.width - 10) / Math.max(1, root.options.length)
        height: root.height - 10
        y: 5
        x: 5 + root.currentIndex * width
        radius: 7
        color: Qt.rgba(0.435, 0.659, 1, 0.14)
        border.color: Qt.rgba(0.435, 0.659, 1, 0.30)
        Behavior on x { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 5
        spacing: 0

        Repeater {
            model: root.options
            delegate: Item {
                required property int index
                required property string modelData
                Layout.fillWidth: true
                Layout.fillHeight: true

                Text {
                    anchors.centerIn: parent
                    text: modelData
                    color: root.currentIndex === index ? theme.text : theme.muted
                    font.pixelSize: 13
                    font.bold: root.currentIndex === index
                    Behavior on color { ColorAnimation { duration: 150 } }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.changed(index)
                }
            }
        }
    }
}
