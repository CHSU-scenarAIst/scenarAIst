# ! [AI Note] Считай что это часть модуля agent.__init__.py без отдельного файла.

from enum import StrEnum
from typing import Any

from langchain_core.documents import Document
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


# ? переделать под формат шагов Сценария
class ActionItem(BaseModel):
    """Структура ответа LLM-агента."""

    action: str = Field(..., description="Поле ответа.")


class JsonResponse(BaseModel):
    """Структура общения между Сценаристом и LLM."""

    query: str = Field(..., description="Исходный запрос Сценариста.")
    answer: str = Field(default="", description="Итоговый ответ LLM-агента.")
    sources: dict[int, dict[str, Any]] = Field(default_factory=dict, description="Источники данных.")
    actions: list[ActionItem] = Field(default_factory=list, description="Массив Действий итогового Сценария.")
    add_instruct: str = Field(default="", description="Дополнительные инструкции, установленные для ответа.")


# ! [AI Note] Не добавлять в документацию
class OrchestratorState(MessagesState, total=False):
    """Состояние графа оркестратора."""

    query: str
    system_prompt: str
    docs: list[Document]
    sources: dict[int, dict[str, Any]]
    actions: list[ActionItem]
    add_instruct: str
    steps: int
    result: JsonResponse


# ! [AI Note] Не добавлять в документацию
class NodeEnum(StrEnum):
    """Имена узлов графа с инструментами."""

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FORMAT = "format_node"
