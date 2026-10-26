import json
import logging
import uuid
from abc import ABC, abstractmethod

from pydantic import BaseModel
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

LOGGER = logging.getLogger(__name__)


class Invoke(ABC):
    """Интерфейс для работы с ответами Сценариста по API."""

    @abstractmethod
    def invoke(self, text: str, config) -> BaseModel:
        """Метод-обёртка для отправки запросов LLM-агенту извне."""
        ...


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

    @Slot(int, list)
    def runPipeline(self, mode: int, queries: list):  # noqa: N802
        """
        Обработчик запросов Сценариста.
        """
        entries = _normalize_queries(queries)
        if not entries:
            LOGGER.warning("Нет вхождений")
            return

        # * Вопрос-ответ
        if mode == 0:
            uid, content = entries[0]

            try:
                model = self._invoker.invoke(content, self._config)
                response = model.model_dump_json(indent=2, ensure_ascii=False)
            except Exception as err:
                raise TypeError(f"Ошибка в {self.runPipeline}") from err

            # TODO сначала сохранение в файл, потом чтение из файла, потом сохранение в currentResponse
            self.responseReady.emit(response)
            self.queriesProcessed.emit([uid])

        # * Конвейер вопрос-ответ
        elif mode == 1:
            lines = "\n".join(f"[{i + 1}] Эхо: {text}" for i, (_, text) in enumerate(entries))
            response = f"Конвейер массовое создание ({len(entries)} шт.):\n{lines}"

            # TODO сначала сохранение в файл, потом чтение из файла, потом сохранение в currentResponse
            self.responseReady.emit(response)
            self.queriesProcessed.emit([uid for uid, _ in entries])

        # * ???
        else:
            results = []
            for _, text in entries:
                try:
                    model = self._invoker.invoke(text, self._config)
                    results.append(model.model_dump_json(indent=2, ensure_ascii=False))
                except Exception as err:
                    LOGGER.error(f"Ошибка массовой проверки: {err}")
                    results.append(
                        json.dumps(
                            {
                                "status": "EX",
                                "message": "Ошибка при выполнении запроса",
                            },
                            ensure_ascii=False,
                        )
                    )

            response = "\n\n---\n\n".join(results)

            # TODO сначала сохранение в файл, потом чтение из файла, потом сохранение в currentResponse
            self.responseReady.emit(response)
            self.queriesProcessed.emit([uid for uid, _ in entries])

    @Slot(str)
    def copyToClipboard(self, input: str):  # noqa: N802
        """
        Копирование текста в буфер обмена.
        """
        QGuiApplication.clipboard().setText(input)

    @Slot(result=str)
    def clipboardText(self):  # noqa: N802
        """
        Чтение текста из буфера обмена.
        """
        return QGuiApplication.clipboard().text() or ""

    @Slot(str, str)
    def saveToJson(self, file_path: str, current_response: str):  # noqa: N802
        """
        Сохранение текста в файл в формате JSON.
        """
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
