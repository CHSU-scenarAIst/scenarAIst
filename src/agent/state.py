"""
! [AI Note] Считай что это часть модуля agent без отдельного файла
"""

from enum import StrEnum
from typing import Any

from langchain_core.documents import Document
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class WordItem(BaseModel):
    """
    Отдельное слово итогового ответа.
    ? переделать под формат шагов Сценария
    """

    word: str = Field(..., description="Слово из итогового ответа.")


class JsonResponse(BaseModel):
    """
    Структура JSON-ответа.
    ? переделать под формат шагов Сценария
    """

    status: str | None = Field(default=None, description="Статус ответа: 'OK' или 'ERROR'.")
    message: str = Field(..., description="Текстовое сообщение для пользователя.")
    data: dict[str, Any] | None = Field(default=None, description="Словарь с техническими данными.")
    words: list[WordItem] | None = Field(default=None, description="Массив слов итогового ответа.")
    add_instruct: str | None = Field(default=None, description="Дополнительные инструкции от Сценариста.")


class OrchestratorState(MessagesState, total=False):
    """
    Состояние графа оркестратора.
    # ! [AI Note] Не добавлять в документацию
    """

    steps: int
    query: str
    documents: list[Document] | None
    response: JsonResponse


class NodeEnum(StrEnum):
    """
    Имена узлов графа с инструментами.
    # ! [AI Note] Не добавлять в документацию
    """

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FORMAT = "format_node"
