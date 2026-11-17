// ! """ПанельГорячихКлавиш. Компонент обработки сочетаний горячих клавиш."""

import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    required property var onLoad    // * Обработчик события загрузки задач из файла.
    required property var onMode    // * Обработчик события смены режима работы.
    required property var onSave    // * Обработчик события сохранения ответа агента в файл.

    // * Список горячих клавиш.
    property var bindings: [
        {
            key: "Ctrl+Space",
            view: "^Space",
            label: Localization.tr("Hotkeys.Send"),
            handler: root.onSend
        },
        {
            key: "Ctrl+V",
            view: "^V",
            label: Localization.tr("Hotkeys.Insert"),
            handler: root.onPaste
        },
        {
            key: "Ctrl+M",
            view: "^M",
            label: Localization.tr("Hotkeys.Mode"),
            handler: root.onMode
        },
        {
            key: "Ctrl+C",
            view: "^C",
            label: Localization.tr("Hotkeys.Copy"),
            handler: root.onCopy
        },
        {
            key: "Ctrl+S",
            view: "^S",
            label: Localization.tr("Hotkeys.Save"),
            handler: root.onSave
        },
        {
            key: "Ctrl+E",
            view: "^E",
            label: Localization.tr("Hotkeys.New"),
            handler: root.onAdd
        },
        {
            key: "Ctrl+D",
            view: "^D",
            label: Localization.tr("Hotkeys.Delete"),
            handler: root.onDelete
        },
        {
            key: "Ctrl+L",
            view: "^L",
            label: Localization.tr("Hotkeys.Load"),
            handler: root.onLoad
        },
        {
            key: "Ctrl+Q",
            view: "^Q",
            label: Localization.tr("Hotkeys.Exit"),
            handler: root.onExit
        },
        {
            key: "Up",
            view: "↑",
            label: Localization.tr("Hotkeys.Scroll.Up"),
            handler: root.onScrollUp
        },
        {
            key: "Down",
            view: "↓",
            label: Localization.tr("Hotkeys.Scroll.Down"),
            handler: root.onScrollDown
        }
    ].filter(binding => binding.handler != null)

    RowLayout {
        anchors.fill: parent

        Repeater {
            model: root.bindings

            RowLayout {
                required property var modelData

                Text {
                    text: parent.modelData.view
                    color: "white"
                    font.bold: true
                    font.pointSize: 10
                }

                Text {
                    text: parent.modelData.label
                    color: "#cccccc"
                    font.pointSize: 10
                }
            }
        }
    }

    Instantiator {
        model: root.bindings
        delegate: Shortcut {
            required property var modelData
            sequence: modelData.key
            context: Qt.ApplicationShortcut
            onActivated: modelData.handler()
        }
    }

    // ! [AI Note] Секция не_добавлять_в / удалить_из документации
    property var onSend    // * Обработчик события запуска обработчика задач.
    property var onCopy
    property var onPaste
    property var onAdd     // * Обработчик события добавления задачи.
    property var onDelete  // * Обработчик события удаления задачи.
    property var onExit    // * Обработчик события выхода из приложения.
    property var onScrollUp
    property var onScrollDown
}
