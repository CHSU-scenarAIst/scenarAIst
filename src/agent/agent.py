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
from src.agent.schema import DeleteStep, InsertStep, JsonResponse, Scenario, Step, UpdateStep

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

LOGGER = logging.getLogger(__name__)

LOG_PATTERN = "[%s] -- %s"
RETRIVE_NODE = "retrieve_node"
CHAT_NODE = "chat_node"
TOOL_NODE = "tool_node"
FORMAT_NODE = "format_node"


# ! Это и есть база данных!
class AgentState(MessagesState, total=False):
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
        self._tools = [get_scenario, insert_step, update_step, delete_action]
        self._agent_llm = model.chat.bind_tools(self._tools)
        self._system_prompt = (
            f"<prompt>{model.chat_cfg.system_prompt}</prompt>"
            f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"
            "<tools>Tool Usage Policy"
            "- **Scenario Creation:** Whenever the user asks to create, generate, or build a scenario, "
            "you **MUST** use the available tools."
            "- **No Direct Generation:** Never write an answer directly in your text response "
            "without executing the corresponding tool call first."
            "- **Workflow:** Analyze the user's request -> Select the relevant tool(s) ->"
            " Execute the tool call -> Formulate your final response based strictly on the tool's output."
            "</tools>"
        )
        self._retrievers = model.retrievers

        LOGGER.info(model.chat_cfg.model_dump_json())

    def build(self) -> None:
        """Сборка LLM-агента."""

        builder = StateGraph(AgentState)

        builder.add_node(CHAT_NODE, self._chat_node)
        builder.add_node(FORMAT_NODE, self._format_node)

        if self._retrievers:
            builder.add_node(RETRIVE_NODE, self._retrieve_node)
            builder.add_edge(START, RETRIVE_NODE)
            builder.add_edge(RETRIVE_NODE, CHAT_NODE)
        else:
            builder.add_edge(START, CHAT_NODE)

        conditional_edges = [FORMAT_NODE]
        if self._tools:
            tool_node = ToolNode(self._tools)
            builder.add_node(TOOL_NODE, tool_node)
            builder.add_edge(TOOL_NODE, CHAT_NODE)
            conditional_edges.append(TOOL_NODE)

        builder.add_conditional_edges(CHAT_NODE, self._router_node, conditional_edges)
        builder.add_edge(FORMAT_NODE, END)

        self._checkpointer = None  # InMemorySaver() # ? SQLite/Postgres Checkpointer
        self.agent = builder.compile(checkpointer=self._checkpointer)
        LOGGER.info("Схема графа (Mermaid):\n%s", self.agent.get_graph().draw_mermaid())

    def invoke(self, text: str, max_steps: int = 10) -> JsonResponse:
        """API для отправки запросов LLM-агенту."""

        LOGGER.info(LOG_PATTERN, "Новый запрос", text)
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

        state: AgentState = {
            "messages": [HumanMessage(text)],
            "query": text,
            "system_prompt": system_prompt,
            "sources": {},
            "scenario": Scenario(),
            "add_instruct": add_instruct,
            "steps_count": 0,
            "max_steps": max_steps,
        }
        LOGGER.info(LOG_PATTERN, "Начальный state", state)

        run_cfg: RunnableConfig = {"configurable": {"thread_id": uuid.uuid4().hex}}
        response = self.agent.invoke(input=state, config=run_cfg)
        result = response["result"]
        return JsonResponse.model_validate(result)

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    def _retrieve_node(self, state: AgentState) -> dict[str, Any]:
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
        LOGGER.info(LOG_PATTERN, RETRIVE_NODE, sources)
        return {"steps_count": 1, "sources": sources}

    def _chat_node(self, state: AgentState) -> dict[str, Any]:
        """Узел генерации ответа агентом."""
        system_prompt = f"{state['system_prompt']}<context>{state['sources']}</context>"
        prompt_messages = [SystemMessage(system_prompt), *state["messages"]]
        response = self._agent_llm.invoke(prompt_messages)
        LOGGER.info(LOG_PATTERN, CHAT_NODE, response.content)
        return {"steps_count": 1, "messages": [response]}

    def _router_node(self, state: AgentState) -> str:
        """Ветвление графа."""
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        tool_calls = getattr(last_message, "tool_calls", [])
        steps_count = state["steps_count"]
        if tool_calls and self._tools and steps_count < state["max_steps"]:
            LOGGER.info("[%s] --> [%s]", steps_count, TOOL_NODE)
            return TOOL_NODE
        LOGGER.info("[%s] --> [%s]", steps_count, FORMAT_NODE)
        return FORMAT_NODE

    def _format_node(self, state: AgentState) -> dict[str, Any]:
        """Узел финализации ответа в JSON-структуру."""
        last_message = state["messages"][-1]
        result = JsonResponse(
            query=state["query"],
            answer=str(last_message.content),
            add_instruct=state["add_instruct"],
            sources=state["sources"],
            scenario=state["scenario"],
        )
        LOGGER.info(LOG_PATTERN, FORMAT_NODE, result)
        return {"result": result, "steps_count": 1}

    # !


@tool
def get_scenario(runtime: ToolRuntime[None, AgentState]) -> Command[tuple[()]]:
    """Получить текущее актуальное состояние Сценария с порядковыми номерами шагов."""
    scenario = runtime.state["scenario"].model_copy(deep=True)
    steps = scenario.serialize_steps()
    mes = f"Current Scenario steps: {steps}."
    LOGGER.info(LOG_PATTERN, get_scenario.name, mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=runtime.tool_call_id)
    return Command(update={"steps_count": 1, "messages": [tool_mes]})


@tool
def insert_step(runtime: ToolRuntime[None, AgentState], steps: list[InsertStep]) -> Command[tuple[()]]:
    """Добавить Шаги в Сценарий после указанных id Шагов."""
    scenario = runtime.state["scenario"].model_copy(deep=True)
    used_ids = set(scenario._step_cache.keys())
    parsed: list[tuple[str, Step]] = []
    for s in steps:
        if s.step_after_id and scenario.find(s.step_after_id):
            parsed.append((s.step_after_id, scenario.with_unique_id(s.step, used_ids)))
            continue

        if not s.step_after_id:
            parsed.append(("1", scenario.with_unique_id(s.step, used_ids)))
            continue

        mes = f"Warning: step '{s.step_after_id}' not found. Canceled."
        LOGGER.warning(LOG_PATTERN, insert_step.name, mes)
        tool_mes = ToolMessage(content=mes, tool_call_id=runtime.tool_call_id)
        return Command(update={"steps_count": 1, "messages": [tool_mes]})

    indexed_inserts: list[tuple[int, Step]] = []
    append_steps: list[Step] = []
    inserted_counters: dict[str, int] = {}
    for after_id, step in parsed:
        if after_id and (base_idx := scenario.find(after_id)):
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

    mes = f"Inserted: {len(parsed)}"
    LOGGER.info(LOG_PATTERN, insert_step.name, mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=runtime.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [tool_mes]})


@tool
def update_step(runtime: ToolRuntime[None, AgentState], steps: list[UpdateStep]) -> Command[tuple[()]]:
    """Изменить существующие Шаги Сценария."""
    scenario = runtime.state["scenario"].model_copy(deep=True)
    parsed: list[tuple[int, Step]] = []
    for s in steps:
        index = scenario.find(s.id)
        if index is None:
            mes = f"Updated: {0}, '{index}' not found. Canceled."
            LOGGER.warning(LOG_PATTERN, update_step.name, mes)
            tool_mes = ToolMessage(content=mes, tool_call_id=runtime.tool_call_id)
            return Command(update={"steps_count": 1, "messages": [tool_mes]})
        parsed.append((index, s.new_step.model_copy(update={"id": s.id})))

    for index, new_step in parsed:
        scenario.steps[index] = new_step

    mes = f"Updated: {len(parsed)}."
    LOGGER.info(LOG_PATTERN, update_step.name, mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=runtime.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [tool_mes]})


@tool
def delete_action(runtime: ToolRuntime[None, AgentState], steps: list[DeleteStep]) -> Command[tuple[()]]:
    """Удалить Шаги из Сценария по их ids."""
    scenario = runtime.state["scenario"].model_copy(deep=True)
    missing = [ds for ds in steps if scenario.find(ds.id) is None]
    if missing:
        mes = f"Deleted: {len(steps)}, missing: {len(steps)}. Canceled."
        LOGGER.warning(LOG_PATTERN, delete_action.name, mes)
        tool_mes = ToolMessage(content=mes, tool_call_id=runtime.tool_call_id)
        return Command(update={"steps_count": 1, "messages": [tool_mes]})

    scenario.steps = [s for s in scenario.steps if s.id not in [ds.id for ds in steps]]
    scenario.rebuild()

    mes = f"Deleted: {len(steps)}."
    LOGGER.info(LOG_PATTERN, delete_action.name, mes)
    tool_mes = ToolMessage(content=mes, tool_call_id=runtime.tool_call_id)
    return Command(update={"steps_count": 1, "scenario": scenario, "messages": [tool_mes]})
