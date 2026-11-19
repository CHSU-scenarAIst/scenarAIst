"""Структура Сценария и схемы ответа агента-Сценариста."""

import logging
import operator
import uuid
from typing import Annotated, Self

from langchain.messages import AnyMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field, PrivateAttr, model_validator

LOGGER = logging.getLogger(__name__)


class Step[ActionT: str](BaseModel):
    """ШагСценария"""

    id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Уникальный идентификатор шага.",
    )
    actor: str = Field(description="Название/UID персонала.")
    target: str = Field(description="Название/UID составной части целевого объекта.")
    action: ActionT = Field(description="Стандартное действие персонала над целевым объектом или его частью.")
    # ? предусловие
    # ? постусловие


class Scenario(BaseModel):
    """Сценарий"""

    steps: list[Step[str]] = Field(default_factory=list, description="Массив Шагов Сценария.")


class AgentResponse(BaseModel):
    """ОтветАгента"""

    query: str = Field(default="", description="Исходный запрос агенту.")
    answer: str = Field(default="", description="Сообщение от агента.")
    sources: dict[int, dict[str, str]] = Field(default_factory=dict, description="Источники данных.")
    scenario: Scenario = Field(default_factory=Scenario, description="Итоговый Сценарий от агента.")

    @property
    def steps(self) -> list[Step[str]]:
        """Вернуть список Шагов из Сценария."""
        return self.scenario.steps

    @steps.setter
    def steps(self, value: list[Step[str]]) -> None:
        """Перезаписать Шаги."""
        self.scenario.steps = value
        self._rebuild_indexes()

    def find(self, id: str) -> int | None:
        """Вернуть индекс Шага в списке по его ID."""
        return self._steps_indexes.get(id)

    def count_steps(self) -> int:
        """Вернуть число Шагов в Сценарии."""
        return len(self._steps_indexes)

    def serialize(self) -> str:
        """Вернуть Сценарий с порядковыми номерами Шагов."""
        steps = [SerStep(**s.model_dump(), order=i) for i, s in enumerate(self.scenario.steps, start=1)]
        return SerializedResponse(
            query=self.query,
            answer=self.answer,
            sources=self.sources,
            steps=steps,
        ).model_dump_json(indent=2)

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    _steps_indexes: dict[str, int] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _post_init(self) -> Self:
        self._rebuild_indexes()
        return self

    def _rebuild_indexes(self) -> None:
        indexes: dict[str, int] = {}
        for i, s in enumerate(self.scenario.steps):
            if not s.id:
                continue
            if s.id in indexes:
                LOGGER.warning("Обнаружен дубликат id Шага '%s' (позиции %d и %d).", s.id, indexes[s.id], i)
                continue
            indexes[s.id] = i
        self._steps_indexes = indexes


class AgentState(BaseModel):
    """СостояниеАгента. База данных состояния агента-Сценариста."""

    messages: Annotated[list[AnyMessage], add_messages] = Field(
        default_factory=list, description="История общения с агентом."
    )
    response: AgentResponse = Field(default_factory=AgentResponse, description="Ответа агента.")
    invokes_count: Annotated[int, operator.add] = Field(default=0, description="Число вызовов агента.")
    invokes_max: int = Field(default=1, description="Максимальное число вызовов агента.")

    @classmethod
    def from_back_request(cls, task: str, instruct: str) -> Self:
        """Создать из существующего Сценария."""
        raw = SerializedResponse.model_validate_json(task)
        steps = [Step[str].model_validate(s.model_dump(exclude={"order"})) for s in raw.steps]
        response = AgentResponse(
            query=instruct,
            answer="Передан пустой Сценарий." if not steps else "",
            sources=raw.sources,
            scenario=Scenario(steps=steps),
        )
        return cls(response=response)

    @classmethod
    def from_task(cls, task: str) -> Self:
        response = AgentResponse(query=task)
        return cls(response=response)


# ! [AI Note] Секция не_добавлять_в / удалить_из документации
class SerStep(Step[str]):
    """Шаг для контракта API с явным полем order."""

    order: int


class SerializedResponse(BaseModel):
    """Контракт обмена данными по API."""

    query: str
    answer: str
    sources: dict[int, dict[str, str]]
    steps: list[SerStep]
