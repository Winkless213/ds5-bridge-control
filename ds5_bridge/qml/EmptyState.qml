import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property string detail: ""
    property bool probing: false
    signal retry()

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(520, root.width - 80)
        spacing: 12

        BrandMark {
            Layout.alignment: Qt.AlignHCenter
            width: 54
            height: 54
            radius: 15
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: root.probing ? "正在检测接收器…" : "没有找到 DS5 Bridge"
            color: theme.text
            font.pixelSize: 24
            font.bold: true
        }

        BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            running: root.probing
            visible: root.probing
            width: 28
            height: 28
        }

        Text {
            Layout.fillWidth: true
            text: root.detail
            color: theme.muted
            font.pixelSize: 14
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        DeckButton {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6
            text: "重新检测"
            primary: true
            visible: !root.probing
            onClicked: root.retry()
        }
    }
}
