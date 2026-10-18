"""Обработчик для {Main.qml}."""

import json
import logging
import uuid

from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

LOGGER = logging.getLogger(__name__)


class HandlerBackend(QObject):
    queriesProcessed = Signal(list)  # noqa: N815
    responseReady = Signal(str)  # noqa: N815

    def __init__(self, agent: CompiledStateGraph, parent=None):
        super().__init__(parent)
        self._config: dict[str, dict[str, str]] = {
            "configurable": {
                "thread_id": uuid.uuid4().hex,
            }
        }

        self._agent = agent

    @Slot(int, list)
    def runPipeline(self, mode: int, queries: list):  # noqa: N802
        queries = [str(q).strip() for q in (queries or []) if str(q).strip()]

        if mode == 0:
            if not queries:
                return

            content = queries[0]

            try:
                result = self._agent.invoke(input={"messages": [HumanMessage(content)]}, config=self._config)
                model = result["response"]

                if not isinstance(model, BaseModel):
                    raise TypeError("Ответ агента не является моделью Pydantic")

                response = model.model_dump_json(indent=2, ensure_ascii=False)
            except Exception as e:
                response = "Ошибка при выполнении запроса"
                LOGGER.error(f"{response}: {e}")

            self.responseReady.emit(response)
            self.queriesProcessed.emit([0])

        elif mode == 1:
            if not queries:
                return

            lines = "\n".join(f"[{i + 1}] Эхо: {q}" for i, q in enumerate(queries))
            response = f"Конвейер массовое создание ({len(queries)} шт.):\n{lines}"

            self.responseReady.emit(response)
            self.queriesProcessed.emit(list(range(len(queries))))

        else:
            response = "Заглушка: режим «массовая проверка + изменение» не реализован."

            self.responseReady.emit(response)

    @Slot(str)
    def copyToClipboard(self, input: str):  # noqa: N802
        QGuiApplication.clipboard().setText(input)

    @Slot(result=str)
    def clipboardText(self):  # noqa: N802
        return QGuiApplication.clipboard().text() or ""

    @Slot(str, str)
    def saveToJson(self, file_path: str, current_response: str):  # noqa: N802
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(current_response, fh, ensure_ascii=False, indent=2)

        # try:
        #     data = json.loads(self._current_response)
        # except json.JSONDecodeError:
        #     data = self._current_response

        # with open(file_path, "w", encoding="utf-8") as fh:
        #     json.dump(data, fh, ensure_ascii=False, indent=2)
