import QtQuick

Item {
    id: root
    property int percent: -1
    property int diameter: 104
    width: diameter
    height: diameter

    Behavior on percent {
        NumberAnimation { duration: 600; easing.type: Easing.OutCubic }
    }

    onPercentChanged: ring.requestPaint()

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
            var ratio = root.percent < 0 ? 0 : Math.max(0, Math.min(100, root.percent)) / 100

            ctx.lineWidth = 7
            ctx.lineCap = "round"
            ctx.strokeStyle = "#1B2A35"
            ctx.beginPath()
            ctx.arc(c, c, r, start, start + span)
            ctx.stroke()

            if (ratio > 0) {
                var grad = ctx.createLinearGradient(0, 0, width, height)
                grad.addColorStop(0, theme.accent)
                grad.addColorStop(1, theme.accent2)
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
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.percent >= 0 ? root.percent + "%" : "—"
            color: theme.text
            font.family: "Bahnschrift"
            font.pixelSize: 24
            font.bold: true
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "电量"
            color: theme.muted
            font.pixelSize: 11
        }
    }
}
