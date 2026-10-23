import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property bool advancedOpen: false

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

                RowLayout {
                    Layout.fillWidth: true

                    ColumnLayout {
                        spacing: 2
                        Text {
                            text: "设备"
                            color: theme.text
                            font.pixelSize: 30
                            font.bold: true
                            font.letterSpacing: 0.3
                        }
                        Text {
                            text: "连接状态、电量、固件版本与实时信号"
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
                    Layout.preferredHeight: 330
                    radius: 20
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#102033" }
                        GradientStop { position: 0.55; color: "#0C1722" }
                        GradientStop { position: 1; color: "#0B1219" }
                    }
                    border.color: "#263B50"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 0

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 22

                            BatteryRing {
                                diameter: 116
                                percent: bridge.batteryPercent
                            }

                            ColumnLayout {
                                spacing: 3
                                Text {
                                    text: bridge.connected ? bridge.deviceName : "等待连接"
                                    color: theme.text
                                    font.pixelSize: 26
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: bridge.deviceModel
                                    color: theme.muted
                                    font.pixelSize: 14
                                }
                                Text {
                                    text: bridge.batteryText
                                    color: theme.accent
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                            }

                            Item { Layout.fillWidth: true }

                            Text {
                                text: "只读概览"
                                color: theme.muted2
                                font.pixelSize: 12
                            }
                        }

                        Item { Layout.preferredHeight: 18 }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 3
                            columnSpacing: 24
                            rowSpacing: 14

                            Metric { label: "固件版本"; value: bridge.firmware }
                            Metric { label: "信号"; value: bridge.rssiText }
                            Metric { label: "音频输出"; value: bridge.audioText }
                            Metric { label: "控制器模式"; value: bridge.deviceModeLabel }
                            Metric { label: "USB 型号"; value: bridge.vidText }
                            Metric { label: "配置格式"; value: bridge.configVersionText }
                            Metric { label: "连接接口"; value: bridge.interfaceText }
                            Metric { label: "更新时间"; value: bridge.timestampText }
                            Metric { label: "电量"; value: bridge.batteryText }
                        }
                    }
                }

                Rectangle {
                    objectName: "reportRateCard"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 204
                    radius: 16
                    color: theme.card
                    border.color: theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            Rectangle {
                                width: 4
                                height: 18
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

                            Rectangle {
                                implicitWidth: rateState.implicitWidth + 18
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
                                    id: rateState
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

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 16

                            RowLayout {
                                spacing: 4
                                Text {
                                    objectName: "reportRateValue"
                                    text: bridge.reportRateValue
                                    color: theme.text
                                    font.family: "Bahnschrift"
                                    font.pixelSize: 40
                                    font.bold: true
                                }
                                Text {
                                    text: "Hz"
                                    color: theme.muted
                                    font.pixelSize: 13
                                    Layout.alignment: Qt.AlignBottom
                                    Layout.bottomMargin: 7
                                }
                            }

                            ColumnLayout {
                                spacing: 2
                                Text {
                                    text: bridge.reportRateDetail
                                    color: theme.textSoft
                                    font.pixelSize: 13
                                }
                                Text {
                                    text: "2 秒窗口 · 最近 10 秒 · 仅统计 0x01 输入报文"
                                    color: theme.muted2
                                    font.pixelSize: 12
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 46

                            Canvas {
                                id: rateChart
                                anchors.fill: parent
                                onPaint: {
                                    var ctx = getContext("2d")
                                    ctx.clearRect(0, 0, width, height)
                                    var values = bridge.reportRateSamples
                                    if (values.length < 2)
                                        return

                                    var lo = values[0]
                                    var hi = values[0]
                                    for (var i = 1; i < values.length; i++) {
                                        lo = Math.min(lo, values[i])
                                        hi = Math.max(hi, values[i])
                                    }
                                    var pad = Math.max(10, (hi - lo) * 0.25)
                                    lo = Math.max(0, lo - pad)
                                    hi = hi + pad

                                    var chartWidth = width
                                    var chartHeight = height - 2
                                    ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.06)
                                    ctx.lineWidth = 1
                                    ctx.beginPath()
                                    ctx.moveTo(0, chartHeight)
                                    ctx.lineTo(chartWidth, chartHeight)
                                    ctx.stroke()

                                    ctx.strokeStyle = bridge.reportRateStateKind === "warn"
                                        ? theme.amber
                                        : theme.accent
                                    ctx.lineWidth = 2
                                    ctx.lineJoin = "round"
                                    ctx.lineCap = "round"
                                    ctx.beginPath()
                                    for (var j = 0; j < values.length; j++) {
                                        var x = chartWidth * j / (values.length - 1)
                                        var y = chartHeight
                                            - (values[j] - lo) / Math.max(1, hi - lo) * chartHeight
                                        if (j === 0)
                                            ctx.moveTo(x, y)
                                        else
                                            ctx.lineTo(x, y)
                                    }
                                    ctx.stroke()

                                    var lastX = chartWidth
                                    var lastY = chartHeight
                                        - (values[values.length - 1] - lo) / Math.max(1, hi - lo) * chartHeight
                                    ctx.fillStyle = bridge.reportRateStateKind === "warn"
                                        ? theme.amber
                                        : theme.accent
                                    ctx.beginPath()
                                    ctx.arc(lastX - 2, lastY, 2.5, 0, Math.PI * 2)
                                    ctx.fill()
                                }
                            }

                            Connections {
                                target: bridge
                                function onRateChanged() { rateChart.requestPaint() }
                            }

                            Text {
                                anchors.centerIn: parent
                                visible: bridge.reportRateSamples.length < 2
                                text: "等待采样…"
                                color: theme.muted2
                                font.pixelSize: 12
                            }
                        }
                    }
                }

                DeckCard {
                    title: "高级信息"
                    subtitle: "排查问题时使用；只读"
                    summary: "19 字节"
                    open: root.advancedOpen
                    contentHeight: 96
                    onToggleRequested: root.advancedOpen = !root.advancedOpen

                    Text {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 76
                        text: bridge.rawText
                        color: theme.textSoft
                        font.family: theme.mono
                        font.pixelSize: 13
                        wrapMode: Text.WrapAnywhere
                        verticalAlignment: Text.AlignVCenter
                        padding: 12
                        Rectangle {
                            z: -1
                            anchors.fill: parent
                            color: "#0A1016"
                            radius: 10
                            border.color: "#17232C"
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    DeckButton {
                        text: "刷新状态"
                        enabled: bridge.canRead
                        onClicked: bridge.refreshStatus()
                    }
                    DeckButton {
                        text: "重连 USB"
                        enabled: bridge.canRead
                        onClicked: bridge.reconnectUsb()
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "重连会让手柄短暂掉线后自动恢复"
                        color: theme.muted2
                        font.pixelSize: 12
                    }
                }

                Item { Layout.preferredHeight: 6 }
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
