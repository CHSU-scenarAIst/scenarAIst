"""Сборка LLM-агента с инструментами и структурированным выводом.
Получение Json-Сценария (back_request).
JSON ответ агента:
    - Ручная сборка ответа в Json
    - Инструменты патчинга (частичного изменения) для редактирования Сценария
    - TODO? Structured output вместо ручной сборки
"""

import logging
import operator
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any

from langchain.messages import HumanMessage, SystemMessage
from langchain.tools import InjectedState, tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from pydantic import ValidationError

from src.agent.model import ScenarAIstModelFactory
from src.agent.schema import JsonResponse, Scenario, ScenarioStep

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig


LOGGER = logging.getLogger(__name__)


# ! [AI Note] Не добавлять в документацию
class OrchestratorState(MessagesState, total=False):
    """Состояние графа агента-Сценариста."""

    query: str
    system_prompt: str
    sources: dict[int, dict[str, str]]
    scenario: Scenario
    add_instruct: str
    steps_count: Annotated[int, operator.add]
    result: JsonResponse


# ! [AI Note] Не добавлять в документацию
class NodeEnum(StrEnum):
    """Имена узлов графа агента-Сценариста."""

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FORMAT = "format_node"


class ScenarAIstAgent:
    """Сборщик агента-Сценариста."""

    def __init__(self, model: ScenarAIstModelFactory):
        self._model = model
        self._checkpointer = None  # InMemorySaver() # ? SQLite/Postgres Checkpointer
        self._tools = [
            self.get_scenario,
            self.insert_step,
            self.update_step,
            self.delete_action,
        ]
        self._agent_llm = self._model.chat.bind_tools(self._tools)

        (name_get, name_add, name_update, name_delete) = (t.name for t in self._tools)
        tools_prompt = (
            "С помощью tools ты можешь управлять текущим Сценарием:"
            f"  1) получить текущее актуальное состояние Сценария - '{name_get}',"
            f"  2) добавлять Шаги в Сценарий после определённых id - '{name_add}',"
            f"  3) изменять существующие Шаги - '{name_update}',"
            f"  4) удалять Шаги по их id - '{name_delete}'."
        )

        self._model.chat_cfg.system_prompt = (
            f"<prompt>{self._model.chat_cfg.system_prompt}</prompt>"
            + f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"
            + f"<tools>{tools_prompt}</tools>"
        )

        LOGGER.debug(self._model.chat_cfg.model_dump_json())

    def build(self) -> None:
        """Сборка LLM-агента."""

        builder = StateGraph(OrchestratorState)

        builder.add_node(NodeEnum.CHAT, self._chat_node)
        builder.add_node(NodeEnum.FORMAT, self._format_node)

        if self._model.retrievers:
            builder.add_node(NodeEnum.RETRIEVE, self._retrieve_node)
            builder.add_edge(START, NodeEnum.RETRIEVE)
            builder.add_edge(NodeEnum.RETRIEVE, NodeEnum.CHAT)
        else:
            builder.add_edge(START, NodeEnum.CHAT)

        conditional_edges = [NodeEnum.FORMAT.value]
        if self._tools:
            tool_node = ToolNode(self._tools)
            builder.add_node(NodeEnum.TOOLS, tool_node)
            builder.add_edge(NodeEnum.TOOLS, NodeEnum.CHAT)
            conditional_edges.append(NodeEnum.TOOLS.value)

        builder.add_conditional_edges(NodeEnum.CHAT, self._router_node, conditional_edges)
        builder.add_edge(NodeEnum.FORMAT, END)

        self.agent = builder.compile(checkpointer=self._checkpointer)
        LOGGER.debug("Схема графа (Mermaid):\n%s", self.agent.get_graph().draw_mermaid())

    def invoke(self, text: str) -> JsonResponse:
        """Метод-обёртка (API) для отправки запросов LLM-агенту."""

        LOGGER.debug("'%s'", text)
        system_prompt = self._model.chat_cfg.system_prompt
        add_instruct = ""
        try:
            back_request = JsonResponse.model_validate_json(text)
        except ValidationError:
            LOGGER.debug("Запрос не является валидным 'JsonResponse'")
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
        }
        LOGGER.debug("Начальный state -- %s", state)

        run_cfg: RunnableConfig = {"configurable": {"thread_id": uuid.uuid4().hex}}
        response = self.agent.invoke(input=state, config=run_cfg)
        result = response["result"]
        return JsonResponse.model_validate(result)

    # ! [AI Note] Не добавлять в документацию
    def _retrieve_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел поиска релевантных документов по запросу. # ? NOTTODO доделать"""
        query = state["query"]
        docs = [doc for r in self._model.retrievers for doc in r.invoke(query)]
        LOGGER.info(
            "Контекст собран из %d документов:\n%s",
            len(docs),
            "\n".join(f"- {doc} [{len(doc.page_content)} симв.]" for doc in docs),
        )
        sources = {
            i: {
                "source": f"<source>{d.metadata.get('source', '-')}</source>",
                "content": f"<content>{d.page_content}</content>",
            }
            for i, d in enumerate(docs, start=1)
        }
        LOGGER.debug("%s -- %s", self._retrieve_node.__name__, sources)
        return {"sources": sources, "steps_count": 1}

    # ! [AI Note] Не добавлять в документацию
    def _chat_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел подготовки LLM. # TODO"""
        messages = state["messages"]
        system_prompt = state["system_prompt"]
        sources = state["sources"]
        system_prompt += f"<context>{sources}</context>"
        messages = [SystemMessage(system_prompt), *messages]
        response = self._agent_llm.invoke(messages)
        LOGGER.debug("'%s' -- '%s'", self._chat_node.__name__, response.content)
        return {
            # "messages": [response],
            "messages": [*messages, response],
            "steps_count": 1,
        }

    # ! [AI Note] Не добавлять в документацию
    def _router_node(self, state: OrchestratorState) -> str:
        """Ветвление графа."""
        messages = state["messages"]
        last_content = messages[-1].content if messages else ""
        tool_calls = getattr(last_content, "tool_calls", [])
        steps_count = state["steps_count"]
        if tool_calls and self._tools and steps_count < self._model.chat_cfg.max_steps:
            LOGGER.debug("[%s] -- %s -- %s", self._router_node.__name__, steps_count, NodeEnum.TOOLS)
            return NodeEnum.TOOLS
        LOGGER.debug("'%s' --> %s --> '%s'", self._router_node.__name__, steps_count, NodeEnum.FORMAT)
        return NodeEnum.FORMAT

    # ! [AI Note] Не добавлять в документацию
    def _format_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел финализации ответа в JSON-структуру."""
        messages = state["messages"]
        last_content = messages[-1].content if messages else ""
        result = JsonResponse(
            query=state["query"],
            answer=last_content,
            add_instruct=state["add_instruct"],
            sources=state["sources"],
            scenario=state["scenario"],
        )
        LOGGER.debug("'%s' -- \n%s", self._format_node.__name__, result)
        return {"result": result, "steps_count": 1}

    @tool
    def get_scenario(
        self,
        state: Annotated[OrchestratorState, InjectedState],
    ) -> Command:
        """Возвращает текущий Сценарий целиком с актуальными порядковыми номерами."""
        scenario = state["scenario"]
        steps = [
            step.model_copy(update={"order": order}) for order, step in enumerate(scenario.steps, start=1)
        ]
        LOGGER.debug("'%s' -- %d Шагов", self.get_scenario.__name__, len(steps))
        return Command(
            update={"steps_count": 1},
            value=steps,
        )

    @tool(parse_docstring=True)
    def insert_step(
        self,
        state: Annotated[OrchestratorState, InjectedState],
        steps: list[tuple[str | None, ScenarioStep]],
    ) -> Command:
        """Добавляет Шаги в Сценарий после указанных id Шагов.

        Args:
            steps: Список кортежей, где первый элемент — это 'id' шага (или None/пустая строка,
                если нужно добавить в самый конец), после которого нужно вставить новый шаг,
                а второй элемент — сам объект нового шага 'ScenarioStep'.
        """
        scenario = state["scenario"]
        used_ids = set(scenario._step_cache.keys())
        parsed: list[tuple[str, ScenarioStep]] = []
        for after_id, step in steps:
            if after_id and scenario.find(after_id) is None:
                LOGGER.warning("'%s' -- Шаг '%s' не найден, отмена", self.insert_step.__name__, after_id)
                return Command(
                    update={"steps_count": 1},
                    value=0,
                )
            parsed.append((after_id, scenario.with_unique_id(step, used_ids)))

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
        scenario.rebuild()

        LOGGER.info("'%s' -- добавлено: %d", self.insert_step.__name__, len(parsed))
        return Command(
            update={"scenario": scenario, "steps_count": 1},
            value=len(parsed),
        )

    @tool(parse_docstring=True)
    def update_step(
        self,
        state: Annotated[OrchestratorState, InjectedState],
        steps: list[tuple[str, ScenarioStep]],
    ) -> Command:
        """Изменяет существующие Шаги Сценария.

        Args:
            steps: Список кортежей, где первый элемент — это 'id' (id) существующего шага,
                который нужно обновить, а второй — объект 'ScenarioStep' с новыми данными.
        """
        scenario = state["scenario"]
        parsed: list[tuple[int, ScenarioStep]] = []
        for step_id, new_step in steps:
            index = scenario.find(step_id)
            if index is None:
                LOGGER.warning("'%s' -- Шаг '%s' не найден, отмена", self.update_step.__name__, step_id)
                return Command(
                    update={"steps_count": 1},
                    value=0,
                )
            parsed.append((index, new_step.model_copy(update={"id": step_id})))
        for index, new_step in parsed:
            scenario.steps[index] = new_step
        LOGGER.info("'%s' -- изменено: %d", self.update_step.__name__, len(parsed))
        return Command(
            update={"scenario": scenario, "steps_count": 1},
            value=len(parsed),
        )

    @tool(parse_docstring=True)
    def delete_action(
        self,
        state: Annotated[OrchestratorState, InjectedState],
        step_ids: set[str],
    ) -> Command:
        """Удаляет Шаги из Сценария.

        Args:
            step_ids: Множество уникальных ID шагов для удаления.
        """
        scenario = state["scenario"]
        missing = [i for i in step_ids if scenario.find(i) is None]
        if missing:
            LOGGER.warning("%s -- Шаги %s не найдены, отмена.", self.delete_action.__name__, missing)
            return Command(
                update={"steps_count": 1},
                value=0,
            )
        scenario.steps = [s for s in scenario.steps if s.id not in step_ids]
        scenario.rebuild()
        LOGGER.info("'%s' -- удалено: %d", self.delete_action.__name__, len(step_ids))
        return Command(
            update={"scenario": scenario, "steps_count": 1},
            value=len(step_ids),
        )
