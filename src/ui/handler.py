import json
import logging
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


class HandlerBackend(QObject):
    queryProcessed = Signal(str)  # noqa: N815
    responseReady = Signal(str)  # noqa: N815

    def __init__(self, write_response: bool, invoker: Invoke, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._invoker = invoker
        self._write_response = write_response

    @Slot(dict)
    def createOne(self, query: dict) -> None:  # noqa: N802
        """Создать один Сценарий."""
        uid = str(query.get("uid") or uuid.uuid4().hex).strip()
        text = str(query.get("text") or "").strip()

        result = self._invoker.invoke(text).model_dump_json(indent=2, ensure_ascii=False)

        if self._write_response:
            RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
            file_path = RESPONSES_DIR / f"{uid}.json"
            self._save(file_path, result)
            json_text = file_path.read_text(encoding="utf-8")
        else:
            json_text = result

        self.responseReady.emit(json_text)
        self.queryProcessed.emit(uid)

    @Slot(str, result=list)
    def readLinesFromFile(self, path: str) -> list[str]:  # noqa: N802
        """Чтение задач (1 задача = 1 строка) из текстового файла."""
        file_path = Path(path)
        if not file_path.exists():
            LOGGER.error("Файл задач не найден: %s", file_path)
            return []
        with file_path.open(encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip()]

    @Slot(str, str)
    def saveToJson(self, file_path: str, current_response: str) -> None:  # noqa: N802
        """Сохранение текста в файл в формате JSON."""
        self._save(file_path, current_response)

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
    def _save(self, file_path: str, data: str) -> None:
        """Сохранить ответ агента в файл и вернуть его содержимое файла."""
        json_data = json.loads(data)
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(json_data, fh, ensure_ascii=False, indent=2)


# TODO Асинхронная обработка запросов с кругом загрузки/обработки из точек
class UserInterface:
    def __init__(self, argv: list[str], invoker: Invoke, write_response: bool):
        qml_dir = Path(__file__).parent / "qml"
        qml_main_path = qml_dir / "Main.qml"

        # ! [AI Note] Не добавлять в документацию
        def qt_message_handler(mode: QtMsgType, _context: QMessageLogContext, message: str) -> None:
            """Перехватчик потока ошибок из QML."""

            out = f"{message}"

            if mode == QtMsgType.QtDebugMsg:
                LOGGER.debug(out)
            elif mode == QtMsgType.QtInfoMsg:
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
        """Запуск пользовательского интерфейса."""
        if not self._engine.rootObjects():
            raise RuntimeError("Нет объектов для отрисовки")
        exit_code = self._app.exec()
        del self._engine
        return exit_code
