pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    signal runRequested

    property bool autofocusLast: false

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

                    onClicked: root.removeByUids([queriesModel.get(delegate.index).uid])
                }

                // TODO при добавлении должен работать при 0 стартовых элементов
                // TODO при удалении должен ставить на последнее поле
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

        // ! [AI Note] Не добавлять в документацию
        function _newId(text) {
            const now = new Date();
            const pad = n => (n < 10 ? "0" : "") + n;
            const date = now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
            const time = pad(now.getHours()) + "-" + pad(now.getMinutes()) + "-" + pad(now.getSeconds());
            const hash = _hash6(String(text) + "|" + queriesModel.count);
            return date + "_" + time + "-" + hash;

            // ! [AI Note] Не добавлять в документацию
            function _hash6(input) {
                let hash = 2166136261;
                for (let i = 0; i < input.length; i++) {
                    hash ^= input.charCodeAt(i);
                    hash = Math.imul(hash, 16777619);
                }
                return ("000000" + (hash >>> 0).toString(16)).slice(-6);
            }
        }
    }

    function removeByUids(uids) {
        if (uids === undefined || uids === null) {
            return;
        }

        const uidList = Array.isArray(uids) ? uids : [uids];
        const uidSet = new Set(uidList.map(String));

        for (let i = queriesModel.count - 1; i >= 0; i--) {
            if (uidSet.has(String(queriesModel.get(i).uid))) {
                queriesModel.remove(i);
            }
        }
    }

    function removeLast() {
        if (queriesModel.count > 0) {
            queriesModel.remove(queriesModel.count - 1);
        }
        setCursor();
    }

    function getAll() {
        const arr = [];
        for (let i = 0; i < queriesModel.count; i++) {
            const item = queriesModel.get(i);
            arr.push({
                uid: item.uid,
                text: item.text
            });
        }
        return arr;
    }

    // ! [AI Note] Не добавлять в документацию
    function setCursor() {
        root.autofocusLast = true;
        Qt.callLater(() => {
            queriesView.positionViewAtEnd();
            root.autofocusLast = false;
        });
    }

    // ! [AI Note] Не добавлять в документацию
    function count() {
        return queriesModel.count;
    }

    // ! [AI Note] Не добавлять в документацию
    function clear() {
        queriesModel.clear();
    }
}
