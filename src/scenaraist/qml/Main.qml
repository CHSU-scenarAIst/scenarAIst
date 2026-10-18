import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Window

import "./components"

ApplicationWindow {
    id: root

    title: root.handler.translate("Main.title", root.handler.language)
    visible: true
    width: 1200
    height: 700
    minimumWidth: 900
    minimumHeight: 500
    color: "#e8e8e8"

    property var handler: handlerBackend // qmllint disable unqualified

    ColumnLayout {
        anchors.fill: parent

        StatusBar {
            id: statusBar
            Layout.fillWidth: true
            implicitHeight: 30
            color: "#000000"
        }

        // TODO убрать знание о поддерживаемых языках
        ComboBox {
            Layout.alignment: Qt.AlignRight
            model: ["English", "Русский"]
            currentIndex: 0
            onActivated: function (index) {
                root.handler.setLanguage(["en", "ru"][index]);
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            LlmResponse {
                id: llmResponse
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: root.handler.translate("Response.title", root.handler.language)
                text: root.handler.currentResponse
                onCopyRequested: root.handler.copyToClipboard(root.handler.currentResponse)
            }

            UserQueries {
                id: userQueries
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: root.handler.translate("Query.title", root.handler.language)
                onRunRequested: root.runPipeline()
                handler: handler
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: root.handler.translate("Clear.btn", root.handler.language)
                ToolTip.text: root.handler.translate("Clear.tip", root.handler.language)
                ToolTip.visible: hovered
                onClicked: {
                    root.handler.clearAll();
                    userQueries.clear();
                    root.refreshStatus();
                }
            }
        }

        HotkeyBar {
            id: hotkeyBar
            Layout.fillWidth: true
            implicitHeight: 30
            color: "#000000"
            bindings: []
        }
    }

    Shortcut {
        sequence: "Ctrl+Space"
        context: Qt.ApplicationShortcut
        onActivated: root.runPipeline()
    }

    Shortcut {
        sequence: "Ctrl+V"
        context: Qt.ApplicationShortcut
        onActivated: root.pasteFromClipboard()
    }

    Shortcut {
        sequence: "Ctrl+M"
        context: Qt.ApplicationShortcut
        onActivated: root.handler.cycleMode()
    }

    Shortcut {
        sequence: "Ctrl+S"
        context: Qt.ApplicationShortcut
        onActivated: saveDialog.open()
    }

    Shortcut {
        sequence: "Up"
        context: Qt.ApplicationShortcut
        onActivated: llmResponse.scrollBy(-24)
    }

    Shortcut {
        sequence: "Down"
        context: Qt.ApplicationShortcut
        onActivated: llmResponse.scrollBy(24)
    }

    Connections {
        target: root.handler

        function onCurrentModeChanged() {
            root.refreshStatus();
            root.refreshHotkeys();
        }

        function onQueriesProcessed(indices) {
            userQueries.removeAtIndices(indices);
            root.refreshStatus();
        }
    }

    Component.onCompleted: {
        root.refreshStatus();
        root.refreshHotkeys();
    }

    FileDialog {
        id: saveDialog
        title: root.handler.translate("Save.dialogue", root.handler.language)
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        nameFilters: ["JSON files (*.json)", "All files (*)"]

        onAccepted: {
            // TODO это работает на Windows?
            const path = selectedFile.toString().replace("file://", "");
            root.handler.saveToJson(path);
        }
    }

    function runPipeline() {
        const queries = userQueries.texts();
        if (queries.length <= 0) {
            return;
        }
        handler.runPipeline(handler.currentMode, queries);
    }

    function pasteFromClipboard() {
        const clip = handler.clipboardText();

        if (!clip) {
            return;
        }

        const focus = root.activeFocusItem;
        if (focus && focus.activeFocus) {
            if (focus instanceof TextInput || focus instanceof TextArea) {
                const pos = focus.cursorPosition; // qmllint disable missing-property
                focus.insert(pos, clip);// qmllint disable missing-property
                focus.cursorPosition = pos + clip.length;
            } else {
                userQueries.addQuery(clip);
            }
        } else {
            userQueries.addQuery(clip);
        }

        root.refreshStatus();
    }

    function refreshStatus() {
        statusBar.text = root.handler.translate("Hotkeys.Mode", root.handler.language) + ": " + handler.currentModeName + "   |   " + root.handler.translate("Response.Count", root.handler.language) + ": " + userQueries.count();
    }

    function refreshHotkeys() {
        hotkeyBar.bindings = [
            {
                key: "^Space",
                label: root.handler.translate("Hotkeys.Send", root.handler.language)
            },
            {
                key: "^V",
                label: root.handler.translate("Hotkeys.Insert", root.handler.language)
            },
            {
                key: "^M",
                label: root.handler.translate("Hotkeys.Mode", root.handler.language) + ": " + handler.currentModeName
            },
            {
                key: "^S",
                label: root.handler.translate("Hotkeys.Save", root.handler.language)
            },
            {
                key: "↑↓",
                label: root.handler.translate("Hotkeys.Scroll", root.handler.language)
            }
        ];
    }
}
