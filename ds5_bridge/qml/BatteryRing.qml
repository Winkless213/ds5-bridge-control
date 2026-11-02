import QtQuick

Item {
    id: root
    property int percent: -1
    // normal / low / charging / full / error / unknown (bridge.batteryKind)
    property string kind: "unknown"
    property string caption: "电量"
    property int diameter: 104
    // Animated copy of percent; "—" is shown from percent itself so an
    // unknown state never flashes through 0%.
    property real shown: percent < 0 ? 0 : percent
    width: diameter
    height: diameter

    readonly property color startColor: kind === "full"
        ? theme.green
        : (kind === "low" || kind === "error") ? theme.amber : theme.accent
    readonly property color endColor: kind === "full"
        ? "#7FE0B0"
        : (kind === "low" || kind === "error") ? "#F7C873" : theme.accent2

    Behavior on shown {
        NumberAnimation { duration: 600; easing.type: Easing.OutCubic }
    }

    onShownChanged: ring.requestPaint()
    onKindChanged: ring.requestPaint()

    Canvas {
        id: ring
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var c = width / 2
            var r = Math.max(1, width / 2 - 7)
            var start = -Math.PI * 0.75
            var span = Math.PI * 1.5
            var ratio = root.percent < 0 ? 0 : Math.max(0, Math.min(100, root.shown)) / 100

            ctx.lineWidth = 7
            ctx.lineCap = "round"
            ctx.strokeStyle = "#1B2A35"
            ctx.beginPath()
            ctx.arc(c, c, r, start, start + span)
            ctx.stroke()

            if (ratio > 0) {
                var grad = ctx.createLinearGradient(0, 0, width, height)
                grad.addColorStop(0, root.startColor)
                grad.addColorStop(1, root.endColor)
                ctx.strokeStyle = grad
                ctx.beginPath()
                ctx.arc(c, c, r, start, start + span * ratio)
                ctx.stroke()
            }
        }
    }

    Column {
        anchors.centerIn: parent
        spacing: -2
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 2
            Text {
                visible: root.kind === "charging"
                anchors.verticalCenter: parent.verticalCenter
                text: "⚡"
                color: theme.accent
                font.pixelSize: 15
            }
            Text {
                text: root.percent >= 0 ? Math.round(root.shown) + "%" : "—"
                color: theme.text
                font.family: "Bahnschrift"
                font.pixelSize: 24
                font.bold: true
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.caption
            color: (root.kind === "low" || root.kind === "error")
                ? theme.amber
                : root.kind === "full" ? theme.green : theme.muted
            font.pixelSize: 11
        }
    }
}
