import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property int from: 0
    property int to: 100
    property int value: 0
    property string valueText: String(value)
    signal valueEdited(real value)

    implicitWidth: 258
    implicitHeight: 34

    RowLayout {
        anchors.fill: parent
        spacing: 12

        DeckSlider {
            Layout.fillWidth: true
            from: root.from
            to: root.to
            value: root.value
            onValueEdited: function(value) { root.valueEdited(value) }
        }

        Text {
            Layout.preferredWidth: 52
            horizontalAlignment: Text.AlignRight
            text: root.valueText
            color: theme.textSoft
            font.pixelSize: 14
            font.bold: true
        }
    }
}
