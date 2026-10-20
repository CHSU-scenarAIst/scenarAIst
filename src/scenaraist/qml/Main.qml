import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Window

import "./"

ApplicationWindow {
    id: root

    title: Localization.tr("Main.Title")
    visible: true
    width: 1200
    height: 700
    minimumWidth: 900
    minimumHeight: 500
    color: "#e8e8e8"

    property var handler: handlerBackend // qmllint disable unqualified
    property int currentMode: 0
    property var modes: {
        0: "Mode.QuestionAnswer",
        1: "Mode.ConveyorCreate",
        2: "Mode.ConveyorCheck"
    }
    readonly property int modesLength: Object.keys(modes).length
    property string currentResponse: ""

    ColumnLayout {
        anchors.fill: parent

        StatusBar {
            id: statusBar
            Layout.fillWidth: true
            implicitHeight: 30
            color: "#000000"
        }

        ComboBox {
            Layout.alignment: Qt.AlignRight

            model: ["Русский", "English"]
            currentIndex: Localization.language === "ru" ? 0 : 1

            onActivated: function (index) {
                Localization.language = index === 0 ? "ru" : "en";
                root.refreshStatus();
                root.refreshHotkeys();
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
                text: root.currentResponse
                onCopyRequested: root.handler.copyToClipboard(root.currentResponse)
            }

            UserQueries {
                id: userQueries
                Layout.fillWidth: true
                Layout.fillHeight: true
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
                text: Localization.tr("Clear.Btn")
                ToolTip.text: Localization.tr("Clear.Tip")
                ToolTip.visible: hovered
                onClicked: {
                    root.currentResponse = "";
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
        onActivated: function onCurrentModeChanged() {
            root.currentMode = (root.currentMode + 1) % root.modesLength;
            root.refreshStatus();
        }
    }

    Shortcut {
        sequence: "Ctrl+C"
        context: Qt.ApplicationShortcut
        onActivated: root.copyResponseOrSelection()
    }

    Shortcut {
        sequence: "Ctrl+S"
        context: Qt.ApplicationShortcut
        onActivated: saveDialog.open()
    }

    Shortcut {
        sequence: "Up"
        context: Qt.ApplicationShortcut
        onActivated: llmResponse.scrollBy(-40)
    }

    Shortcut {
        sequence: "Down"
        context: Qt.ApplicationShortcut
        onActivated: llmResponse.scrollBy(40)
    }

    Connections {
        target: root.handler

        function onResponseReady(response) {
            root.currentResponse = response;
        }

        function onQueriesProcessed(indices) {
            userQueries.removeByIndices(indices);
            // function onQueriesProcessed(uids) {
            //     userQueries.removeByUids(uids);
            root.refreshStatus();
        }
    }

    Component.onCompleted: {
        root.refreshStatus();
        root.refreshHotkeys();
    }

    FileDialog {
        id: saveDialog
        title: Localization.tr("Save.Response")
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        nameFilters: ["JSON files (*.json)", "All files (*)"]

        onAccepted: {
            const path = root.toLocalPath(selectedFile);
            root.handler.saveToJson(path, root.currentResponse);
        }
    }

    function runPipeline() {
        const queries = userQueries.texts();
        if (queries.length <= 0) {
            return;
        }
        handler.runPipeline(root.currentMode, queries);
    }

    function pasteFromClipboard() {
        const clip = handler.clipboardText();

        if (!clip) {
            return;
        }

        const focus = root.activeFocusItem;
        if (focus && focus.activeFocus && focus instanceof TextArea) {
            const pos = focus.cursorPosition; // qmllint disable missing-property
            focus.insert(pos, clip);// qmllint disable missing-property
            focus.cursorPosition = pos + clip.length;
        } else {
            userQueries.addQuery(clip);
        }

        refreshStatus();
    }

    function copyResponseOrSelection() {
        const focus = root.activeFocusItem;

        if (focus && focus.activeFocus && focus.selectedText) { // qmllint disable missing-property
            focus.copy(); // qmllint disable missing-property
            return;
        }

        if (root.currentResponse) {
            root.handler.copyToClipboard(root.currentResponse);
        }
    }

    function toLocalPath(fileUrl) {
        let path = fileUrl.toString().replace(/^file:\/\//, "");
        // ? есть ли уже готовые решения в документации?
        // Windows: "file:///C:/..." -> "/C:/..." -> "C:/..."
        if (/^\/[A-Za-z]:[\\/]/.test(path)) {
            path = path.slice(1);
        }

        return path;
    }

    function refreshStatus() {
        statusBar.text = Localization.tr("Hotkeys.Mode") + ": " + Localization.tr(root.modes[root.currentMode]) + "   |   " + Localization.tr("Response.Count") + ": " + userQueries.count();
    }

    function refreshHotkeys() {
        hotkeyBar.bindings = [
            {
                key: "^Space",
                label: Localization.tr("Hotkeys.Send")
            },
            {
                key: "^V",
                label: Localization.tr("Hotkeys.Insert")
            },
            {
                key: "^M",
                label: Localization.tr("Hotkeys.Mode")
            },
            {
                key: "^C",
                label: Localization.tr("Hotkeys.Copy")
            },
            {
                key: "^S",
                label: Localization.tr("Hotkeys.Save")
            },
            {
                key: "↑↓",
                label: Localization.tr("Hotkeys.Scroll")
            }
        ];
    }
}
