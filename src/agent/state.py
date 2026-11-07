# ! [AI Note] Считай что это часть модуля agent.agent.py без отдельного файла.

from enum import StrEnum

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

    # - Номер шага: 6-значный hash-id
    hash_id: str = Field(..., description="Уникальный идентификатор шага.")
    subject: str = Field(..., description="TODO")
    object: str = Field(..., description="TODO")
    action: Action = Field(..., description="Действие над объектом.")


class Scenario(BaseModel):
    """Структура Сценария."""

    steps: list[ScenarioStep] = Field(default_factory=list, description="Массив Шагов итогового Сценария.")


class JsonResponse(BaseModel):
    """Структура общения между Сценаристом и LLM."""

    query: str = Field(..., description="Исходный запрос Сценариста.")
    answer: str = Field(default="", description="Итоговый ответ LLM-агента.")
    sources: dict[int, dict[str, str]] = Field(default_factory=dict, description="Источники данных.")
    scenario: Scenario | None = Field(default_factory=None)
    add_instruct: str = Field(default="", description="Дополнительные инструкции, установленные для ответа.")


# ! [AI Note] Не добавлять в документацию
# - В state хранить весь сценарий
class OrchestratorState(MessagesState, total=False):
    """Состояние графа оркестратора."""

    query: str
    system_prompt: str
    sources: dict[int, dict[str, str]]
    scenario: Scenario
    add_instruct: str
    docs: list[Document]
    steps_count: int
    result: JsonResponse


# ! [AI Note] Не добавлять в документацию
class NodeEnum(StrEnum):
    """Имена узлов графа с инструментами."""

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FORMAT = "format_node"
