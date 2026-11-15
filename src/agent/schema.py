"""Схемы общения между Сценаристом и агентом-Сценаристом"""

import hashlib
import operator
from typing import Annotated, Any, Self

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class Step(BaseModel):
    """Структура Шага в Сценарии."""

    id: str = Field(description="Уникальный идентификатор шага.")
    actor: str = Field(description="Название/UID персонала.")
    target: str = Field(description="Название/UID целевого объекта.")
    action: str = Field(description="Действие персонала над целевым объектом.")
    # ? предусловие
    # ? постусловие

    def with_unique_id(self, used_ids: set[str]) -> Self:
        """Генерирует и гарантирует уникальный id Шага."""
        if self.id and self.id not in used_ids:
            used_ids.add(self.id)
            return self

        payload = self.model_dump_json().encode("utf-8")
        salt = 0
        while True:
            hasher = hashlib.sha256()
            hasher.update(payload)
            hasher.update(salt.to_bytes(4, "big"))

            hash_id = hasher.hexdigest()[:6]
            salt += 1
            if hash_id not in used_ids:
                used_ids.add(hash_id)
                return self.model_copy(update={"hash_id": hash_id})


class Scenario(BaseModel):
    """Структура итогового Сценария."""

    steps: list[Step] = Field(default_factory=list, description="Массив Шагов Сценария.")

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    _steps_cache: dict[str, int] = {}

    def serialize_steps(self) -> list[dict[str, Any]]:
        return [{**s.model_dump(), "order": i} for i, s in enumerate(self.steps, start=1)]

    def rebuild(self) -> None:
        self._steps_cache = {s.id: i for i, s in enumerate(self.steps, start=1) if s.id}

    def find(self, id: str) -> int | None:
        return self._steps_cache.get(id)


class AgentResponse(BaseModel):
    """Структура ответа агента-Сценариста."""

    query: str = Field(description="Исходный запрос Сценариста.")
    answer: str | None = Field(default=None, description="Необязательные пояснения.")
    sources: dict[int, dict[str, str]] = Field(description="Источники данных.")
    add_instruct: str = Field(default="", description="Дополнительные инструкции, установленные для ответа.")
    scenario: Scenario | None = Field(default=None, description="Итоговый Сценарий от LLM-агента.")


# ! База данных состояния агента-Сценариста между запусками
class AgentState(MessagesState, total=False):
    """Состояние агента-Сценариста."""

    query: str
    # system_prompt: str
    sources: dict[int, dict[str, str]]
    scenario: Scenario
    add_instruct: str
    steps_count: Annotated[int, operator.add]
    max_invokes: int
    result: AgentResponse
