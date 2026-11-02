import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string label: ""
    property string value: "—"
    // Set to tint the value and show a dot before it; "" leaves the row plain.
    property color accent: "transparent"
    spacing: 2

    Text {
        text: root.label
        color: theme.muted
        font.pixelSize: 13
    }
    RowLayout {
        spacing: 6
        Rectangle {
            objectName: "metricDot"
            visible: root.accent.a > 0
            implicitWidth: 7
            implicitHeight: 7
            radius: 3.5
            color: root.accent
        }
        Text {
            Layout.fillWidth: true
            text: root.value
            color: root.accent.a > 0 ? root.accent : theme.textSoft
            font.pixelSize: 15
            font.bold: true
            elide: Text.ElideRight
        }
    }
}
