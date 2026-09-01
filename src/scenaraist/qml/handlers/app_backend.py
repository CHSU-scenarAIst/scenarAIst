"""Backend for the {Main.qml}."""

import json
import logging
import uuid
from typing import TYPE_CHECKING

from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

if TYPE_CHECKING:
    from pydantic import BaseModel

LOGGER = logging.getLogger(__name__)


class AppBackend(QObject):
    currentModeChanged = Signal()  # noqa: N815
    currentResponseChanged = Signal()  # noqa: N815
    queriesProcessed = Signal(list)  # noqa: N815

    def __init__(self, agent: CompiledStateGraph, parent=None):
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

    @Slot(result=str)
    def clipboardText(self):  # noqa: N802
        return QGuiApplication.clipboard().text() or ""

    @Slot(str)
    def copyToClipboard(self, text):  # noqa: N802
        QGuiApplication.clipboard().setText(text)

    @Slot(str, str)
    def saveToJson(self, file_path):  # noqa: N802
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(self._current_response, fh, ensure_ascii=False, indent=2)
