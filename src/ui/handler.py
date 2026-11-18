"""Сборка и обработка сигналов UI."""

import csv
import logging
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QMessageLogContext, QObject, QtMsgType, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

LOGGER = logging.getLogger(__name__)


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
        self.RESPONSES_DIR = Path("responses")  # ! [AI Note] Не_добавлять_в / удалить_из документации

    @Slot(str, str)
    def createOne(self, uid: str, query: str) -> None:  # noqa: N802
        """Создать или изменить один Сценарий."""
        try:
            task, min_steps, instruct = self._get_args(query)
            back_request = self._read_from_file(task)
            if back_request:
                task = back_request
            response = self._invoker.invoke(task, min_steps, instruct)
            self._emit_response(uid, response)
        except Exception as e:
            LOGGER.critical(e)

    @Slot(str, result=list)
    def readLinesFromFile(self, path: str) -> list[str]:  # noqa: N802
        """Прочитать задачи (1 задача = 1 строка) из файла."""
        file_path = Path(path)
        if not file_path.exists():
            return []
        with file_path.open(encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip()]

    @Slot(str, str)
    def save(self, name: str, response: str) -> None:
        """Сохранить ответ агента в файл."""
        self._save_to_file(name, response)

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    queryProcessed = Signal(str)  # noqa: N815
    responseReady = Signal(str)  # noqa: N815

    @Slot(str)
    def copyToClipboard(self, input: str) -> None:  # noqa: N802
        QGuiApplication.clipboard().setText(input)

    @Slot(result=str)
    def clipboardText(self) -> str:  # noqa: N802
        return QGuiApplication.clipboard().text() or ""

    def _get_args(self, query: str) -> tuple[str, int, str]:
        parts = next(csv.reader([query]), [])
        if not parts:
            return "", -1, ""
        task, *args = parts
        min_steps = int(s) if args and (s := args[0].strip()).isdigit() else -1
        instruct = i if len(args) > 1 and (i := args[1].strip()) else ""
        return task, min_steps, instruct

    def _emit_response(self, uid: str, response: str) -> None:
        if self._write_response:
            name = f"{uid}.json"
            self._save_to_file(name, response)
        self.responseReady.emit(response)
        self.queryProcessed.emit(uid)

    def _save_to_file(self, name: str, response: str) -> None:
        file_path = self.RESPONSES_DIR / name
        self.RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
        with file_path.open(encoding="utf-8", mode="w") as f:
            f.write(response)

    def _read_from_file(self, name: str) -> str:
        file_path = self.RESPONSES_DIR / name
        if not file_path.exists():
            LOGGER.warning("Сохранённый Сценарий '%s' не найден.", file_path)
            return ""
        try:
            back_request = file_path.read_text(encoding="utf-8")
        except Exception as e:
            LOGGER.exception("Не удалось прочитать Сценарий '%s'.", file_path, exc_info=e)
            return ""
        return back_request


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
