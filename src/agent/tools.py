"""Инструменты для редактирования Сценария."""

import logging
from enum import StrEnum
from typing import Any

from langchain.messages import ToolMessage
from langchain.tools import BaseTool, tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from src.agent.schema import (
    AgentState,
    DeleteStep,
    InsertStep,
    InsertSteps,
    Step,
    StepType,
    UpdateStep,
    UpdateSteps,
)

LOGGER = logging.getLogger(__name__)


class AgentToolsBuilder:
    """Сборщик инструментов для агента-Сценариста."""

    def build(self, data: dict[str, str]) -> list[BaseTool]:
        """Собрать инструменты агента."""

        ActionT = StrEnum("Action", data)  # type: ignore[misc]  # noqa: N806
        DynamicStep = Step[ActionT]  # noqa: N806

        insert_step_tool = tool(name_or_callable=insert_step, args_schema=InsertSteps[DynamicStep])
        update_step_tool = tool(name_or_callable=update_step, args_schema=UpdateSteps[DynamicStep])

        return [
            tool(get_scenario),
            tool(delete_step),
            insert_step_tool,
            update_step_tool,
        ]


LOG_PATTERN = "[%s] -- %s"


def get_scenario(rtm: ToolRuntime[None, AgentState]) -> Command[Any]:
    """Получить текущее актуальное состояние Сценария с порядковыми номерами шагов."""

    scenario = rtm.state["scenario"].model_copy(deep=True)
    steps = scenario.serialize_steps()
    mes = f"Current Scenario steps: {steps}."
    LOGGER.info(LOG_PATTERN, "get_scenario", mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
    return Command(update={"steps_count": 1, "messages": [tool_mes]})


def delete_step(rtm: ToolRuntime[None, AgentState], steps: list[DeleteStep]) -> Command[Any]:
    """Удалить Шаги из Сценария по их ids."""

    scenario = rtm.state["scenario"].model_copy(deep=True)
    missing = [ds for ds in steps if scenario.find(ds.id) is None]
    if missing:
        mes = f"Not found: {[i.id for i in missing]} steps.id. Canceled."
        LOGGER.warning(LOG_PATTERN, "delete_step", mes)
        tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
        return Command(update={"steps_count": 1, "messages": [tool_mes]})

    ids_to_delete = {ds.id for ds in steps}
    scenario.steps = [s for s in scenario.steps if s.id not in ids_to_delete]
    scenario.rebuild_indexes()

    mes = f"Deleted: {len(steps)}."
    LOGGER.info(LOG_PATTERN, "delete_step", mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [tool_mes]})


def insert_step(rtm: ToolRuntime[None, AgentState], steps: list[InsertStep[StepType]]) -> Command[Any]:
    "Добавить Шаги в Сценарий после указанных id Шагов."

    scenario = rtm.state["scenario"].model_copy(deep=True)
    inserts: list[tuple[str | None, int, StepType]] = []

    for s in steps:
        step_obj = StepType(**s.step.model_dump())

        if not s.step_after_id:
            inserts.append((None, len(scenario.steps), step_obj))
            continue

        if (idx := scenario.find(s.step_after_id)) is not None:
            inserts.append((s.step_after_id, idx, step_obj))
            continue

        mes = f"Warning: step '{s.step_after_id}' not found or '{step_obj} is not Step'. Canceled."
        LOGGER.warning(LOG_PATTERN, "insert_step", mes)
        tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
        return Command(update={"steps_count": 1, "messages": [tool_mes]})

    indexed: list[tuple[int, int, StepType]] = []

    for order, (after_id, idx, step) in enumerate(inserts):
        target_idx = len(scenario.steps) if after_id is None else idx + 1
        indexed.append((target_idx, order, step))

    for target_idx, _, step in sorted(indexed, key=lambda x: (x[0], x[1]), reverse=True):
        scenario.steps.insert(target_idx, step)

    scenario.rebuild_indexes()

    mes = f"Inserted: {len(inserts)}"
    LOGGER.info(LOG_PATTERN, "insert_step", mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [tool_mes]})


def update_step(rtm: ToolRuntime[None, AgentState], steps: list[UpdateStep[StepType]]) -> Command[Any]:
    "Изменить существующие Шаги Сценария."

    scenario = rtm.state["scenario"].model_copy(deep=True)
    parsed: list[tuple[int, StepType]] = []
    for s in steps:
        index = scenario.find(s.id)
        if index is None:
            mes = f"Updated: {0}, '{s.id}' not found. Canceled."
            LOGGER.warning(LOG_PATTERN, "update_step", mes)
            tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
            return Command(update={"steps_count": 1, "messages": [tool_mes]})

        step_obj = StepType(
            id=s.id,
            actor=s.new_step.actor,
            target=s.new_step.target,
            action=s.new_step.action,
        )
        parsed.append((index, step_obj))

    for index, step in parsed:
        scenario.steps[index] = step

    mes = f"Updated: {len(parsed)}."
    LOGGER.info(LOG_PATTERN, "update_step", mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=rtm.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [tool_mes]})
