"""Обработчик для {Main.qml}."""

import json
import logging
import uuid
from typing import TYPE_CHECKING, TypedDict

from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

if TYPE_CHECKING:
    from pydantic import BaseModel

LOGGER = logging.getLogger(__name__)


class Translation(TypedDict):
    language: str
    translation: str


class Translatable(TypedDict):
    trId: str
    translations: list[Translation]


class TranslationsFile(TypedDict):
    translatables: list[Translatable]


class HandlerBackend(QObject):
    currentModeChanged = Signal()  # noqa: N815
    currentResponseChanged = Signal()  # noqa: N815
    queriesProcessed = Signal(list)  # noqa: N815
    languageChanged = Signal()  # noqa: N815

    def __init__(self, agent: CompiledStateGraph, json: TranslationsFile, parent=None):
        super().__init__(parent)
        self._MODES = ["question_answer", "conveyor_create", "conveyor_check"]
        self._MODE_NAMES = {
            "question_answer": "вопрос-ответ",
            "conveyor_create": "конвейер массовое создание",
            "conveyor_check": "конвейер массовая проверка + изменение",
        }

        self._current_mode = self._MODES[0]
        self._current_response = ""
        self._agent = agent
        self._config: dict[str, dict[str, str]] = {
            "configurable": {
                "thread_id": uuid.uuid4().hex,
            }
        }

        self._translations: dict[str, dict[str, str]] = {}
        self._languages: set[str] = set()
        for item in json.get("translatables", []):
            key = item.get("trId")
            if not key:
                continue

            mapping = {}
            for entry in item.get("translations", []):
                language = entry.get("language")
                value = entry.get("translation")
                mapping[language] = value
                self._languages.add(language)

            self._translations[key] = mapping

        self._language = "ru" if "ru" in self._languages else next(iter(sorted(self._languages)), "ru")

    @Property(str, notify=currentModeChanged)
    def currentMode(self):  # noqa: N802
        return self._current_mode

    @Property(str, notify=currentModeChanged)
    def currentModeName(self):  # noqa: N802
        return self._MODE_NAMES[self._current_mode]

    @Slot()
    def cycleMode(self):  # noqa: N802
        idx = self._MODES.index(self._current_mode)
        self._current_mode = self._MODES[(idx + 1) % len(self._MODES)]
        self.currentModeChanged.emit()

    @Property(str, notify=currentResponseChanged)
    def currentResponse(self):  # noqa: N802
        return self._current_response

    @Slot(str, list)
    def runPipeline(self, mode, queries):  # noqa: N802
        queries = [str(q).strip() for q in (queries or []) if str(q).strip()]

        if mode == "question_answer":
            if not queries:
                return

            content = queries[0]

            try:
                result = self._agent.invoke(input={"messages": [HumanMessage(content)]}, config=self._config)
                response: BaseModel = result["response"]
                response = response.model_dump_json(indent=2, ensure_ascii=False)
            except Exception as e:
                LOGGER.error(f"Ошибка при выполнении запроса: {e}")
                response = "Ошибка при выполнении запроса."

            self._current_response = response
            self.currentResponseChanged.emit()
            self.queriesProcessed.emit([0])

        elif mode == "conveyor_create":
            if not queries:
                return

            lines = "\n".join(f"[{i + 1}] Эхо: {q}" for i, q in enumerate(queries))
            response = f"Конвейер массовое создание ({len(queries)} шт.):\n{lines}"

            self._current_response = response
            self.currentResponseChanged.emit()
            self.queriesProcessed.emit(list(range(len(queries))))

        else:
            response = "Заглушка: режим «массовая проверка + изменение» не реализован."

            self._current_response = response
            self.currentResponseChanged.emit()

    @Slot()
    def clearAll(self):  # noqa: N802
        self._current_response = ""
        self.currentResponseChanged.emit()
        # TODO очищать поле ввода Пользователя

    @Slot(result=str)
    def clipboardText(self):  # noqa: N802
        return QGuiApplication.clipboard().text() or ""

    @Slot(str)
    def copyToClipboard(self, text):  # noqa: N802
        QGuiApplication.clipboard().setText(text)

    @Slot(str)
    def saveToJson(self, file_path):  # noqa: N802
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(self._current_response, fh, ensure_ascii=False, indent=2)

    @Property(str, notify=languageChanged)
    def language(self):
        return self._language

    @Slot(str)
    def setLanguage(self, language: str):  # noqa: N802
        if language not in self._languages or language == self._language:
            return
        self._language = language
        self.languageChanged.emit()

    @Slot(str, str, result=str)
    def translate(self, key: str, language: str) -> str:
        # Fallback order: requested language -> English -> key.
        translations: dict[str, str] = self._translations.get(key, {})
        return translations.get(language) or translations.get("en") or key
