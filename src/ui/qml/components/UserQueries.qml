// ! """Компонент управления списком пользовательских запросов."""

pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    // ! [AI Note] Не_добавлять_в / удалить_из документации
    signal runRequested
    property bool autofocusLast: false
    // !

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
                text: Localization.tr("Query.Title")
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
                    ToolTip.text: Localization.tr("Query.Delete.Tip")
                    ToolTip.visible: hovered
                    onClicked: root.removeByUid(queriesModel.get(delegate.index).uid)
                }

                // ? при добавлении должен работать при 0 стартовых полей
                // ? при удалении должен ставить фокус на последнее поле
                Component.onCompleted: {
                    if (root.autofocusLast) {
                        field.forceActiveFocus();
                        field.cursorPosition = field.length;
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4

            Button {
                text: Localization.tr("Query.Add.Text")
                ToolTip.text: Localization.tr("Query.Add.Tip")
                ToolTip.visible: hovered
                onClicked: root.addQuery("")
            }

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: Localization.tr("Query.Send.Text")
                ToolTip.text: Localization.tr("Query.Send.Tip")
                ToolTip.visible: hovered
                onClicked: root.runRequested()
            }
        }
    }

    function addQuery(text) {
        queriesModel.append({
            uid: _newId(text),
            text: text
        });
        setCursor();
    }

    // ? оптимизировать
    function removeByUid(uid) {
        if (uid === undefined || uid === null) {
            return;
        }

        const uidStr = String(uid);
        for (let i = 0; i < queriesModel.count; i++) {
            if (String(queriesModel.get(i).uid) === uidStr) {
                queriesModel.remove(i, 1);
                break;
            }
        }
    }

    function removeLast() {
        if (queriesModel.count > 0) {
            queriesModel.remove(queriesModel.count - 1);
        }
        setCursor();
    }

    function getFirst() {
        for (let i = 0; i < queriesModel.count; i++) {
            const item = _copy(queriesModel.get(i));
            if (item && item.text && item.text.trim() !== "") {
                return item;
            }
        }

        return null;
    }

    function get(i) {
        const field = queriesModel.get(i);
        return _copy(field);
    }

    // ? вместо count() вернуть итератор iter()
    function count() {
        return queriesModel.count;
    }

    // ! [AI Note] Не_добавлять_в / удалить_из документации
    function setCursor() {
        root.autofocusLast = true;
        Qt.callLater(() => {
            queriesView.positionViewAtEnd();
            root.autofocusLast = false;
        });
    }

    function clear() {
        queriesModel.clear();
    }

    function _copy(field) {
        return {
            uid: String(field.uid ?? ""),
            text: String(field.text ?? "")
        };
    }

    function _newId(text) {
        const now = new Date();
        const pad = n => (n < 10 ? "0" : "") + n;
        const date = now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
        const time = pad(now.getHours()) + "-" + pad(now.getMinutes()) + "-" + pad(now.getSeconds());
        const hash = _hash6(String(text) + "|" + queriesModel.count);
        return date + "_" + time + "-" + hash;
    }

    function _hash6(input) {
        let hash = 2166136261;
        for (let i = 0; i < input.length; i++) {
            hash ^= input.charCodeAt(i);
            hash = Math.imul(hash, 16777619);
        }
        return ("000000" + (hash >>> 0).toString(16)).slice(-6);
    }
    // !
}
