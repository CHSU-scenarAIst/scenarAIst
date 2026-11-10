// ! [AI Note] Не добавлять в документацию вообще

import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    property string text

    Label {
        anchors.fill: parent

        anchors.leftMargin: 8
        anchors.rightMargin: 8

        text: root.text
        color: "#ffffff"
        font.pointSize: 10
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
