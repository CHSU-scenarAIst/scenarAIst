// ! """Управление пользовательским интерфейсом, бизнес-логика."""

import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Window

import "./components"

ApplicationWindow {
    id: root

    // * Обработчик сигналов пользовательского интерфейса.
    property var handler: handlerBackend // qmllint disable unqualified
    // * Текущий режим работы программы.
    property int currentMode: 0
    // * Режимы генерации (создать один / создать массово / изменить один / изменить массово).
    property var modes: {
        0: "Mode.CreateOne",
        1: "Mode.CreateSome"
    }
    // * Текущий ответ агента.
    property string currentResponse: ""

    ColumnLayout {
        anchors.fill: parent

        StatusBar {
            id: statusBar
            Layout.fillWidth: true
            implicitHeight: 30
            color: "#000000"
            currentMode: root.modes[root.currentMode]
            queryCount: userQueries.queryCount
        }

        ComboBox {
            Layout.alignment: Qt.AlignRight
            model: ["Русский", "English"]
            currentIndex: Localization.language === "ru" ? 0 : 1
            onActivated: index => Localization.language = index === 0 ? "ru" : "en"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            AgentResponse {
                id: llmResponse
                Layout.fillWidth: true
                Layout.fillHeight: true
                answer: root.currentResponse
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
            onMode: () => root.currentMode = (root.currentMode + 1) % root.modesLength
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

    FileDialog {
        id: saveDialog
        title: Localization.tr("Save.Response")
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        nameFilters: ["JSON files (*.json)", "All files (*)"]
        onAccepted: {
            const name = root.toLocalPath(selectedFile);
            root.handler.save("", name, root.currentResponse);
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
                // ? сообщение об ошибке на экран пользователя, текст из перевода
                console.error("Файл задач не найден или он пуст: ", path);
                return;
            }

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

    // * Отправить задачи на обработку.
    function send() {
        if (root.currentMode === 0 || root.currentMode === 2) {
            const field = userQueries.getFirst();
            if (field) {
                let [task, minSteps, instruct] = handler.readAsCSV(field.text);
                const backRequest = handler.readAsBackRequest(task);
                if (backRequest) {
                    task = backRequest;
                }
                handler.createOne(field.uid, task, minSteps, instruct);
            }
        } else {
            const fields = [];
            for (let i = 0; i < userQueries.queryCount; i++) {
                const field = userQueries.get(i);
                if (field && field.text !== "") {
                    fields.push(field);
                }
            }
            for (const field of fields) {
                let [task, minSteps, instruct] = handler.readAsCSV(field.text);
                const backRequest = handler.readAsBackRequest(task);
                if (backRequest) {
                    task = backRequest;
                }
                handler.createOne(field.uid, task, minSteps, instruct);
            }
        }
    }

    // ! [AI Note] Секция не_добавлять_в / удалить_из документации
    title: Localization.tr("Main.Title")
    visible: true
    width: 1500
    height: 700
    minimumWidth: 900
    minimumHeight: 500
    color: "#e8e8e8"

    readonly property int modesLength: Object.keys(modes).length

    Connections {
        target: root.handler

        function onResponseReady(uid, response, write_response) {
            userQueries.removeByUid(uid);
            root.currentResponse = response;
            if (write_response) {
                root.handler.save("responses", uid, root.currentResponse);
            }
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
}
