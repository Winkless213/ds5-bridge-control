import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: win
    width: 1280
    height: 820
    minimumWidth: 1080
    minimumHeight: 720
    visible: true
    color: theme.bg
    title: "DS5 Bridge 控制台"

    property int page: 0
    readonly property var tabTitles: ["配置", "设备", "关于"]
    readonly property bool rateActive: win.visible
        && win.visibility !== Window.Minimized
        && win.page === 1

    font.family: "Microsoft YaHei UI"
    font.pixelSize: 15

    // Closing the window hides it to the tray; shutdown happens on quit.

    // Ambient background
    Rectangle {
        anchors.fill: parent
        color: theme.bg
    }
    Rectangle {
        width: 760
        height: 760
        radius: 380
        x: -240
        y: -320
        color: Qt.rgba(0.435, 0.659, 1, 0.07)
        opacity: 0.55
    }
    Rectangle {
        width: 640
        height: 640
        radius: 320
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: -240
        anchors.bottomMargin: -280
        color: Qt.rgba(0.545, 0.486, 1, 0.055)
        opacity: 0.5
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 78

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 32
                anchors.rightMargin: 32
                spacing: 18

                RowLayout {
                    spacing: 12
                    BrandMark {}
                    ColumnLayout {
                        spacing: -1
                        Text {
                            text: "DS5 BRIDGE"
                            color: theme.text
                            font.pixelSize: 15
                            font.bold: true
                            font.letterSpacing: 1.1
                        }
                        Text {
                            text: "接收器控制台"
                            color: theme.muted
                            font.pixelSize: 11
                            font.letterSpacing: 0.6
                        }
                    }
                }

                Item { Layout.preferredWidth: 18 }

                Item {
                    Layout.preferredWidth: 330
                    Layout.preferredHeight: 42

                    Rectangle {
                        anchors.fill: parent
                        radius: 12
                        color: Qt.rgba(1, 1, 1, 0.025)
                        border.color: Qt.rgba(1, 1, 1, 0.05)
                    }

                    Rectangle {
                        id: tabPill
                        width: 104
                        height: 34
                        y: 4
                        x: 4 + win.page * 106
                        radius: 9
                        color: Qt.rgba(0.435, 0.659, 1, 0.12)
                        border.color: Qt.rgba(0.435, 0.659, 1, 0.26)
                        Behavior on x { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 2

                        Repeater {
                            model: win.tabTitles
                            delegate: Item {
                                required property int index
                                required property string modelData
                                Layout.fillWidth: true
                                Layout.fillHeight: true

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData
                                    color: win.page === index ? theme.text : theme.muted
                                    font.pixelSize: 14
                                    font.bold: win.page === index
                                    Behavior on color { ColorAnimation { duration: 160 } }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: win.page = index
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                StatusPill {
                    state: bridge.connected ? (bridge.busy ? "busy" : "ok") : "off"
                    text: bridge.connected
                        ? "已连接 · " + bridge.firmware
                        : bridge.probing
                            ? "检测中…"
                            : "未连接"
                }

                Rectangle {
                    width: 128
                    height: 34
                    radius: 17
                    color: Qt.rgba(0.435, 0.659, 1, 0.07)
                    border.color: Qt.rgba(0.435, 0.659, 1, 0.20)

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 7
                        BatteryGlyph {
                            percent: bridge.batteryPercent
                            tint: bridge.batteryPercent >= 0 && bridge.batteryPercent <= 20
                                ? theme.amber
                                : theme.accent
                        }
                        Text {
                            text: bridge.batteryPercent >= 0 ? bridge.batteryPercent + "%" : "—"
                            color: theme.textSoft
                            font.pixelSize: 13
                            font.bold: true
                        }
                    }
                }

                Rectangle {
                    width: 36
                    height: 34
                    radius: 10
                    color: refreshMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.035)
                    border.color: Qt.rgba(1, 1, 1, 0.07)

                    Text {
                        anchors.centerIn: parent
                        text: "↻"
                        color: theme.textSoft
                        font.pixelSize: 17
                    }

                    MouseArea {
                        id: refreshMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: bridge.refresh()
                    }
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Qt.rgba(1, 1, 1, 0.06)
            }
        }

        StackLayout {
            id: pageStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: win.page
            transform: Translate { id: pageShift; y: 0 }

            ConfigPage {
                objectName: "configPage"
                onResetRequested: resetPopup.open()
            }
            DevicePage {}
            AboutPage {}
        }
    }

    ParallelAnimation {
        id: pageIn
        NumberAnimation { target: pageStack; property: "opacity"; to: 1; duration: 200; easing.type: Easing.OutCubic }
        NumberAnimation { target: pageShift; property: "y"; to: 0; duration: 240; easing.type: Easing.OutCubic }
    }

    onPageChanged: {
        pageStack.opacity = 0
        pageShift.y = 8
        pageIn.restart()
    }

    onRateActiveChanged: bridge.setRateMonitorActive(rateActive)

    Toast {
        id: toast
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: 94
        anchors.rightMargin: 28
        z: 200
    }

    Connections {
        target: bridge
        function onToastRequested(level, title, message) {
            toast.show(level, title, message)
        }
    }

    Popup {
        id: resetPopup
        objectName: "resetPopup"
        modal: true
        dim: true
        anchors.centerIn: Overlay.overlay
        width: 440
        padding: 22

        background: Rectangle {
            color: theme.card
            radius: 16
            border.color: Qt.rgba(1, 1, 1, 0.10)
            border.width: 1
        }

        contentItem: ColumnLayout {
            spacing: 0

            Text {
                text: "恢复默认设置"
                color: theme.text
                font.pixelSize: 19
                font.bold: true
            }
            Text {
                Layout.fillWidth: true
                Layout.topMargin: 8
                text: "会恢复默认设置并立即写入接收器，必要时自动重连。是否继续？"
                color: theme.muted
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 20
                spacing: 10
                Item { Layout.fillWidth: true }
                DeckButton {
                    text: "取消"
                    onClicked: resetPopup.close()
                }
                DeckButton {
                    text: "恢复默认值"
                    danger: true
                    onClicked: {
                        resetPopup.close()
                        bridge.resetDefaults()
                    }
                }
            }
        }

        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150 }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120 }
        }
    }

    Component.onCompleted: bridge.start()
}
