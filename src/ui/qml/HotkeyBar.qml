import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    required property var bindings

    RowLayout {
        anchors.fill: parent

        Repeater {
            model: root.bindings

            RowLayout {
                required property var modelData

                Text {
                    text: parent.modelData?.key ?? ""
                    color: "white"
                    font.bold: true
                    font.pointSize: 10
                }

                Text {
                    text: parent.modelData?.label ?? ""
                    color: "#cccccc"
                    font.pointSize: 10
                }
            }
        }
    }
}
