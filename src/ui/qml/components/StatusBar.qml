// ! """Компонент отображения строки состояния работы приложения."""

import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    property string text // * Состояние работы приложения.

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
