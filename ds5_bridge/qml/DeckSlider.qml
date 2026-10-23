import QtQuick
import QtQuick.Controls

Slider {
    id: control
    signal valueEdited(real value)

    implicitHeight: 32

    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: control.availableWidth
        height: 6
        radius: 3
        color: "#1B2831"

        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: 3
            gradient: Gradient {
                GradientStop { position: 0; color: "#4F8CFF" }
                GradientStop { position: 1; color: theme.accent }
            }
        }
    }

    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: 18
        height: 18
        radius: 9
        color: "#F2FBFF"
        border.color: theme.accent
        border.width: 2
        scale: control.pressed ? 1.16 : 1
        Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
    }

    onMoved: control.valueEdited(value)
}
