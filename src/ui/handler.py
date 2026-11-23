"""Сборка и обработка сигналов UI."""

import csv
import logging
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import (
    QMessageLogContext,
    QObject,
    QtMsgType,
    Signal,
    Slot,
    qInstallMessageHandler,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine


class InvokeAgent(Protocol):
    """ВызовАгента. Интерфейс для работы с агентом-Сценаристом."""

    def invoke(self, task: str, min_steps: int, add_instruct: str) -> str:
        """Интерфейс метода отправки запросов агенту."""
        ...


class HandlerBackend(QObject):
    """Обработчик. Обработчик сигналов пользовательского интерфейса."""

    # ! [AI Note] Не_добавлять_в / удалить_из документации параметры `write_response`, `parent`
    def __init__(self, invoker: InvokeAgent, write_response: bool, parent: QObject | None = None) -> None:
        """Конструктор обработчика сигналов пользовательского интерфейса."""
        super().__init__(parent)
        self._invoker = invoker  # * Объект вызова агента-Сценариста.
        self._write_response = write_response  # ! [AI Note] Не_добавлять_в / удалить_из документации

    @Slot(str, str, str, str)
    def createOne(self, uid: str, task: str, min_steps: str, instruct: str) -> None:  # noqa: N802
        """Создать или изменить один Сценарий."""
        response = self._invoker.invoke(task, int(min_steps), instruct)
        self.responseReady.emit(uid, response, self._write_response)

    @Slot(str, result=list)
    def readLinesFromFile(self, path: str) -> list[str]:  # noqa: N802
        """Прочитать задачи (1 задача = 1 строка) из файла."""
        file_path = Path(path)
        if not file_path.exists():
            return []
        with file_path.open(encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip()]

    @Slot(str, str, str)
    def save(self, path: str, name: str, response: str) -> None:
        """Сохранить ответ агента в файл."""
        path_dir = Path(path)
        file_path = path_dir / f"{name}.json"
        path_dir.mkdir(parents=True, exist_ok=True)
        with file_path.open(encoding="utf-8", mode="w") as f:
            f.write(response)

    @Slot(str, result="QVariantList")
    def readAsCSV(self, text: str) -> list[str | int]:  # noqa: N802
        """Прочитать задачу как строку CSV."""
        parts = next(csv.reader([text]), [])
        if not parts:
            return ["", -1, ""]
        task, *args = parts
        min_steps = int(s) if args and (s := args[0].strip()).isdigit() else -1
        instruct = i if len(args) > 1 and (i := args[1].strip()) else ""
        return [task, min_steps, instruct]

    @Slot(str, result=str)
    def readAsBackRequest(self, path: str) -> str:  # noqa: N802
        """Прочитать существующий Сценарий."""
        file_path = Path(path)
        if not file_path.exists():
            LOGGER.warning("Сохранённый Сценарий '%s' не найден.", file_path)
            return ""
        # TODO упростить
        try:
            back_request = file_path.read_text(encoding="utf-8")
        except Exception as e:
            LOGGER.exception("Не удалось прочитать Сценарий '%s'.", file_path, exc_info=e)
            return ""
        return back_request

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    responseReady = Signal(str, str, bool)  # noqa: N815

    @Slot(str)
    def copyToClipboard(self, input: str) -> None:  # noqa: N802
        QGuiApplication.clipboard().setText(input)

    @Slot(result=str)
    def clipboardText(self) -> str:  # noqa: N802
        return QGuiApplication.clipboard().text() or ""


LOGGER = logging.getLogger(__name__)


class UserInterface:
    """ПользовательскийИнтерфейс. Сборщик пользовательского интерфейса."""

    # ! [AI Note] Не_добавлять_в / удалить_из документации параметры `argv`, `write_response`
    def __init__(self, argv: list[str], invoker: InvokeAgent, write_response: bool):
        """Конструктор сборщика пользовательского интерфейса."""
        qml_dir = Path(__file__).parent / "qml"
        qml_main_path = qml_dir / "Main.qml"

        # ! [AI Note] Не_добавлять_в / удалить_из документации
        def qt_message_handler(mode: QtMsgType, _context: QMessageLogContext, message: str) -> None:
            out = f"{message}"
            if mode == QtMsgType.QtInfoMsg:
                LOGGER.debug(out)
            if mode == QtMsgType.QtInfoMsg:
                LOGGER.info(out)
            elif mode == QtMsgType.QtWarningMsg:
                LOGGER.warning(out)
            elif mode == QtMsgType.QtCriticalMsg:
                LOGGER.exception(out)
            elif mode == QtMsgType.QtFatalMsg:
                raise RuntimeError("Необработанное исключение из QML: %s", out)

        qInstallMessageHandler(qt_message_handler)
        self._app = QGuiApplication(argv)  # * Объект UI.
        self._engine = QQmlApplicationEngine()  # * Объект движка UI.
        self._engine.addImportPath(qml_dir)
        self._handler_backend = HandlerBackend(invoker, write_response)  # * Объект обработчика сигналов UI.
        self._engine.rootContext().setContextProperty("handlerBackend", self._handler_backend)
        self._engine.load(qml_main_path)

    def run(self) -> int:
        """Запустить пользовательский интерфейс."""
        if not self._engine.rootObjects():
            raise RuntimeError("Нет объектов для отрисовки")
        exit_code = self._app.exec()
        del self._engine
        return exit_code
