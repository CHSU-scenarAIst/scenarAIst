import QtQuick
import QtQuick.Layouts

// TODO динамическое количество рядов в зависимости от ширины занимаемого пространства
Rectangle {
    id: root

    property var bindings: []

    required property var funcAdd

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

    // TODO фокус курсора должен быть в новом после сразу после создания
    Shortcut {
        sequence: "Ctrl+E"
        context: Qt.ApplicationShortcut
        onActivated: {
            userQueries.addQuery("");
            root.refreshStatus();
        }
    }

    Shortcut {
        sequence: "Ctrl+D"
        context: Qt.ApplicationShortcut
        onActivated: {
            userQueries.removeLast();
            root.refreshStatus();
        }
    }

    Shortcut {
        sequence: "Ctrl+L"
        context: Qt.ApplicationShortcut
        onActivated: loadDialog.open()
    }

    Shortcut {
        sequence: "Ctrl+Q"
        context: Qt.ApplicationShortcut
        onActivated: exitDialog.open()
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
