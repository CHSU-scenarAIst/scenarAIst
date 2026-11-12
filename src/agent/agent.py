"""Сборка LLM-агента с инструментами и структурированным выводом.
- Получение Json-Сценария на вход (back_request).
- Ручная сборка ответа в Json
- Инструменты патчинга (частичного изменения) для редактирования Сценария
"""

import logging
import operator
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, ToolRuntime
from langgraph.types import Command
from pydantic import ValidationError

from src.agent.model import ScenarAIstModelFactory
from src.agent.schema import (
    DeleteStepItem,
    InsertStepItem,
    JsonResponse,
    Scenario,
    ScenarioStep,
    UpdateStepItem,
)

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig


LOGGER = logging.getLogger(__name__)


# ? Это и есть база данных!
class OrchestratorState(MessagesState, total=False):
    """Состояние агента-Сценариста."""

    query: str
    system_prompt: str
    sources: dict[int, dict[str, str]]
    scenario: Scenario
    add_instruct: str
    steps_count: Annotated[int, operator.add]
    max_steps: int
    result: JsonResponse


class ScenarAIstAgent:
    """Сборщик агента-Сценариста."""

    def __init__(self, model: ScenarAIstModelFactory):
        self._checkpointer = None  # InMemorySaver() # ? SQLite/Postgres Checkpointer
        self._tools = [get_scenario, insert_step, update_step, delete_action]
        self._agent_llm = model.chat.bind_tools(self._tools)
        self._system_prompt = (
            f"<prompt>{model.chat_cfg.system_prompt}</prompt>"
            + f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"
        )
        self._retrievers = model.retrievers

        LOGGER.info(model.chat_cfg.model_dump_json())

    def build(self) -> None:
        """Сборка LLM-агента."""

        builder = StateGraph(OrchestratorState)

        builder.add_node("chat_node", self._chat_node)
        builder.add_node("format_node", self._format_node)

        if self._retrievers:
            builder.add_node("retrieve_node", self._retrieve_node)
            builder.add_edge(START, "retrieve_node")
            builder.add_edge("retrieve_node", "chat_node")
        else:
            builder.add_edge(START, "chat_node")

        conditional_edges = ["format_node"]
        if self._tools:
            tool_node = ToolNode(self._tools)
            builder.add_node("tool_node", tool_node)
            builder.add_edge("tool_node", "chat_node")
            conditional_edges.append("tool_node")

        builder.add_conditional_edges("chat_node", self._router_node, conditional_edges)
        builder.add_edge("format_node", END)

        self.agent = builder.compile(checkpointer=self._checkpointer)
        LOGGER.info("Схема графа (Mermaid):\n%s", self.agent.get_graph().draw_mermaid())

    def invoke(self, text: str, max_steps: int = 10) -> JsonResponse:
        """Метод-обёртка (API) для отправки запросов LLM-агенту."""

        LOGGER.info("'%s'", text)
        system_prompt = self._system_prompt
        add_instruct = ""
        try:
            back_request = JsonResponse.model_validate_json(text)
        except ValidationError:
            LOGGER.info("Запрос не является обратным ответом агента-Сценариста.")
        else:
            text = back_request.query
            add_instruct = back_request.add_instruct
            system_prompt += f"<add_instruct>{add_instruct}</add_instruct>"

        state: OrchestratorState = {
            "messages": [HumanMessage(text)],
            "query": text,
            "system_prompt": system_prompt,
            "sources": {},
            "scenario": Scenario(),
            "add_instruct": add_instruct,
            "steps_count": 0,
            "max_steps": max_steps,
        }
        LOGGER.info("Начальный state -- %s", state)

        run_cfg: RunnableConfig = {"configurable": {"thread_id": uuid.uuid4().hex}}
        response = self.agent.invoke(input=state, config=run_cfg)
        result = response["result"]
        return JsonResponse.model_validate(result)

    # ! [AI Note] Не добавлять в документацию
    def _retrieve_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел поиска релевантных документов по запросу. # ? NOTTODO доделать"""
        query = state["query"]
        docs = [doc for r in self._retrievers for doc in r.invoke(query)]
        LOGGER.info(
            "Контекст собран из %d документов:\n%s",
            len(docs),
            "\n".join(f"- {d} [{len(d.page_content)} симв.]" for d in docs),
        )
        sources = {
            i: {
                "source": f"<source>{d.metadata.get('source', '-')}</source>",
                "content": f"<content>{d.page_content}</content>",
            }
            for i, d in enumerate(docs, start=1)
        }
        LOGGER.info("%s -- %s", self._retrieve_node.__name__, sources)
        return {"steps_count": 1, "sources": sources}

    # ! [AI Note] Не добавлять в документацию
    def _chat_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел подготовки LLM. # TODO"""
        system_prompt = f"{state['system_prompt']}<context>{state['sources']}</context>"
        prompt_messages = [SystemMessage(system_prompt), *state["messages"]]
        response = self._agent_llm.invoke(prompt_messages)
        LOGGER.info("'%s' -- '%s'", self._chat_node.__name__, response.content)
        return {"steps_count": 1, "messages": [response]}

    # ! [AI Note] Не добавлять в документацию
    def _router_node(self, state: OrchestratorState) -> str:
        """Ветвление графа."""
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        tool_calls = getattr(last_message, "tool_calls", [])
        steps_count = state["steps_count"]
        if tool_calls and self._tools and steps_count < state["max_steps"]:
            LOGGER.info("[%s] -- %s -- %s", self._router_node.__name__, steps_count, "tool_node")
            return "tool_node"
        LOGGER.info("'%s' --> %s --> '%s'", self._router_node.__name__, steps_count, "format_node")
        return "format_node"

    # ! [AI Note] Не добавлять в документацию
    def _format_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел финализации ответа в JSON-структуру."""
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        result = JsonResponse(
            query=state["query"],
            answer=last_message.content,
            add_instruct=state["add_instruct"],
            sources=state["sources"],
            scenario=state["scenario"],
        )
        LOGGER.info("'%s' -- \n%s", self._format_node.__name__, result)
        return {"result": result, "steps_count": 1}


# TODO доработать сообшения об ошибках


@tool
def get_scenario(runtime: ToolRuntime[None, OrchestratorState]) -> Command:
    """Получить текущее актуальное состояние Сценария с порядковыми номерами шагов."""
    scenario = runtime.state["scenario"].model_copy(deep=True)
    steps = scenario.serialize_steps()
    LOGGER.info("'%s' -- %d Шагов", get_scenario.name, len(steps))
    mes = ToolMessage(content=str(steps), tool_call_id=runtime.tool_call_id)
    return Command(update={"steps_count": 1, "messages": [mes]})


@tool
def insert_step(runtime: ToolRuntime[None, OrchestratorState], steps: list[InsertStepItem]) -> Command:
    """Добавить Шаги в Сценарий после указанных id Шагов."""
    scenario = runtime.state["scenario"].model_copy(deep=True)
    used_ids = set(scenario._step_cache.keys())
    parsed: list[tuple[str, ScenarioStep]] = []
    for s in steps:
        if s.after_id and scenario.find(s.after_id) is None:
            LOGGER.warning("'%s' -- Шаг '%s' не найден, отмена.", insert_step.name, s.after_id)
            err_mes = ToolMessage(
                content=f"Error: step '{s.after_id}' not found. Nothing inserted.",
                tool_call_id=runtime.tool_call_id,
            )
            return Command(update={"steps_count": 1, "messages": [err_mes]})
        parsed.append((s.after_id, scenario.with_unique_id(s.step, used_ids)))

    indexed_inserts: list[tuple[int, ScenarioStep]] = []
    append_steps: list[ScenarioStep] = []
    inserted_counters: dict[str, int] = {}
    for after_id, step in parsed:
        if after_id:
            base_idx = scenario.find(after_id)
            shift = inserted_counters.get(after_id, 0)
            inserted_counters[after_id] = shift + 1
            indexed_inserts.append((base_idx + 1 + shift, step))
        else:
            append_steps.append(step)

    new_steps = list(scenario.steps)
    for target_idx, step in sorted(indexed_inserts, key=lambda x: x[0]):
        new_steps.insert(target_idx, step)

    new_steps.extend(append_steps)
    scenario.steps = new_steps
    scenario.rebuild()

    LOGGER.info("'%s' -- добавлено: %d", insert_step.name, len(parsed))
    mes = ToolMessage(content=f"Inserted: {len(parsed)}", tool_call_id=runtime.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [mes]})


@tool
def update_step(runtime: ToolRuntime[None, OrchestratorState], steps: list[UpdateStepItem]) -> Command:
    """Изменить существующие Шаги Сценария."""
    scenario = runtime.state["scenario"].model_copy(deep=True)
    parsed: list[tuple[int, ScenarioStep]] = []
    for s in steps:
        index = scenario.find(s.step_id)
        if index is None:
            LOGGER.warning("'%s' -- Шаг '%s' не найден, отмена", update_step.name, s.step_id)
            err_mes = ToolMessage(content=f"Updated: {0}", tool_call_id=runtime.tool_call_id)
            return Command(update={"steps_count": 1, "messages": [err_mes]})
        parsed.append((index, s.new_step.model_copy(update={"id": s.step_id})))

    for index, new_step in parsed:
        scenario.steps[index] = new_step

    LOGGER.info("'%s' -- изменено: %d", update_step.name, len(parsed))
    mes = ToolMessage(content=f"Updated: {len(parsed)}", tool_call_id=runtime.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [mes]})


@tool
def delete_action(runtime: ToolRuntime[None, OrchestratorState], step_ids: list[DeleteStepItem]) -> Command:
    """Удалить Шаги из Сценария по их ids."""
    scenario = runtime.state["scenario"].model_copy(deep=True)
    missing = [i for i in step_ids if scenario.find(i) is None]
    if missing:
        LOGGER.warning("%s -- Шаги %s не найдены, отмена.", delete_action.name, missing)
        err_mes = ToolMessage(content=f"Deleted: {0}", tool_call_id=runtime.tool_call_id)
        return Command(update={"steps_count": 1, "messages": [err_mes]})

    scenario.steps = [s for s in scenario.steps if s.id not in step_ids]
    scenario.rebuild()

    LOGGER.info("'%s' -- удалено: %d", delete_action.name, len(step_ids))
    mes = ToolMessage(content=f"Deleted: {len(step_ids)}", tool_call_id=runtime.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [mes]})
