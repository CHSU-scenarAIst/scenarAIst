// ! """СтрокаСтатуса. Компонент отображения строки состояния работы приложения."""

import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    property string currentMode // * Текущий режим работы программы.
    property string queryCount // * Текущее число запросов.

    Label {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        color: "#ffffff"
        font.pointSize: 10
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        text: {
            const mode = Localization.tr("Hotkeys.Mode") + ": " + Localization.tr(root.currentMode);
            const query = Localization.tr("Query.Count") + ": " + root.queryCount;
            return mode + "   |   " + query;
        }
    }
}
