import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string label: ""
    property string value: "—"
    spacing: 2

    Text {
        text: root.label
        color: theme.muted
        font.pixelSize: 13
    }
    Text {
        text: root.value
        color: theme.textSoft
        font.pixelSize: 15
        font.bold: true
    }
}
