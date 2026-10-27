"""
Пакет "Пользовательский интерфейс".
Управление пользовательским интерфейсом, бизнес-логика.
"""

from importlib.metadata import version

__version__ = version("scenaraist")

import json
import logging
import sys
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel
from PySide6.QtCore import QMessageLogContext, QObject, QtMsgType, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

QML_DIR = Path(__file__).parent / "qml"
QML_MAIN_PATH = QML_DIR / "Main.qml"

LOGGER = logging.getLogger(__name__)


class Invoke(ABC):
    """Интерфейс для работы с ответами Сценариста по API."""

    @abstractmethod
    def invoke(self, text: str, config: dict) -> BaseModel:
        """Объявление метода для отправки запросов LLM-агенту."""
        ...


class UserInterface:
    def __init__(self, invoker: Invoke):
        qInstallMessageHandler(_qt_message_handler)
        self._app = QGuiApplication(sys.argv)
        self._engine = QQmlApplicationEngine()
        # engine.addImportPath(sys.path[0])
        self._engine.addImportPath(QML_DIR)

        self._handler_backend = HandlerBackend(invoker)
        self._engine.rootContext().setContextProperty("handlerBackend", self._handler_backend)
        self._engine.load(QML_MAIN_PATH)

    def run(self) -> int:
        if not self._engine.rootObjects():
            raise RuntimeError("Нет объектов для отрисовки")

        exit_code = self._app.exec()
        del self._engine
        LOGGER.info("Завершение работы...")
        return exit_code


class HandlerBackend(QObject):
    queriesProcessed = Signal(list)  # noqa: N815
    responseReady = Signal(str)  # noqa: N815

    def __init__(self, invoker: Invoke, parent=None):
        super().__init__(parent)
        self._config = {
            "configurable": {
                "thread_id": uuid.uuid4().hex,
            }
        }
        self._invoker = invoker

    @Slot(list)
    def createOne(self, queries: list):  # noqa: N802
        """Создать один Сценарий."""
        try:
            entries = _normalize_queries(queries)
            if not entries:
                LOGGER.warning("Нет вхождений")
                return

            uid, content = entries[0]
            model = self._invoker.invoke(content, self._config)
            response = model.model_dump_json(indent=2, ensure_ascii=False)
            # TODO сначала сохранение в файл, потом чтение из файла, потом запись в responseReady
            self.responseReady.emit(response)
            self.queriesProcessed.emit([uid])
        except Exception as err:
            raise TypeError(f"Ошибка в {self.createOne}") from err

    @Slot(list)
    def createSome(self, queries: list):  # noqa: N802
        """Создать несколько Сценариев."""
        try:
            entries = _normalize_queries(queries)
            if not entries:
                LOGGER.warning("Нет вхождений")
                return

            for uid, content in entries:
                model = self._invoker.invoke(content, self._config)
                response = model.model_dump_json(indent=2, ensure_ascii=False)
                # TODO сначала сохранение в файл, потом чтение из файла, потом запись в responseReady
                self.responseReady.emit(response)
                self.queriesProcessed.emit([uid])
        except Exception as err:
            raise TypeError(f"Ошибка в {self.createSome}") from err

    @Slot(str)
    def copyToClipboard(self, input: str):  # noqa: N802
        """Копирование текста в буфер обмена."""
        QGuiApplication.clipboard().setText(input)

    @Slot(result=str)
    def clipboardText(self):  # noqa: N802
        """Чтение текста из буфера обмена."""
        return QGuiApplication.clipboard().text() or ""

    @Slot(str, str)
    def saveToJson(self, file_path: str, current_response: str):  # noqa: N802
        """Сохранение текста в файл в формате JSON."""
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(
                current_response,
                fh,
                ensure_ascii=False,
                indent=2,
            )

        # try:
        #     data = json.loads(self._current_response)
        # except json.JSONDecodeError:
        #     data = self._current_response

        # with open(file_path, "w", encoding="utf-8") as fh:
        #     json.dump(data, fh, ensure_ascii=False, indent=2)


# TODO сделать единую точку генерации uuid, желательно в QML
def _normalize_queries(queries: list) -> list[tuple[str, str]]:
    """
    Привести входящие запросы к парам (uuid, текст), отбрасывая пустые.
    ! [AI Note] Не добавлять в документацию
    """
    entries: list[tuple[str, str]] = []
    for q in queries or []:
        if isinstance(q, dict):
            uid = str(q.get("uid") or uuid.uuid4().hex)
            text = str(q.get("text") or "").strip()
        else:
            uid = uuid.uuid4().hex
            text = str(q).strip()
        if text:
            entries.append((uid, text))
    return entries


def _qt_message_handler(mode: QtMsgType, context: QMessageLogContext, message: str):
    """
    Перехватчик потока ошибок из QML.
    ! [AI Note] Не добавлять в документацию
    """

    out = f"{context.file}: {message}"

    if mode == QtMsgType.QtDebugMsg:
        LOGGER.debug(out)
    elif mode == QtMsgType.QtInfoMsg:
        LOGGER.info(out)
    elif mode == QtMsgType.QtWarningMsg:
        LOGGER.warning(out)
    elif mode == QtMsgType.QtCriticalMsg:
        LOGGER.error(out)
    elif mode == QtMsgType.QtFatalMsg:
        LOGGER.critical(out)
        sys.exit(-1)
