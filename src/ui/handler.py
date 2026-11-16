"""Сборка и обработка сигналов UI."""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel
from PySide6.QtCore import QMessageLogContext, QObject, QtMsgType, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

LOGGER = logging.getLogger(__name__)

RESPONSES_DIR = Path("responses")


class InvokeAgent(Protocol):
    """Интерфейс для работы с агентом-Сценаристом."""

    def invoke(self, task: str, min_steps: int, add_instruct: str) -> BaseModel:
        """Объявление метода для отправки запросов агенту."""
        ...


class HandlerBackend(QObject):
    """Обработчик сигналов пользовательского интерфейса."""

    def __init__(self, invoker: InvokeAgent, write_response: bool, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._invoker = invoker  # * Объект вызова агента-Сценариста
        self._write_response = write_response  # ! [AI Note] Не_добавлять_в / удалить_из документации

    @Slot(str, str)
    def createOne(self, uid: str, query: str) -> None:  # noqa: N802
        """Создать один Сценарий."""
        try:
            task, min_steps, instruct = self._get_args(query)
            response = self._invoker.invoke(task, min_steps, instruct)
            data = response.model_dump_json(indent=2, ensure_ascii=False)
            self._emit_response(uid, data)
        except Exception as e:
            LOGGER.critical(e)

    @Slot(dict)
    def changeOne(self, uid: str, query: str) -> None:  # noqa: N802
        """Изменить один Сценарий."""
        try:
            name, min_steps, instruct = self._get_args(query)
            back_request = self._read_from_file(name)
            if not back_request:
                return
            task = json.dumps(back_request, ensure_ascii=False)
            response = self._invoker.invoke(task, min_steps, instruct)
            data = response.model_dump_json(indent=2, ensure_ascii=False)
            self._emit_response(uid, data)
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
    def save(self, path: str, response: str) -> None:
        """Сохранить ответ агента-Сценариста в файл."""
        self._save_to_file(path, response)

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    queryProcessed = Signal(str)  # noqa: N815
    responseReady = Signal(str)  # noqa: N815

    @Slot(str)
    def copyToClipboard(self, input: str) -> None:  # noqa: N802
        """Скопировать текст в буфер обмена."""
        QGuiApplication.clipboard().setText(input)

    @Slot(result=str)
    def clipboardText(self) -> str:  # noqa: N802
        """Прочитать текст из буфера обмена."""
        return QGuiApplication.clipboard().text() or ""

    def _get_args(self, query: str) -> tuple[str, int, str]:
        parts = next(csv.reader([query]), [])
        if not parts:
            return "", -1, ""
        task, *args = parts
        min_steps = int(s) if args and (s := args[0].strip()).isdigit() else 1
        instruct = i if len(args) > 1 and (i := args[1].strip()) else ""
        return task, min_steps, instruct

    def _emit_response(self, uid: str, data: str) -> None:
        if self._write_response:
            name = f"{uid}.json"
            self._save_to_file(name, data)
        self.responseReady.emit(data)
        self.queryProcessed.emit(uid)

    def _save_to_file(self, name: str, data: str) -> None:
        file_path = RESPONSES_DIR / name
        RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
        with file_path.open(encoding="utf-8", mode="w") as f:
            f.write(data)

    def _read_from_file(self, name: str) -> Any:
        file_path = RESPONSES_DIR / name
        if not file_path.exists():
            LOGGER.warning("Сохранённый Сценарий '%s' не найден.", file_path)
            return {}
        try:
            back_request = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            LOGGER.exception("Не удалось прочитать Сценарий '%s'.", file_path)
            return {}
        return back_request


class UserInterface:
    """Сборщик пользовательского интерфейса."""

    def __init__(self, argv: list[str], invoker: InvokeAgent, write_response: bool):
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
        self._app = QGuiApplication(argv)  # * Объект UI
        self._engine = QQmlApplicationEngine()  # * Объект движка UI
        self._engine.addImportPath(qml_dir)
        self._handler_backend = HandlerBackend(invoker, write_response)  # * Объект обработчика сигналов UI
        self._engine.rootContext().setContextProperty("handlerBackend", self._handler_backend)
        self._engine.load(qml_main_path)

    def run(self) -> int:
        """Запускает пользовательский интерфейс."""
        if not self._engine.rootObjects():
            raise RuntimeError("Нет объектов для отрисовки")
        exit_code = self._app.exec()
        del self._engine
        return exit_code
