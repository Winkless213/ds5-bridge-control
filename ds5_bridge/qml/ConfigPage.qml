import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    signal resetRequested()

    // A row's two cards fold together: one folded alone left a hole under it,
    // beside its still-open neighbour.
    property bool hapticsRowOpen: true
    property bool systemRowOpen: false

    function kindColor(kind) {
        if (kind === "warn" || kind === "busy")
            return theme.amber
        if (kind === "ok")
            return theme.green
        return theme.muted
    }

    function isChanged(name) {
        return bridge.changedKeys.indexOf(name) >= 0
    }

    function batteryColor(kind) {
        if (kind === "full")
            return theme.green
        if (kind === "low" || kind === "error")
            return theme.amber
        return theme.accent
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
                            text: "调节后马上试用，满意再保存"
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
                    objectName: "readOnlyBanner"
                    visible: bridge.connected && !bridge.writable
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? readOnlyText.implicitHeight + 28 : 0
                    radius: 14
                    color: Qt.rgba(0.961, 0.718, 0.306, 0.08)
                    border.color: Qt.rgba(0.961, 0.718, 0.306, 0.30)

                    Text {
                        id: readOnlyText
                        anchors.fill: parent
                        anchors.margins: 14
                        text: "只读模式：" + bridge.readOnlyReason
                            + "下面显示的数值按 v0.7.2 格式解读，可能不准确。"
                        color: theme.amber
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "触觉反馈"
                        color: theme.text
                        font.pixelSize: 17
                        font.bold: true
                    }

                    Item { Layout.fillWidth: true }

                    // Which of the two folds below a game is driving right now.
                    Rectangle {
                        visible: bridge.vibSupported
                        implicitWidth: 7
                        implicitHeight: 7
                        radius: 3.5
                        color: bridge.vibPathKind === "rumble" ? theme.amber
                            : bridge.vibPathKind === "haptics" ? theme.accent
                            : theme.muted2
                    }
                    Text {
                        visible: bridge.vibSupported
                        text: "当前：" + bridge.vibPathText
                        color: bridge.vibPathKind === "rumble" ? theme.amber
                            : bridge.vibPathKind === "haptics" ? theme.accent
                            : theme.muted
                        font.pixelSize: 12
                        font.bold: bridge.vibPathKind !== "idle"
                    }
                }

                // A game drives one vibration system or the other, so each gets
                // a card built the same way: strength, the one setting only that
                // path has, and a test to feel it.
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 18

                    DeckCard {
                        objectName: "hdCard"
                        Layout.fillHeight: true
                        title: "HD 触觉"
                        subtitle: "原生适配的游戏"
                        summary: open ? "" : bridge.gainLabel + " · 增益 " + bridge.speakerGainLabel
                        open: root.hapticsRowOpen
                        enabled: bridge.writable
                        onToggleRequested: root.hapticsRowOpen = !root.hapticsRowOpen

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 6
                            Layout.bottomMargin: 10
                            spacing: 4

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                Text {
                                    text: bridge.gainLabel
                                    color: theme.text
                                    font.family: "Bahnschrift"
                                    font.pixelSize: 50
                                    font.bold: true
                                    HoverHandler { id: gainHover }
                                    ToolTip.visible: gainHover.hovered
                                    ToolTip.delay: 400
                                    ToolTip.text: bridge.gainIsDefault
                                        ? "只放大原生适配游戏的触觉波形"
                                        : "弱震动变明显，强震动平滑收顶不发硬"
                                }
                                Rectangle {
                                    objectName: "gainBadge"
                                    readonly property bool unsaved: root.isChanged("hapticsGain")
                                    visible: unsaved || bridge.gainIsDefault
                                    // The RowLayout sets width itself, so ask for a
                                    // size instead of binding one it would overwrite.
                                    implicitWidth: badgeText.implicitWidth + 22
                                    implicitHeight: 24
                                    radius: 12
                                    color: unsaved ? Qt.rgba(0.961, 0.718, 0.306, 0.12) : Qt.rgba(0.435, 0.659, 1, 0.10)
                                    border.color: unsaved ? Qt.rgba(0.961, 0.718, 0.306, 0.35) : Qt.rgba(0.435, 0.659, 1, 0.22)
                                    Text {
                                        id: badgeText
                                        anchors.centerIn: parent
                                        text: parent.unsaved ? "试用中 · 未保存" : "默认"
                                        color: parent.unsaved ? theme.amber : theme.accent
                                        font.pixelSize: 11
                                        font.bold: true
                                    }
                                }
                                Item { Layout.fillWidth: true }
                                DeckButton {
                                    objectName: "heroTestHapticsButton"
                                    text: "试一下"
                                    enabled: bridge.canRead
                                    onClicked: bridge.testHaptics()
                                }
                            }

                            DeckSlider {
                                objectName: "hapticsSlider"
                                Layout.fillWidth: true
                                from: 100
                                to: 200
                                stepSize: 5
                                value: Math.round(bridge.hapticsGain * 100)
                                onValueEdited: function(value) { bridge.setValue("hapticsGain", value / 100) }
                            }

                            RowLayout {
                                spacing: 8

                                Repeater {
                                    model: [1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
                                    delegate: Rectangle {
                                        required property var modelData
                                        readonly property bool selected: Math.abs(bridge.hapticsGain - modelData) < 0.005
                                        width: 48
                                        height: 26
                                        radius: 8
                                        color: selected ? Qt.rgba(0.435, 0.659, 1, 0.14) : chipMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.035)
                                        border.color: selected ? Qt.rgba(0.435, 0.659, 1, 0.30) : Qt.rgba(1, 1, 1, 0.06)
                                        Text {
                                            anchors.centerIn: parent
                                            text: Number(modelData).toFixed(1) + "×"
                                            color: parent.selected ? theme.text : theme.muted
                                            font.pixelSize: 12
                                        }
                                        MouseArea {
                                            id: chipMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: bridge.setValue("hapticsGain", modelData)
                                        }
                                    }
                                }

                                Item { Layout.fillWidth: true }
                            }

                        }

                        SettingRow {
                            objectName: "audioGainRow"
                            title: "声音增益"
                            field: "speakerGain"
                            changed: root.isChanged("speakerGain")
                            desc: changed && bridge.speakerGain === 0
                                ? "改回自动要等手柄重连才生效"
                                : "震感偏弱时调高，太高会破音"
                            Stepper {
                                value: bridge.speakerGain
                                from: 0
                                to: 7
                                labels: ["自动", "1", "2", "3", "4", "5", "6", "7"]
                                onChanged: function(value) { bridge.setValue("speakerGain", value) }
                            }
                        }
                    }

                    DeckCard {
                        objectName: "rumbleCard"
                        visible: bridge.vibSupported
                        Layout.fillHeight: true
                        title: "普通震动"
                        subtitle: "XInput / 模拟器"
                        accent: theme.amber
                        summary: open ? "" : bridge.rumbleGainLabel + (bridge.legacyRumble ? " · 老式换算" : "")
                        open: root.hapticsRowOpen
                        enabled: bridge.writable
                        onToggleRequested: root.hapticsRowOpen = !root.hapticsRowOpen

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 6
                            Layout.bottomMargin: 10
                            spacing: 4

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                Text {
                                    text: bridge.rumbleGainLabel
                                    color: theme.text
                                    font.family: "Bahnschrift"
                                    font.pixelSize: 50
                                    font.bold: true
                                    HoverHandler { id: rumbleHover }
                                    ToolTip.visible: rumbleHover.hovered
                                    ToolTip.delay: 400
                                    ToolTip.text: "大多数 PC 游戏走这条；满值的强震动加不上去"
                                }
                                Rectangle {
                                    objectName: "rumbleBadge"
                                    readonly property bool unsaved: root.isChanged("rumbleGain")
                                    visible: unsaved || bridge.rumbleGain === 100
                                    implicitWidth: rumbleBadgeText.implicitWidth + 22
                                    implicitHeight: 24
                                    radius: 12
                                    color: unsaved ? Qt.rgba(0.961, 0.718, 0.306, 0.12) : Qt.rgba(1, 1, 1, 0.06)
                                    border.color: unsaved ? Qt.rgba(0.961, 0.718, 0.306, 0.35) : Qt.rgba(1, 1, 1, 0.12)
                                    Text {
                                        id: rumbleBadgeText
                                        anchors.centerIn: parent
                                        text: parent.unsaved ? "试用中 · 未保存" : "原始强度"
                                        color: parent.unsaved ? theme.amber : theme.muted
                                        font.pixelSize: 11
                                        font.bold: true
                                    }
                                }
                                Item { Layout.fillWidth: true }
                                DeckButton {
                                    objectName: "heroTestRumbleButton"
                                    text: "试一下"
                                    enabled: bridge.canRead
                                    onClicked: bridge.testRumble()
                                }
                            }

                            DeckSlider {
                                objectName: "heroRumbleSlider"
                                Layout.fillWidth: true
                                from: 10
                                to: 400
                                stepSize: 10
                                value: bridge.rumbleGain
                                onValueEdited: function(value) { bridge.setValue("rumbleGain", value) }
                            }

                            RowLayout {
                                spacing: 8

                                Repeater {
                                    model: [100, 150, 200, 300]
                                    delegate: Rectangle {
                                        required property var modelData
                                        readonly property bool selected: bridge.rumbleGain === modelData
                                        implicitWidth: 48
                                        implicitHeight: 26
                                        radius: 8
                                        color: selected ? Qt.rgba(0.961, 0.718, 0.306, 0.14)
                                            : rumbleChipMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.06)
                                            : Qt.rgba(1, 1, 1, 0.035)
                                        border.color: selected ? Qt.rgba(0.961, 0.718, 0.306, 0.30) : Qt.rgba(1, 1, 1, 0.06)
                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData + "%"
                                            color: parent.selected ? theme.text : theme.muted
                                            font.pixelSize: 12
                                        }
                                        MouseArea {
                                            id: rumbleChipMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: bridge.setValue("rumbleGain", modelData)
                                        }
                                    }
                                }

                                Item { Layout.fillWidth: true }
                            }
                        }

                        SettingRow {
                            title: "老式换算"
                            changed: root.isChanged("legacyRumble")
                            ToggleSwitch {
                                objectName: "legacyRumbleToggle"
                                checked: bridge.legacyRumble
                                onToggled: function(on) { bridge.setValue("legacyRumble", on) }
                            }
                        }
                    }
                }

                // Live measurement, not a setting, so it never folds: it spans
                // the page between the two folding rows, with the speed that
                // drives it alongside the number it produces.
                Rectangle {
                    objectName: "rateCard"
                    Layout.fillWidth: true
                    Layout.preferredHeight: rateBody.implicitHeight + 40
                    radius: 16
                    color: theme.card2
                    border.width: 1
                    border.color: theme.border

                    ColumnLayout {
                        id: rateBody
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 10

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
                                    text: "输入回报率"
                                    color: theme.textSoft
                                    font.pixelSize: 16
                                    font.bold: true
                                    font.letterSpacing: 0.5
                                }
                                Text {
                                    text: "电脑实际收到的输入报文"
                                    color: theme.muted
                                    font.pixelSize: 13
                                }
                            }

                            Item { Layout.fillWidth: true }

                            RowLayout {
                                spacing: 4
                                Text {
                                    objectName: "reportRateValue"
                                    text: bridge.reportRateValue
                                    color: theme.text
                                    font.family: "Bahnschrift"
                                    font.pixelSize: 34
                                    font.bold: true
                                }
                                Text {
                                    text: "Hz"
                                    color: theme.muted
                                    font.pixelSize: 13
                                    Layout.alignment: Qt.AlignBottom
                                    Layout.bottomMargin: 6
                                }
                            }

                            Rectangle {
                                implicitWidth: rateStateText.implicitWidth + 18
                                implicitHeight: 24
                                radius: 12
                                color: bridge.reportRateStateKind === "warn"
                                    ? Qt.rgba(0.961, 0.718, 0.306, 0.10)
                                    : bridge.reportRateStateKind === "ok"
                                        ? Qt.rgba(0.435, 0.659, 1, 0.10)
                                        : Qt.rgba(1, 1, 1, 0.04)
                                border.color: bridge.reportRateStateKind === "warn"
                                    ? Qt.rgba(0.961, 0.718, 0.306, 0.24)
                                    : bridge.reportRateStateKind === "ok"
                                        ? Qt.rgba(0.435, 0.659, 1, 0.24)
                                        : Qt.rgba(1, 1, 1, 0.08)
                                Text {
                                    id: rateStateText
                                    anchors.centerIn: parent
                                    text: bridge.reportRateStateLabel
                                    color: bridge.reportRateStateKind === "warn"
                                        ? theme.amber
                                        : bridge.reportRateStateKind === "ok"
                                            ? theme.accent
                                            : theme.muted
                                    font.pixelSize: 12
                                    font.bold: true
                                }
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: bridge.reportRateDetail
                            color: theme.muted2
                            font.pixelSize: 12
                        }

                        RateChart {
                            objectName: "rateChart"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                        }

                        SettingRow {
                            objectName: "pollingRow"
                            title: "上报速度"
                            field: "polling"
                            changed: root.isChanged("polling")
                            desc: "日常建议 500 Hz"
                            enabled: bridge.writable
                            Segmented {
                                Layout.preferredWidth: 230
                                options: ["250 Hz", "500 Hz", "实时"]
                                currentIndex: bridge.polling
                                onChanged: function(index) { bridge.setValue("polling", index) }
                            }
                        }
                    }
                }

                // Paired in one row so neither column ends far above the other.
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 18

                    DeckCard {
                        objectName: "powerCard"
                        Layout.fillHeight: true
                        title: "电源与指示灯"
                        subtitle: "省电、指示灯、麦克风和扬声器"
                        summary: bridge.powerSummary
                        open: root.systemRowOpen
                        enabled: bridge.writable
                        onToggleRequested: root.systemRowOpen = !root.systemRowOpen

                        SettingRow {
                            title: "闲置自动断开"
                            field: "inactiveTime"
                            changed: root.isChanged("inactiveTime")
                            desc: bridge.idleDropHint !== ""
                                ? bridge.idleDropHint
                                : changed ? "保存后才生效（不参与试用）" : "手柄多久不动就断开省电；关闭则不断开"
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
                            title: "关闭手柄声音"
                            field: "disableSpeaker"
                            changed: root.isChanged("disableSpeaker")
                            desc: "扬声器和耳机孔都不出声"
                            ToggleSwitch {
                                objectName: "speakerToggle"
                                checked: bridge.disableSpeaker
                                onToggled: function(on) { bridge.setValue("disableSpeaker", on) }
                            }
                        }
                        SettingRow {
                            title: "关闭指示灯"
                            field: "disableLed"
                            changed: root.isChanged("disableLed")
                            desc: "低电量闪烁不受影响"
                            ToggleSwitch {
                                objectName: "ledToggle"
                                checked: bridge.disableLed
                                onToggled: function(on) { bridge.setValue("disableLed", on) }
                            }
                        }

                        SettingRow {
                            title: "关闭麦克风"
                            field: "disableMic"
                            changed: root.isChanged("disableMic")
                            desc: "关掉手柄麦克风"
                            ToggleSwitch {
                                objectName: "micToggle"
                                checked: bridge.disableMic
                                onToggled: function(on) { bridge.setValue("disableMic", on) }
                            }
                        }
                    }

                    DeckCard {
                        objectName: "perfCard"
                        Layout.fillHeight: true
                        title: "性能与兼容性"
                        subtitle: "扳机、声音缓冲和识别方式"
                        summary: bridge.compatSummary
                        open: root.systemRowOpen
                        enabled: bridge.writable
                        onToggleRequested: root.systemRowOpen = !root.systemRowOpen

                        SettingRow {
                            objectName: "triggerReduceRow"
                            title: "扳机反馈减弱"
                            field: "triggerReduce"
                            changed: root.isChanged("triggerReduce")
                            desc: changed && bridge.triggerReduce === 0
                                ? "改回自动要等手柄重连才生效"
                                : "阻力太强时调高"
                            SliderField {
                                from: 0
                                to: 10
                                value: bridge.triggerReduce
                                valueText: bridge.triggerReduce === 0 ? "自动" : String(bridge.triggerReduce)
                                onValueEdited: function(value) { bridge.setValue("triggerReduce", value) }
                            }
                        }

                        SettingRow {
                            objectName: "audioBufferRow"
                            title: "声音缓冲"
                            field: "audioBuffer"
                            changed: root.isChanged("audioBuffer")
                            desc: "越小延迟越低，但可能断续"
                            SliderField {
                                from: 16
                                to: 127
                                value: bridge.audioBuffer
                                valueText: String(bridge.audioBuffer)
                                onValueEdited: function(value) { bridge.setValue("audioBuffer", value) }
                            }
                        }

                        SettingRow {
                            title: "手柄识别方式"
                            changed: root.isChanged("mode")
                            desc: "电脑识别到的型号"
                            Segmented {
                                Layout.preferredWidth: 230
                                options: ["DS5", "DSE", "自动"]
                                currentIndex: bridge.mode
                                onChanged: function(index) { bridge.setValue("mode", index) }
                            }
                        }

                        SettingRow {
                            title: "固定设备身份"
                            changed: root.isChanged("usbSn")
                            desc: "换 USB 口后仍认作同一手柄"
                            ToggleSwitch {
                                objectName: "usbSnToggle"
                                checked: bridge.usbSn
                                onToggled: function(on) { bridge.setValue("usbSn", on) }
                            }
                        }

                        SettingRow {
                            title: "PS 键打开 Game Bar"
                            changed: root.isChanged("psShortcut")
                            desc: "按 PS 键打开 Xbox Game Bar"
                            ToggleSwitch {
                                objectName: "psShortcutToggle"
                                checked: bridge.psShortcut
                                onToggled: function(on) { bridge.setValue("psShortcut", on) }
                            }
                        }
                    }
                }

                // Status only, so it comes last and spans the page.
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
                                kind: bridge.batteryKind
                                caption: bridge.batteryLabel
                            }
                            ColumnLayout {
                                spacing: 3
                                Layout.fillWidth: true
                                Text {
                                    Layout.fillWidth: true
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
                                    color: root.batteryColor(bridge.batteryKind)
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                            }
                        }

                        Item { Layout.preferredHeight: 12 }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 4
                            columnSpacing: 16
                            rowSpacing: 12
                            Metric { label: "固件"; value: bridge.firmware }
                            Metric { label: "信号"; value: bridge.rssiText }
                            Metric { label: "音频活动"; value: bridge.audioText }
                            Metric {
                                objectName: "vibPathMetric"
                                label: "震动通路"
                                value: bridge.vibPathText
                                accent: bridge.vibPathKind === "rumble" ? theme.amber
                                    : bridge.vibPathKind === "haptics" ? theme.accent
                                    : "transparent"
                            }
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
                            Text {
                                objectName: "vibPathHint"
                                text: bridge.vibPathHint
                                color: bridge.vibPathKind === "rumble" ? theme.amber
                                    : bridge.vibPathKind === "haptics" ? theme.accent
                                    : theme.muted2
                                font.pixelSize: 12
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
                        Layout.maximumWidth: 560
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
                    objectName: "revertButton"
                    text: bridge.dirty || bridge.liveActive ? "撤销更改" : "重新读取"
                    enabled: bridge.dirty || bridge.liveActive ? bridge.canRevert : bridge.canRead
                    onClicked: bridge.dirty || bridge.liveActive ? bridge.revert() : bridge.reload()
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
