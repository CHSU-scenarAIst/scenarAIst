"""Сборка и обработка сигналов UI."""

import json
import logging
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel
from PySide6.QtCore import QMessageLogContext, QObject, QtMsgType, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

RESPONSES_DIR = Path("responses")

LOGGER = logging.getLogger(__name__)


class InvokeAgent(Protocol):
    """Интерфейс для работы с агентом-Сценаристом."""

    def invoke(self, text: str) -> BaseModel:
        """Объявление метода для отправки запросов агенту."""
        ...


class HandlerBackend(QObject):
    """Обработчик сигналов пользовательского интерфейса."""

    def __init__(self, write_response: bool, invoker: InvokeAgent, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._invoker = invoker
        self._write_response = write_response

    @Slot(dict)
    def createOne(self, query: dict[str, str]) -> None:  # noqa: N802
        """Создать один Сценарий."""
        uid = str(query.get("uid")).strip()
        text = str(query.get("text")).strip()

        result = self._invoker.invoke(text).model_dump_json(indent=2, ensure_ascii=False)

        if self._write_response:
            RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
            file_path = RESPONSES_DIR / f"{uid}.json"
            self._save_to_json(file_path, result)
            json_text = file_path.read_text(encoding="utf-8")
        else:
            json_text = result

        self.responseReady.emit(json_text)
        self.queryProcessed.emit(uid)

    @Slot(dict)
    def changeOne(self, query: dict[str, str]) -> None:  # noqa: N802
        """Изменить один Сценарий."""
        # TODO
        ...

    @Slot(str, result=list)
    def readLinesFromFile(self, path: Path) -> list[str]:  # noqa: N802
        """Прочитать задачи (1 задача = 1 строка) из файла."""
        if not path.exists():
            LOGGER.error("Файл задач не найден: %s", path)
            return []
        with path.open(encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip()]

    @Slot(str, str)
    def saveToJson(self, path: Path, response: str) -> None:  # noqa: N802
        """Сохранить ответ агента-Сценариста в файл."""
        self._save_to_json(path, response)

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

    def _save_to_json(self, path: Path, data: str) -> None:
        """Сохранить текст в файл в формате Json."""
        json_data = json.loads(data)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(json_data, fh, ensure_ascii=False, indent=2)

    # !


class UserInterface:
    """Сборщик пользовательского интерфейса."""

    def __init__(self, argv: list[str], invoker: InvokeAgent, write_response: bool):
        qml_dir = Path(__file__).parent / "qml"
        qml_main_path = qml_dir / "Main.qml"

        # ! [AI Note] Секция не_добавлять_в / удалить_из документации
        def qt_message_handler(mode: QtMsgType, _context: QMessageLogContext, message: str) -> None:
            """Перехватчик потока ошибок из QML."""

            out = f"{message}"

            if mode in (QtMsgType.QtDebugMsg, QtMsgType.QtInfoMsg):
                LOGGER.info(out)
            elif mode == QtMsgType.QtWarningMsg:
                LOGGER.warning(out)
            elif mode == QtMsgType.QtCriticalMsg:
                LOGGER.exception(out)
            elif mode == QtMsgType.QtFatalMsg:
                raise RuntimeError("Необработанное исключение из QML: %s", out)

        qInstallMessageHandler(qt_message_handler)
        self._app = QGuiApplication(argv)
        self._engine = QQmlApplicationEngine()
        self._engine.addImportPath(qml_dir)

        self._handler_backend = HandlerBackend(write_response, invoker)  # нужно держать в памяти
        self._engine.rootContext().setContextProperty("handlerBackend", self._handler_backend)

        self._engine.load(qml_main_path)

    def run(self) -> int:
        """Запускает пользовательский интерфейс."""
        if not self._engine.rootObjects():
            raise RuntimeError("Нет объектов для отрисовки")
        exit_code = self._app.exec()
        del self._engine
        return exit_code
