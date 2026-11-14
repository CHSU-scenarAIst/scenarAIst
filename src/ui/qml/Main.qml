// ! """Управление пользовательским интерфейсом, бизнес-логика."""

import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Window

import "./components"

ApplicationWindow {
    id: root

    // * Обработчик сигналов пользовательского интерфейса
    property var handler: handlerBackend    // qmllint disable unqualified

    // * Текущий режим работы программы
    property int currentMode: 0

    // * Режимы работы (создать один / создать массово / изменить один / изменить массово).
    property var modes: {
        0: "Mode.CreateOne",
        1: "Mode.CreateSome",
        2: "Mode.ChangeOne",
        3: "Mode.ChangeSome"
    }

    // * Текущий ответ агента-Сценариста
    property string currentResponse: ""

    ColumnLayout {
        anchors.fill: parent

        StatusBar {
            id: statusBar
            Layout.fillWidth: true
            implicitHeight: 30
            color: "#000000"

            text: {
                const mode = Localization.tr("Hotkeys.Mode") + ": " + Localization.tr(root.modes[root.currentMode]);
                const query = Localization.tr("Query.Count") + ": " + userQueries.queryCount;
                return mode + "   |   " + query;
            }
        }

        ComboBox {
            Layout.alignment: Qt.AlignRight

            model: ["Русский", "English"]
            currentIndex: Localization.language === "ru" ? 0 : 1

            onActivated: index => {
                Localization.language = index === 0 ? "ru" : "en";

                hotkeyBar.refreshHotkeys();
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            AgentResponse {
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
                onRunRequested: root.send()
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
                }
            }
        }

        HotkeyBar {
            id: hotkeyBar
            Layout.fillWidth: true
            implicitHeight: 30
            color: "#000000"

            onLoad: () => loadDialog.open()
            onMode: () => {
                root.currentMode = (root.currentMode + 1) % root.modesLength;
            }
            onSave: () => saveDialog.open()

            onAdd: () => userQueries.addQuery("")
            onDelete: () => userQueries.removeLast()
            onExit: () => exitDialog.open()
            onSend: () => root.send()
            onPaste: () => root.pasteFromClipboard()
            onCopy: () => root.copyResponseOrSelection()
            onScrollUp: () => llmResponse.scrollBy(-60)
            onScrollDown: () => llmResponse.scrollBy(60)
        }
    }

    Component.onCompleted: {
        hotkeyBar.refreshHotkeys();
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

    FileDialog {
        id: loadDialog
        title: Localization.tr("Load.Tasks")
        fileMode: FileDialog.OpenFile
        nameFilters: ["Text files (*.csv)", "All files (*)"]

        onAccepted: {
            const path = root.toLocalPath(selectedFile);
            const lines = root.handler.readLinesFromFile(path);
            if (lines.length <= 0) {
                console.error("Файл задач не найден или он пуст: ", path);
                // ? сообщение об ошибке
                return;
            }

            // TODO "Задача,Максимум_шагов"
            for (const line of lines) {
                userQueries.addQuery(line);
            }
            root.currentMode = 1;
        }
    }

    Dialog {
        id: exitDialog
        title: Localization.tr("Exit.Question")
        modal: true
        standardButtons: Dialog.Yes | Dialog.No
        onOpened: {
            Qt.callLater(() => {
                const overlay = Overlay.overlay;
                exitDialog.x = Math.max(0, (overlay.width - exitDialog.width) / 2);
                exitDialog.y = Math.max(0, (overlay.height - exitDialog.height) / 2);
                exitDialog.standardButton(Dialog.No).forceActiveFocus();
            });
        }
        onAccepted: Qt.quit()
    }

    // * """Отправить задачи на обработку."""
    function send() {
        if (root.currentMode === 0) {
            const field = userQueries.getFirst();
            if (field) {
                handler.createOne(field);
            }
        } else if (root.currentMode === 1) {
            const fields = [];
            for (let i = 0; i < userQueries.queryCount; i++) {
                const field = userQueries.get(i);
                if (field && field.text.trim() !== "") {
                    fields.push(field);
                }
            }
            for (const field of fields) {
                handler.createOne(field);
            }
        }
    // TODO остальные режимы
    }

    // ! [AI Note] Секция не_добавлять_в / удалить_из документации
    title: Localization.tr("Main.Title")
    visible: true
    width: 1200
    height: 700
    minimumWidth: 900
    minimumHeight: 500
    color: "#e8e8e8"

    readonly property int modesLength: Object.keys(modes).length

    Connections {
        target: root.handler

        function onResponseReady(response) {
            root.currentResponse = response;
        }

        function onQueryProcessed(uid) {
            userQueries.removeByUid(uid);
        }
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
    // !
}
