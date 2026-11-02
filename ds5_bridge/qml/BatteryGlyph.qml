import QtQuick

Item {
    id: root
    property int percent: 100
    property color tint: theme.green
    property bool charging: false
    width: 22
    height: 12

    Rectangle {
        x: 0.6
        y: 1.6
        width: 17
        height: 8.8
        radius: 2
        color: "transparent"
        border.color: root.percent >= 0 ? root.tint : theme.muted2
        border.width: 1.2
    }

    Rectangle {
        x: 18.4
        y: 4.2
        width: 2.2
        height: 3.6
        radius: 0.8
        color: root.percent >= 0 ? root.tint : theme.muted2
    }

    Rectangle {
        visible: root.percent >= 0
        x: 2
        y: 3
        width: 14 * Math.max(0, Math.min(100, root.percent)) / 100
        height: 6
        radius: 1
        color: root.tint
        opacity: root.charging ? 0.55 : 1
        Behavior on width { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
    }

    // Lightning bolt while charging.
    Canvas {
        visible: root.charging
        x: 4
        y: 0
        width: 10
        height: 12
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.fillStyle = theme.text
            ctx.beginPath()
            ctx.moveTo(6.2, 0.5)
            ctx.lineTo(1.5, 6.6)
            ctx.lineTo(4.6, 6.6)
            ctx.lineTo(3.6, 11.5)
            ctx.lineTo(8.5, 5.0)
            ctx.lineTo(5.3, 5.0)
            ctx.closePath()
            ctx.fill()
        }
    }
}
