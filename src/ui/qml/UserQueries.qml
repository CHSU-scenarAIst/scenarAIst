pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

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

                    onClicked: root.removeByUids(delegate.index)
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

    function count() {
        return queriesModel.count;
    }

    // TODO вместо uuid режим + дата и время (без милисекунд) + хэшсумма из 6 символов
    function _newUuid() {
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
            const r = Math.random() * 16 | 0;
            const v = c === "x" ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    function addQuery(text) {
        queriesModel.append({
            uid: _newUuid(),
            text: text
        });
        Qt.callLater(() => queriesView.positionViewAtEnd());
    }

    function removeByUids(uids) {
        const uidSet = new Set(uids.map(String));

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
    }

    function clear() {
        queriesModel.clear();
    }

    function texts() {
        /// вам
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
}
