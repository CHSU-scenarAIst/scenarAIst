pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// TODO: проверить оформление, вынести хард-код текст на уровень выше, UUID вместо числовых индексов

Item {
    id: root

    required property string title

    signal runRequested

    ListModel {
        id: queriesModel
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 28

            color: "#f2f2f2"
            border.color: "#cccccc"
            border.width: 1

            Label {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 8
                text: root.title
                font.bold: true
                font.pointSize: 11
            }
        }

        ListView {
            id: queriesView

            Layout.fillWidth: true
            Layout.fillHeight: true

            clip: true
            model: queriesModel
            spacing: 4
            cacheBuffer: 400

            delegate: Rectangle {
                id: delegate

                required property int index
                required property string text

                width: ListView.view ? ListView.view.width : 0
                height: 34
                color: "white"
                border.color: "#cccccc"
                border.width: 1
                radius: 3

                TextField {
                    id: field

                    anchors.left: parent.left
                    anchors.right: deleteBtn.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom

                    anchors.leftMargin: 4
                    anchors.topMargin: 3
                    anchors.bottomMargin: 3

                    selectByMouse: true
                    padding: 2

                    text: delegate.text

                    onTextChanged: {
                        if (delegate.text !== text) {
                            queriesModel.setProperty(delegate.index, "text", text);
                        }
                    }
                }

                ToolButton {
                    id: deleteBtn

                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.margins: 2

                    width: 26
                    text: "\u2715"
                    ToolTip.text: "Удалить запрос"
                    ToolTip.visible: hovered

                    onClicked: root.removeAt(delegate.index)
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4

            Button {
                text: "+"
                ToolTip.text: "Добавить запрос"
                ToolTip.visible: hovered
                onClicked: root.addQuery("")
            }

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: "\u25B2 Отправить"
                ToolTip.text: "Отправить запрос / запустить конвейер (Ctrl+Space)"
                ToolTip.visible: hovered
                onClicked: root.runRequested()
            }
        }
    }

    function count() {
        return queriesModel.count;
    }

    function addQuery(text) {
        queriesModel.append({
            text: text
        });
        Qt.callLater(() => queriesView.positionViewAtEnd());
    }

    function removeAt(i) {
        if (i >= 0 && i < queriesModel.count) {
            queriesModel.remove(i);
        }
    }

    function removeAtIndices(indices) {
        const sorted = indices.slice().sort((a, b) => b - a);

        for (const index of sorted) {
            removeAt(index);
        }
    }

    function clear() {
        queriesModel.clear();
    }

    function texts() {
        const arr = [];

        for (let i = 0; i < queriesModel.count; i++) {
            arr.push(queriesModel.get(i).text);
        }

        return arr;
    }
}
