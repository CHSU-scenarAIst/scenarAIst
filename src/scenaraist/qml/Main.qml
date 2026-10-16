import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Window

import "./components"

// TODO: проверить оформление, вынести хард-код текст на уровень выше

ApplicationWindow {
    id: root

    title: "scenarAIst"
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

            text: ""
        }

        // TODO убрать знание о поддерживаемых языках
        ComboBox {
            Layout.alignment: Qt.AlignRight
            model: ["English", "Русский", "Deutsch"]
            currentIndex: 0
            onActivated: function (index) {
                root.handler.setLanguage(["en", "ru", "de"][index]);
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

                title: root.handler.translate("main.titleResponse", root.handler.language)
                text: root.handler.currentResponse
                onCopyRequested: root.handler.copyToClipboard(root.handler.currentResponse)
            }

            UserQueries {
                id: userQueries
                Layout.fillWidth: true
                Layout.fillHeight: true

                title: root.handler.translate("main.titleQuery", root.handler.language)
                onRunRequested: root.runPipeline()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: root.handler.translate("main.btnClear", root.handler.language)
                ToolTip.text: "Очистить поля Ответов LLM и Запросов Пользователя"
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

            // * it will be set
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
        title: "Сохранить ответ LLM в JSON"
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
        // ! TODO - здесь не правильный insert
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
        statusBar.text = "Режим: " + handler.currentModeName + "   |   Запросов: " + userQueries.count();
    }

    function refreshHotkeys() {
        hotkeyBar.bindings = [
            {
                key: "^Space",
                label: "Отправить"
            },
            {
                key: "^V",
                label: "Вставить"
            },
            {
                key: "^M",
                label: "Режим: " + handler.currentModeName
            },
            {
                key: "^S",
                label: "Сохранить JSON"
            },
            {
                key: "↑↓",
                label: "Прокрутка ответа"
            }
        ];
    }
}
