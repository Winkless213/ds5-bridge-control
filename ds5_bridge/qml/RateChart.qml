import QtQuick

// The last 10 seconds of report rate. Both the config page's rate card and the
// device page draw the same series, so the canvas lives here rather than twice.
Item {
    id: root

    Canvas {
        id: chart
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
        function onRateChanged() { chart.requestPaint() }
    }

    // Only while sampling: when it is off, the card's own detail line already
    // says why there is no curve, and two copies of that read as a glitch.
    Text {
        anchors.centerIn: parent
        visible: bridge.reportRateSamples.length < 2 && bridge.reportRateState !== "off"
        text: "等待采样…"
        color: theme.muted2
        font.pixelSize: 12
    }
}
