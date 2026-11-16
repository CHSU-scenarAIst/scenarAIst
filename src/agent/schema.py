"""Схемы общения между Сценаристом и агентом-Сценаристом"""

import operator
import uuid
from enum import StrEnum
from typing import Annotated, Any

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class Step[ActionT: StrEnum](BaseModel):
    """Структура Шага в Сценарии."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Уникальный идентификатор шага.")
    actor: str = Field(description="Название/UID персонала.")
    target: str = Field(description="Название/UID составной части целевого объекта.")
    action: ActionT = Field(description="Действие персонала над целевым объектом или его частью.")
    # ? предусловие
    # ? постусловие


StepType = Step[StrEnum]


class Scenario(BaseModel):
    """Структура итогового Сценария."""

    steps: list[Step[StrEnum]] = Field(default_factory=list, description="Массив Шагов Сценария.")

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    _steps_indexes: dict[str, int] = {}

    def serialize_steps(self) -> list[dict[str, Any]]:
        return [{**s.model_dump(), "order": i} for i, s in enumerate(self.steps, start=1)]

    def rebuild_indexes(self) -> None:
        self._steps_indexes = {s.id: i for i, s in enumerate(self.steps, start=1) if s.id}

    def find(self, id: str) -> int | None:
        return self._steps_indexes.get(id)

    def count(self) -> int:
        return len(self._steps_indexes)


class BackRequest(BaseModel):
    """Структура ответа агента-Сценариста."""

    steps: list[Step[StrEnum]] = Field(description="Существующий Сценарий.")


class AgentResponse(BaseModel):
    """Структура ответа агента-Сценариста."""

    query: str = Field(description="Исходный запрос агенту.")
    answer: str = Field(description="Сообщение от агента.")
    sources: dict[int, dict[str, str]] = Field(default_factory=dict, description="Источники данных.")
    steps: list[dict[str, Any]] = Field(default_factory=list, description="Итоговый Сценарий от агента.")


# ! База данных состояния агента-Сценариста между запусками
class AgentState(MessagesState, total=False):
    """Состояние агента-Сценариста."""

    query: str
    sources: dict[int, dict[str, str]]
    scenario: Scenario
    invokes_count: Annotated[int, operator.add]
    invokes_max: int
    result: AgentResponse


class DeleteStep(BaseModel):
    id: str = Field(description="ID шага, который нужно удалить.")


class InsertStep[StepT: Step[Any]](BaseModel):
    step_after_id: str | None = Field(
        default=None, description="ID шага, после которого нужно вставить Шаг, или None для вставки в конец."
    )
    step: StepT = Field(description="Новый Шаг для вставки.")


class InsertSteps[StepT: Step[Any]](BaseModel):
    steps: list[InsertStep[StepT]] = Field(description="Список шагов для вставки.")


class UpdateStep[StepT: Step[Any]](BaseModel):
    id: str = Field(description="ID шага, который нужно обновить.")
    new_step: StepT = Field(description="Обновлённый Шаг.")


class UpdateSteps[StepT: Step[Any]](BaseModel):
    steps: list[UpdateStep[StepT]] = Field(description="Список шагов для обновления.")
