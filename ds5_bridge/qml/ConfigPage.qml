import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    signal resetRequested()

    property bool audioOpen: true
    property bool powerOpen: false
    property bool perfOpen: false

    function kindColor(kind) {
        if (kind === "warn" || kind === "busy")
            return theme.amber
        if (kind === "ok")
            return theme.green
        return theme.muted
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 32
        anchors.rightMargin: 32
        anchors.topMargin: 24
        spacing: 0

        Flickable {
            id: flick
            objectName: "configFlick"
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: content.height + 26
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ScrollBar.vertical: DeckScrollBar {}

            ColumnLayout {
                id: content
                width: flick.width - 10
                spacing: 18

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 14

                    ColumnLayout {
                        spacing: 2
                        Text {
                            text: "配置"
                            color: theme.text
                            font.pixelSize: 30
                            font.bold: true
                            font.letterSpacing: 0.3
                        }
                        Text {
                            text: "声音、触觉和连接方式，改完一次保存"
                            color: theme.muted
                            font.pixelSize: 14
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: bridge.statusText
                        color: root.kindColor(bridge.statusKind)
                        font.pixelSize: 14
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 190
                    radius: 20
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#102033" }
                        GradientStop { position: 0.55; color: "#0C1722" }
                        GradientStop { position: 1; color: "#0B1219" }
                    }
                    border.color: "#263B50"

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 28

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            Text {
                                text: "触觉强度"
                                color: theme.accent
                                font.pixelSize: 11
                                font.bold: true
                                font.letterSpacing: 2
                            }

                            RowLayout {
                                spacing: 10
                                Text {
                                    text: bridge.gainLabel
                                    color: theme.text
                                    font.family: "Bahnschrift"
                                    font.pixelSize: 50
                                    font.bold: true
                                }
                                Rectangle {
                                    width: 54
                                    height: 24
                                    radius: 12
                                    color: Qt.rgba(0.435, 0.659, 1, 0.10)
                                    border.color: Qt.rgba(0.435, 0.659, 1, 0.22)
                                    Text {
                                        anchors.centerIn: parent
                                        text: "默认"
                                        color: theme.accent
                                        font.pixelSize: 11
                                        font.bold: true
                                    }
                                }
                            }

                            DeckSlider {
                                objectName: "hapticsSlider"
                                Layout.fillWidth: true
                                from: 100
                                to: 200
                                value: Math.round(bridge.hapticsGain * 100)
                                onValueEdited: function(value) { bridge.setValue("hapticsGain", value / 100) }
                            }

                            RowLayout {
                                spacing: 8

                                Repeater {
                                    model: [1.0, 1.2, 1.4, 1.6]
                                    delegate: Rectangle {
                                        required property var modelData
                                        readonly property bool selected: Math.abs(bridge.hapticsGain - modelData) < 0.005
                                        width: 52
                                        height: 26
                                        radius: 8
                                        color: selected ? Qt.rgba(0.435, 0.659, 1, 0.14) : Qt.rgba(1, 1, 1, 0.035)
                                        border.color: selected ? Qt.rgba(0.435, 0.659, 1, 0.30) : Qt.rgba(1, 1, 1, 0.06)
                                        Text {
                                            anchors.centerIn: parent
                                            text: Number(modelData).toFixed(1) + "×"
                                            color: parent.selected ? theme.text : theme.muted
                                            font.pixelSize: 12
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: bridge.setValue("hapticsGain", modelData)
                                        }
                                    }
                                }

                                Item { Layout.fillWidth: true }

                                Text {
                                    text: "震动和扳机反馈的整体强度"
                                    color: theme.muted
                                    font.pixelSize: 13
                                }
                            }
                        }

                        Rectangle {
                            Layout.preferredWidth: 1
                            Layout.fillHeight: true
                            color: Qt.rgba(1, 1, 1, 0.08)
                        }

                        ColumnLayout {
                            Layout.preferredWidth: 330
                            spacing: 18

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 32
                                Metric { label: "上报速度"; value: bridge.pollingLabel }
                                Metric { label: "控制器模式"; value: bridge.modeLabel }
                                Metric { label: "声音缓冲"; value: bridge.bufferLabel }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 1
                                color: Qt.rgba(1, 1, 1, 0.06)
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                Text {
                                    text: "握持手感稳定"
                                    color: theme.muted
                                    font.pixelSize: 13
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: bridge.batteryText
                                    color: theme.accent
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 18
                    Layout.alignment: Qt.AlignTop

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        spacing: 18

                        DeckCard {
                            objectName: "audioCard"
                            title: "音频与触觉"
                            subtitle: "声音和触觉反馈"
                            summary: bridge.audioSummary
                            open: root.audioOpen
                            contentHeight: 244
                            onToggleRequested: root.audioOpen = !root.audioOpen

                            Text {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40
                                text: "音量请用 Windows 音量面板调节。"
                                color: theme.muted
                                font.pixelSize: 14
                                verticalAlignment: Text.AlignVCenter
                            }

                            SettingRow {
                                objectName: "audioGainRow"
                                title: "声音增益"
                                desc: "声音偏小时调高；自动即可"
                                Stepper {
                                    value: bridge.speakerGain
                                    from: 0
                                    to: 7
                                    labels: ["自动", "1", "2", "3", "4", "5", "6", "7"]
                                    onChanged: function(value) { bridge.setValue("speakerGain", value) }
                                }
                            }

                            SettingRow {
                                title: "扳机反馈减弱"
                                desc: "反馈太强时调高；自动即可"
                                SliderField {
                                    from: 0
                                    to: 10
                                    value: bridge.triggerReduce
                                    valueText: bridge.triggerReduce === 0 ? "自动" : String(bridge.triggerReduce)
                                    onValueEdited: function(value) { bridge.setValue("triggerReduce", value) }
                                }
                            }

                            SettingRow {
                                title: "声音缓冲"
                                desc: "越小延迟越低，但可能断续"
                                SliderField {
                                    from: 16
                                    to: 127
                                    value: bridge.audioBuffer
                                    valueText: String(bridge.audioBuffer)
                                    onValueEdited: function(value) { bridge.setValue("audioBuffer", value) }
                                }
                            }
                        }

                        DeckCard {
                            title: "电源与指示灯"
                            subtitle: "省电、指示灯和音频开关"
                            summary: bridge.powerSummary
                            open: root.powerOpen
                            contentHeight: 204
                            onToggleRequested: root.powerOpen = !root.powerOpen

                            SettingRow {
                                title: "闲置自动断开"
                                desc: "关闭后手柄不会因闲置被接收器断开"
                                Stepper {
                                    value: bridge.inactiveTime
                                    from: 0
                                    to: 60
                                    zeroLabel: "关闭"
                                    suffix: " 分钟"
                                    onChanged: function(value) { bridge.setValue("inactiveTime", value) }
                                }
                            }

                            SettingRow {
                                title: "关闭指示灯"
                                desc: "关掉接收器上的灯"
                                ToggleSwitch {
                                    objectName: "ledToggle"
                                    checked: bridge.disableLed
                                    onToggled: function(on) { bridge.setValue("disableLed", on) }
                                }
                            }

                            SettingRow {
                                title: "关闭麦克风"
                                desc: "关掉手柄麦克风"
                                ToggleSwitch {
                                    objectName: "micToggle"
                                    checked: bridge.disableMic
                                    onToggled: function(on) { bridge.setValue("disableMic", on) }
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        spacing: 18

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 366
                            radius: 16
                            color: theme.card
                            border.color: theme.border

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 0

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12
                                    Rectangle {
                                        width: 4
                                        height: 20
                                        radius: 1
                                        color: theme.accent
                                    }
                                    ColumnLayout {
                                        spacing: 1
                                        Text {
                                            text: "设备"
                                            color: theme.textSoft
                                            font.pixelSize: 16
                                            font.bold: true
                                            font.letterSpacing: 0.5
                                        }
                                        Text {
                                            text: "接收器和手柄的实时状态"
                                            color: theme.muted
                                            font.pixelSize: 13
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: "刷新"
                                        color: theme.accent
                                        font.pixelSize: 13
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: bridge.refreshStatus()
                                        }
                                    }
                                }

                                Item { Layout.preferredHeight: 14 }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 18
                                    BatteryRing {
                                        diameter: 100
                                        percent: bridge.batteryPercent
                                    }
                                    ColumnLayout {
                                        spacing: 3
                                        Text {
                                            text: bridge.connected ? bridge.deviceName : "等待连接"
                                            color: theme.text
                                            font.pixelSize: 19
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            text: bridge.deviceModel
                                            color: theme.muted
                                            font.pixelSize: 13
                                        }
                                        Text {
                                            text: bridge.batteryText
                                            color: theme.accent
                                            font.pixelSize: 13
                                            font.bold: true
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                }

                                Item { Layout.preferredHeight: 12 }

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 3
                                    columnSpacing: 16
                                    rowSpacing: 12
                                    Metric { label: "固件"; value: bridge.firmware }
                                    Metric { label: "信号"; value: bridge.rssiText }
                                    Metric { label: "音频"; value: bridge.audioText }
                                    Metric { label: "USB 型号"; value: bridge.vidText }
                                    Metric { label: "配置格式"; value: bridge.configVersionText }
                                    Metric { label: "更新时间"; value: bridge.timestampText }
                                }

                                Item { Layout.fillHeight: true }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10
                                    DeckButton {
                                        text: "重连 USB"
                                        enabled: bridge.canRead
                                        onClicked: bridge.reconnectUsb()
                                    }
                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }

                        DeckCard {
                            title: "性能与兼容性"
                            subtitle: "影响电脑如何识别手柄"
                            summary: bridge.compatSummary
                            open: root.perfOpen
                            contentHeight: 272
                            onToggleRequested: root.perfOpen = !root.perfOpen

                            SettingRow {
                                title: "上报速度"
                                desc: "越高越跟手，但可能抖动"
                                Segmented {
                                    Layout.preferredWidth: 230
                                    options: ["250 Hz", "500 Hz", "实时"]
                                    currentIndex: bridge.polling
                                    onChanged: function(index) { bridge.setValue("polling", index) }
                                }
                            }

                            SettingRow {
                                title: "手柄识别方式"
                                desc: "影响电脑和官方应用识别到的型号"
                                Segmented {
                                    Layout.preferredWidth: 230
                                    options: ["DS5", "DSE", "自动"]
                                    currentIndex: bridge.mode
                                    onChanged: function(index) { bridge.setValue("mode", index) }
                                }
                            }

                            SettingRow {
                                title: "固定设备身份"
                                desc: "换 USB 口后仍认作同一手柄"
                                ToggleSwitch {
                                    objectName: "usbSnToggle"
                                    checked: bridge.usbSn
                                    onToggled: function(on) { bridge.setValue("usbSn", on) }
                                }
                            }

                            SettingRow {
                                title: "PS 键打开 Game Bar"
                                desc: "按 PS 键打开 Xbox Game Bar"
                                ToggleSwitch {
                                    objectName: "psShortcutToggle"
                                    checked: bridge.psShortcut
                                    onToggled: function(on) { bridge.setValue("psShortcut", on) }
                                }
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: 8 }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 76
            color: Qt.rgba(0.035, 0.048, 0.061, 0.96)
            border.color: Qt.rgba(1, 1, 1, 0.06)

            RowLayout {
                anchors.fill: parent
                spacing: 12

                ColumnLayout {
                    spacing: 1
                    Text {
                        text: bridge.statusText
                        color: root.kindColor(bridge.statusKind)
                        font.pixelSize: 15
                        font.bold: true
                    }
                    Text {
                        text: bridge.stateHint
                        color: theme.muted
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        Layout.maximumWidth: 540
                    }
                }

                Item { Layout.fillWidth: true }

                DeckButton {
                    text: "恢复默认值"
                    danger: true
                    enabled: bridge.canReset
                    onClicked: root.resetRequested()
                }
                DeckButton {
                    text: "重新读取"
                    enabled: bridge.canRead
                    onClicked: bridge.reload()
                }
                DeckButton {
                    text: bridge.busy ? "正在保存…" : "保存更改"
                    primary: true
                    enabled: bridge.canSave
                    onClicked: bridge.save()
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: !bridge.connected
        color: theme.bg
        z: 40

        EmptyState {
            anchors.fill: parent
            probing: bridge.probing || (!bridge.empty && !bridge.connected)
            detail: bridge.empty
                ? bridge.emptyDetail
                : bridge.probing
                    ? "正在检测接收器…"
                    : "正在连接接收器…"
            onRetry: bridge.probe()
        }
    }
}
