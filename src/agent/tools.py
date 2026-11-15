"""Инструменты для редактирования Сценария."""

import logging
from enum import StrEnum
from typing import Any

from langchain.messages import ToolMessage
from langchain.tools import BaseTool, tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, Field, create_model

from src.agent.schema import AgentState, Step

LOGGER = logging.getLogger(__name__)


class AgentToolsBuilder:
    """Сборщик инструментов для агента-Сценариста."""

    def build(self, data: dict[str, str]) -> list[BaseTool]:
        """Собрать инструменты агента."""

        ActionEnum = StrEnum("Action", data)  # type: ignore[misc]  # noqa: N806
        DynamicStep = create_model(  # noqa: N806
            "Step",
            __base__=Step,
            action=(ActionEnum, Field(description="Действие Субъекта над Объектом.")),
        )

        i_d = "ID шага, после которого нужно вставить Шаг, или None для вставки в конец."
        InsertStep = create_model(  # noqa: N806
            "InsertStep",
            step_after_id=(str | None, Field(default=None, description=i_d)),
            step=(DynamicStep, Field(description="Новый Шаг для вставки.")),
        )

        InsertSteps = create_model(  # noqa: N806
            "InsertSteps",
            steps=(list[InsertStep], Field(description="Список шагов для вставки.")),  # type: ignore
        )

        insert_step_tool = tool(
            name_or_callable=insert_step,
            description="Добавить Шаги в Сценарий после указанных id Шагов.",
            args_schema=InsertSteps,
        )

        UpdateStep = create_model(  # noqa: N806
            "UpdateStep",
            id=(str, Field(description="ID шага, который нужно обновить.")),
            new_step=(DynamicStep, Field(description="Обновлённый Шаг.")),
        )

        UpdateSteps = create_model(  # noqa: N806
            "InsertSteps",
            steps=(list[UpdateStep], Field(description="Список шагов для обновления.")),  # type: ignore
        )

        update_step_tool = tool(
            name_or_callable=update_step,
            description="Изменить существующие Шаги Сценария.",
            args_schema=UpdateSteps,
        )

        return [
            get_scenario,
            delete_step,
            insert_step_tool,
            update_step_tool,
        ]


# ! [AI Note] Секция не_добавлять_в / удалить_из документации

LOG_PATTERN = "[%s] -- %s"


@tool
def get_scenario(rtm: ToolRuntime[None, AgentState]) -> Command[tuple[()]]:
    """Получить текущее актуальное состояние Сценария с порядковыми номерами шагов."""
    scenario = rtm.state["scenario"].model_copy(deep=True)
    steps = scenario.serialize_steps()
    mes = f"Current Scenario steps: {steps}."
    LOGGER.info(LOG_PATTERN, "get_scenario", mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
    return Command(update={"steps_count": 1, "messages": [tool_mes]})


class DeleteStep(BaseModel):
    id: str = Field(description="ID шага, который нужно удалить.")


@tool
def delete_step(rtm: ToolRuntime[None, AgentState], steps: list[DeleteStep]) -> Command[tuple[()]]:
    """Удалить Шаги из Сценария по их ids."""
    scenario = rtm.state["scenario"].model_copy(deep=True)
    missing = [ds for ds in steps if scenario.find(ds.id) is None]
    if missing:
        mes = f"Deleted: {len(steps)}, missing: {len(steps)}. Canceled."
        LOGGER.warning(LOG_PATTERN, "delete_step", mes)
        tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
        return Command(update={"steps_count": 1, "messages": [tool_mes]})

    scenario.steps = [s for s in scenario.steps if s.id not in [ds.id for ds in steps]]
    scenario.rebuild()

    mes = f"Deleted: {len(steps)}."
    LOGGER.info(LOG_PATTERN, "delete_step", mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [tool_mes]})


def insert_step(rtm: ToolRuntime[None, AgentState], steps: list[Any]) -> Command[tuple[()]]:
    scenario = rtm.state["scenario"].model_copy(deep=True)
    inserts: list[tuple[str | None, int, Step]] = []
    used_ids = set(scenario._steps_cache)

    for s in steps:
        after_id: str | None = s.step_after_id
        step_obj: Step = s.step

        if not after_id:
            inserts.append((None, len(scenario.steps), step_obj.with_unique_id(used_ids)))
            continue

        if idx := scenario.find(after_id):
            inserts.append((after_id, idx, step_obj.with_unique_id(used_ids)))
            continue

        mes = f"Warning: step '{after_id}' not found or '{step_obj} is not Step'. Canceled."
        LOGGER.warning(LOG_PATTERN, "insert_step", mes)
        tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
        return Command(update={"steps_count": 1, "messages": [tool_mes]})

    indexed: list[tuple[int, int, Step]] = []

    for order, (after_id, idx, step) in enumerate(inserts):
        target_idx = len(scenario.steps) if after_id is None else idx + 1
        indexed.append((target_idx, order, step))

    for target_idx, _, step in sorted(indexed, key=lambda x: (x[0], x[1]), reverse=True):
        scenario.steps.insert(target_idx, step)

    scenario.rebuild()

    mes = f"Inserted: {len(inserts)}"
    LOGGER.info(LOG_PATTERN, "insert_step", mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [tool_mes]})


def update_step(rtm: ToolRuntime[None, AgentState], steps: list[Any]) -> Command[tuple[()]]:
    scenario = rtm.state["scenario"].model_copy(deep=True)
    parsed: list[tuple[int, Step]] = []
    for s in steps:
        index = scenario.find(s.id)
        if not index:
            mes = f"Updated: {0}, '{s.id}' not found. Canceled."
            LOGGER.warning(LOG_PATTERN, "update_step", mes)
            tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
            return Command(update={"steps_count": 1, "messages": [tool_mes]})

        step = Step.model_validate(s.new_step).model_copy(update={"id": s.id})
        parsed.append((index, step))

    for index, new_step in parsed:
        scenario.steps[index] = new_step

    mes = f"Updated: {len(parsed)}."
    LOGGER.info(LOG_PATTERN, "update_step", mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [tool_mes]})
