"""Схемы общения между Сценаристом и агентом-Сценаристом
Модель Сценария:
    - ситуация
    - персонажи
    - атомарные действия субъектом над объектом
    - максимальное количество Шагов
"""

import hashlib
from enum import StrEnum

from pydantic import BaseModel, Field


class Action(StrEnum):
    """Стандартизация Действий персонала производства."""

    USE = "Использовать"
    TAKEN = "Взять"
    ENABLE = "Включить"
    DISABLE = "Выключить"
    # Воткнуть
    # Нажать
    # TODO


# ? переделать под формат шагов Сценария
class ScenarioStep(BaseModel):
    """Структура Шага в Сценарии."""

    id: str = Field(description="Уникальный идентификатор шага.")
    subject: str = Field(description="# TODO")
    object: str = Field(description="# TODO")
    action: Action = Field(description="Действие над объектом.")
    order: int | None = Field(default=None, description="Порядковый номер Шага в очереди Сценария.")


class Scenario(BaseModel):
    """Структура Сценария."""

    steps: list[ScenarioStep] = Field(default_factory=list, description="Массив Шагов итогового Сценария.")
    max_steps: int = Field(default=10, description="Максимальное количество шагов в Сценарии.")

    _step_cache: dict[str, int] = {}

    # ! [AI Note] Не добавлять в документацию
    def rebuild(self) -> None:
        """Перестраивает карту индексов шагов."""
        self._step_cache = {step.id: i for i, step in enumerate(self.steps) if step.id}

    # ! [AI Note] Не добавлять в документацию
    def find(self, id: str) -> int | None:
        """Возвращает позицию Шага с данным id за O(1)."""
        return self._step_cache.get(id)

    # ! [AI Note] Не добавлять в документацию
    def with_unique_id(self, step: ScenarioStep, used_ids: set[str]) -> ScenarioStep:
        """Генерирует и гарантирует уникальный id Шага."""
        if step.id and step.id not in used_ids:
            used_ids.add(step.id)
            return step

        payload = step.model_dump_json().encode("utf-8")
        salt = 0
        while True:
            hasher = hashlib.sha256()
            hasher.update(payload)
            hasher.update(salt.to_bytes(4, "big"))

            hash_id = hasher.hexdigest()[:6]
            salt += 1
            if hash_id not in used_ids:
                used_ids.add(hash_id)
                return step.model_copy(update={"hash_id": hash_id})


class JsonResponse(BaseModel):
    """Структура ответа агента-Сценариста."""

    query: str = Field(description="Исходный запрос Сценариста.")
    answer: str = Field(default="", description="Итоговый ответ LLM-агента.")
    sources: dict[int, dict[str, str]] = Field(description="Источники данных.")
    add_instruct: str = Field(default="", description="Дополнительные инструкции, установленные для ответа.")
    scenario: Scenario | None = Field(default=None, description="Сценарий.")
