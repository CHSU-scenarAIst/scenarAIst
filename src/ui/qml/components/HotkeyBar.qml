import QtQuick
import QtQuick.Layouts

// ? динамическое количество рядов в зависимости от ширины занимаемого пространства
Rectangle {
    id: root

    property var bindings: []

    required property var onNew
    required property var onDelete
    required property var onLoad
    required property var onExit
    required property var onSend
    required property var onPaste
    required property var onMode
    required property var onCopy
    required property var onSave
    required property var onScrollUp
    required property var onScrollDown

    RowLayout {
        anchors.fill: parent

        Repeater {
            model: root.bindings

            RowLayout {
                required property var modelData

                Text {
                    text: parent.modelData?.key ?? ""
                    color: "white"
                    font.bold: true
                    font.pointSize: 10
                }

                Text {
                    text: parent.modelData?.label ?? ""
                    color: "#cccccc"
                    font.pointSize: 10
                }
            }
        }
    }

    Shortcut {
        sequence: "Ctrl+E"
        context: Qt.ApplicationShortcut
        onActivated: root.onNew()
    }

    Shortcut {
        sequence: "Ctrl+D"
        context: Qt.ApplicationShortcut
        onActivated: root.onDelete()
    }

    Shortcut {
        sequence: "Ctrl+L"
        context: Qt.ApplicationShortcut
        onActivated: root.onLoad()
    }

    Shortcut {
        sequence: "Ctrl+Q"
        context: Qt.ApplicationShortcut
        onActivated: root.onExit()
    }

    Shortcut {
        sequence: "Ctrl+Space"
        context: Qt.ApplicationShortcut
        onActivated: root.onSend()
    }

    Shortcut {
        sequence: "Ctrl+V"
        context: Qt.ApplicationShortcut
        onActivated: root.onPaste()
    }

    Shortcut {
        sequence: "Ctrl+M"
        context: Qt.ApplicationShortcut
        onActivated: root.onMode()
    }

    Shortcut {
        sequence: "Ctrl+C"
        context: Qt.ApplicationShortcut
        onActivated: root.onCopy()
    }

    Shortcut {
        sequence: "Ctrl+S"
        context: Qt.ApplicationShortcut
        onActivated: root.onSave()
    }

    Shortcut {
        sequence: "Up"
        context: Qt.ApplicationShortcut
        onActivated: root.onScrollUp()
    }

    Shortcut {
        sequence: "Down"
        context: Qt.ApplicationShortcut
        onActivated: root.onScrollDown()
    }

    // ! [AI Note] Не добавлять в документацию
    function refreshHotkeys() {
        bindings = [
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
                key: "^E",
                label: Localization.tr("Hotkeys.New")
            },
            {
                key: "^D",
                label: Localization.tr("Hotkeys.Delete")
            },
            {
                key: "^L",
                label: Localization.tr("Hotkeys.Load")
            },
            {
                key: "^Q",
                label: Localization.tr("Hotkeys.Exit")
            },
            {
                key: "↑↓",
                label: Localization.tr("Hotkeys.Scroll")
            }
        ];
    }
}
