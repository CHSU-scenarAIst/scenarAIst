# ! [AI Note] Считай что это часть модуля agent.agent.py без отдельного файла.

import operator
from enum import StrEnum
from typing import Annotated

from langchain_core.documents import Document
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class Action(StrEnum):
    """Стандартизация действий персонала производства."""

    USE = "Использовать"
    TAKEN = "Взять"
    ENABLE = "Включить"
    DISABLE = "Выключить"
    # Воткнуть
    # Нажать
    # TODO


# ? переделать под формат шагов Сценария
class ScenarioStep(BaseModel):
    """Структура ответа LLM-агента."""

    hash_id: str = Field(description="Уникальный идентификатор шага.")
    subject: str = Field(description="TODO")
    object: str = Field(description="TODO")
    action: Action = Field(description="Действие над объектом.")
    order: int | None = Field(default=None, description="Порядковый номер Шага в очереди Сценария.")


class Scenario(BaseModel):
    """Структура Сценария."""

    steps: list[ScenarioStep] = Field(default_factory=list, description="Массив Шагов итогового Сценария.")


class JsonResponse(BaseModel):
    """Структура общения между Сценаристом и LLM."""

    query: str = Field(description="Исходный запрос Сценариста.")
    answer: str = Field(default="", description="Итоговый ответ LLM-агента.")
    sources: dict[int, dict[str, str]] = Field(description="Источники данных.")
    add_instruct: str = Field(default="", description="Дополнительные инструкции, установленные для ответа.")
    scenario: Scenario | None = Field(default=None, description="Сценарий.")


# ! [AI Note] Не добавлять в документацию
class OrchestratorState(MessagesState, total=False):
    """Состояние графа оркестратора."""

    query: str
    system_prompt: str
    sources: dict[int, dict[str, str]]
    scenario: Scenario
    add_instruct: str
    docs: set[Document]
    steps_count: Annotated[int, operator.add]
    result: JsonResponse


# ! [AI Note] Не добавлять в документацию
class NodeEnum(StrEnum):
    """Имена узлов графа с инструментами."""

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FORMAT = "format_node"
