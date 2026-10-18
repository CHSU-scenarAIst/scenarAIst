import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "./"

Item {
    id: root

    required property var handler

    property string text

    signal copyRequested

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
                text: Localization.tr("Response.Title")
                font.bold: true
                font.pointSize: 11
            }

            ToolButton {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 4

                text: Localization.tr("Query.Copy.Text")
                ToolTip.text: Localization.tr("Query.Copy.Tip")
                ToolTip.visible: hovered

                onClicked: root.copyRequested()
            }
        }

        ScrollView {
            id: scroll

            Layout.fillWidth: true
            Layout.fillHeight: true

            clip: true

            TextArea {
                id: answerArea

                text: root.text
                readOnly: true
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                persistentSelection: true
                padding: 8

                background: Rectangle {
                    color: "#ffffff"
                    border.color: "#cccccc"
                    border.width: 1
                }
            }
        }
    }

    function scrollBy(delta) {
        const flickable = scroll.contentItem as Flickable;
        if (!flickable) {
            return;
        }
        flickable.contentY = Math.max(0, Math.min(flickable.contentHeight - flickable.height, flickable.contentY + delta));
    }
}
