import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 32
        anchors.rightMargin: 32
        anchors.topMargin: 24
        spacing: 0

        Flickable {
            id: flick
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: content.height + 24
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ScrollBar.vertical: DeckScrollBar {}

            ColumnLayout {
                id: content
                width: flick.width - 10
                spacing: 18

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: "关于"
                        color: theme.text
                        font.pixelSize: 30
                        font.bold: true
                        font.letterSpacing: 0.3
                    }
                    Text {
                        text: "版本、协议与兼容性"
                        color: theme.muted
                        font.pixelSize: 14
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 144
                    radius: 20
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#102033" }
                        GradientStop { position: 0.55; color: "#0C1722" }
                        GradientStop { position: 1; color: "#0B1219" }
                    }
                    border.color: "#263B50"

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 26
                        spacing: 18

                        BrandMark {
                            width: 54
                            height: 54
                            radius: 15
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "DS5 Bridge 控制台"
                            color: theme.text
                            font.pixelSize: 26
                            font.bold: true
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: 18

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 238
                        radius: 16
                        color: theme.card
                        border.color: theme.border

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 22
                            spacing: 8

                            Text {
                                text: "技术信息"
                                color: theme.textSoft
                                font.pixelSize: 16
                                font.bold: true
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "配置读写使用 0xF6 / 0xF7，固件版本使用 0xF8，RSSI 与音频状态使用 0xF9，电量使用标准 DualSense 0x01 输入报文。配置体严格按官方固件 v0.7.2 的 19 字节布局打包；不兼容 fork 的 30 字节布局。"
                                color: theme.muted
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                            }
                            Text {
                                text: '<a href="https://github.com/awalol/DS5Dongle">github.com/awalol/DS5Dongle</a>'
                                textFormat: Text.RichText
                                color: theme.accent
                                font.pixelSize: 13
                                linkColor: theme.accent
                                onLinkActivated: function(link) { Qt.openUrlExternally(link) }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 238
                        radius: 16
                        color: theme.card
                        border.color: theme.border

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 22
                            spacing: 8

                            Text {
                                text: "版本与兼容性"
                                color: theme.textSoft
                                font.pixelSize: 16
                                font.bold: true
                            }
                            Text {
                                text: "应用版本 " + theme.version + " · 平台 Windows 10/11"
                                color: theme.muted
                                font.pixelSize: 13
                            }
                            Text {
                                text: "适用固件：官方 v0.7.2 / v0.7.2-hotfix（config v5，19 字节）。v0.8.0 起配置布局变了，本程序会自动切到只读，不会写入。"
                                color: theme.muted
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                            Text {
                                text: "可与 PlayStation Accessories 同时使用；只改接收器设置，不改手柄配置。"
                                color: theme.muted
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                            Text {
                                text: "独立项目，与 Sony、Flydigi、awalol 无隶属关系；DualSense 是 Sony 的商标。"
                                color: theme.muted2
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }

                Rectangle {
                    objectName: "logCard"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 150
                    radius: 16
                    color: theme.card
                    border.color: theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 22
                        spacing: 8

                        Text {
                            text: "诊断日志"
                            color: theme.textSoft
                            font.pixelSize: 16
                            font.bold: true
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "记录连接、配置读写、电量原始数据和错误，出问题时把这个文件夹里的 ds5-bridge.log 发出来即可。保留最近 5 个文件，每个最多 1 MB。"
                            color: theme.muted
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            TextEdit {
                                Layout.fillWidth: true
                                text: bridge.logDir
                                readOnly: true
                                selectByMouse: true
                                color: theme.textSoft
                                selectionColor: theme.accent
                                font.family: theme.mono
                                font.pixelSize: 12
                                wrapMode: TextEdit.WrapAnywhere
                            }
                            DeckButton {
                                objectName: "openLogButton"
                                text: "打开日志目录"
                                onClicked: bridge.openLogFolder()
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: 6 }
            }
        }
    }
}
