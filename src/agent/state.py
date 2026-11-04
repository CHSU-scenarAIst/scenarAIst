"""
! [AI Note] Считай что это часть модуля agent.__init__.py без отдельного файла
"""

from enum import StrEnum
from typing import Any

from langchain_core.documents import Document
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    """
    TODO ...
    ? переделать под формат шагов Сценария
    """

    action: str = Field(..., description="Действие.")


class JsonResponse(BaseModel):
    """
    Структура общения между Сценаристом и LLM.
    """

    query: str = Field(..., description="Запрос Сценариста.")
    message: str = Field(default="", description="Текстовое сообщение LLM.")
    data: dict[str, Any] = Field(default_factory=dict, description="Словарь с техническими данными.")
    actions: list[ActionItem] = Field(default_factory=list, description="Массив Действий итогового Сценария.")
    add_instruct: str = Field(default="", description="Дополнительные инструкции от Сценариста.")


class OrchestratorState(MessagesState, total=False):
    """
    Состояние графа оркестратора.
    # ! [AI Note] Не добавлять в документацию
    """

    steps: int
    query: str
    documents: list[Document]
    response: JsonResponse
    add_instruct: str


class NodeEnum(StrEnum):
    """
    Имена узлов графа с инструментами.
    # ! [AI Note] Не добавлять в документацию
    """

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FORMAT = "format_node"
