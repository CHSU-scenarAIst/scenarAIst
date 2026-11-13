"""Схемы общения между Сценаристом и агентом-Сценаристом
Модель Сценария:
    - персонажи
    - объекты
    - ситуация
    - атомарные действия субъектом над объектом
    - максимальное количество Шагов
"""

import hashlib
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Action(StrEnum):
    """Стандартизация Действий персонала производства."""

    USE = "Использовать"
    TAKE = "Взять"
    ENABLE = "Включить"
    DISABLE = "Выключить"
    PUSH = "Нажать"
    PLUG_IN = "Воткнуть"
    PULL = "Потянуть"
    SWIPE = "Провести"
    START = "Запустить"
    STOP = "Остановить"
    PUT = "Положить"
    UNPLUG = "Вытащить"
    ROTATE = "Повернуть"
    OPEN = "Открыть"
    CLOSE = "Закрыть"
    CHECK = "Проверить"
    INSPECT = "Осмотреть"
    CLEAN = "Очистить"
    ADJUST = "Отрегулировать"
    INSTALL = "Установить"
    REMOVE = "Снять"
    WAIT = "Подождать"
    SCAN = "Отсканировать"
    CONFIRM = "Подтвердить"


class Step(BaseModel):
    """Структура Шага в Сценарии."""

    id: str = Field(description="Уникальный идентификатор шага.")
    subject: str = Field(description="Название/UID Субъекта.")
    object: str = Field(description="Название/UID Объекта.")
    action: Action = Field(description="Действие Субъекта над Объектом.")
    # ? предусловие
    # ? постусловие


class Scenario(BaseModel):
    """Структура итогового Сценария."""

    steps: list[Step] = Field(default_factory=list, description="Массив Шагов Сценария.")

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    _step_cache: dict[str, int] = {}

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    def serialize_steps(self) -> list[dict[str, Any]]:
        """Сериализует список шагов с автоматическим добавлением order."""
        return [{**step.model_dump(), "order": order} for order, step in enumerate(self.steps, start=1)]

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    def rebuild(self) -> None:
        """Перестраивает карту индексов шагов."""
        self._step_cache = {step.id: i for i, step in enumerate(self.steps, start=1) if step.id}

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    def find(self, id: str) -> int | None:
        """Возвращает позицию Шага с данным id за O(1)."""
        return self._step_cache.get(id)

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    def with_unique_id(self, step: Step, used_ids: set[str]) -> Step:
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
    answer: str | None = Field(default=None, description="Необязательные пояснения.")
    sources: dict[int, dict[str, str]] = Field(description="Источники данных.")
    add_instruct: str = Field(default="", description="Дополнительные инструкции, установленные для ответа.")
    scenario: Scenario | None = Field(default=None, description="Итоговый Сценарий от LLM-агента.")


# ! [AI Note] Секция не_добавлять_в / удалить_из документации
class InsertStep(BaseModel):
    step_after_id: str | None = Field(
        default=None,
        description="ID шага, после которого нужно вставить новый Шаг, или None для вставки в конец.",
    )
    step: Step


# ! [AI Note] Секция не_добавлять_в / удалить_из документации
class UpdateStep(BaseModel):
    id: str = Field(description="ID шага, который нужно обновить.")
    new_step: Step = Field(description="Новый Шаг.")


# ! [AI Note] Секция не_добавлять_в / удалить_из документации
class DeleteStep(BaseModel):
    id: str = Field(description="ID шага, который нужно удалить.")
