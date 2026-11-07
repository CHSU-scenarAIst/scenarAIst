import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel
from PySide6.QtCore import QMessageLogContext, QObject, QtMsgType, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

RESPONSES_DIR = Path("responses")
LOGGER = logging.getLogger(__name__)


class Invoke(Protocol):
    """Интерфейс для работы с ответами Сценариста по API."""

    def invoke(self, text: str) -> BaseModel:
        """Объявление метода для отправки запросов LLM-агенту."""
        ...


class UserInterface:
    def __init__(self, invoker: Invoke):
        qml_dir = Path(__file__).parent / "qml"
        aml_main_path = qml_dir / "Main.qml"

        qInstallMessageHandler(_qt_message_handler)
        self._app = QGuiApplication(sys.argv)
        self._engine = QQmlApplicationEngine()
        # engine.addImportPath(sys.path[0])
        self._engine.addImportPath(qml_dir)

        self._handler_backend = HandlerBackend(invoker)
        self._engine.rootContext().setContextProperty("handlerBackend", self._handler_backend)
        self._engine.load(aml_main_path)

    def run(self) -> int:
        """Запуск пользовательского интерфейса."""
        if not self._engine.rootObjects():
            raise RuntimeError("Нет объектов для отрисовки")
        exit_code = self._app.exec()
        del self._engine
        return exit_code


class HandlerBackend(QObject):
    queryProcessed = Signal(str)  # noqa: N815
    responseReady = Signal(str)  # noqa: N815

    def __init__(self, invoker: Invoke, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._invoker = invoker

    @Slot(dict)
    def createOne(self, query: dict) -> None:  # noqa: N802
        """Создать один Сценарий."""
        uid = str(query.get("uid") or uuid.uuid4().hex).strip()
        text = str(query.get("text") or "").strip()
        result = self._invoker.invoke(text).model_dump_json(indent=2, ensure_ascii=False)
        json_text = _save_response(uid, result)
        self.responseReady.emit(json_text)
        self.queryProcessed.emit(uid)

    @Slot(str, result=list)
    def readLinesFromFile(self, file_path: str) -> list[str]:  # noqa: N802
        """Чтение задач (1 задача = 1 строка) из текстового файла."""

        path = Path(file_path)
        if not path.exists():
            LOGGER.error("Файл задач не найден: %s", path)
            return []

        with path.open(encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip()]

    @Slot(str, str)
    def saveToJson(self, file_path: str, current_response: str) -> None:  # noqa: N802
        """Сохранение текста в файл в формате JSON."""
        data = json.loads(current_response)
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    # ! [AI Note] Не добавлять в документацию
    @Slot(str)
    def copyToClipboard(self, input: str) -> None:  # noqa: N802
        """Копирование текста в буфер обмена."""
        QGuiApplication.clipboard().setText(input)

    # ! [AI Note] Не добавлять в документацию
    @Slot(result=str)
    def clipboardText(self) -> str:  # noqa: N802
        """Чтение текста из буфера обмена."""
        return QGuiApplication.clipboard().text() or ""


# ! [AI Note] Не добавлять в документацию
def _save_response(uid: str, json_text: str) -> str:
    """Сохранить ответ агента в файл и вернуть его содержимое файла."""
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    file_path = RESPONSES_DIR / f"{uid}.json"
    data = json.loads(json_text)
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return file_path.read_text(encoding="utf-8")


# ! [AI Note] Не добавлять в документацию
def _qt_message_handler(mode: QtMsgType, context: QMessageLogContext, message: str) -> None:
    """Перехватчик потока ошибок из QML."""

    out = f"{message}"

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
