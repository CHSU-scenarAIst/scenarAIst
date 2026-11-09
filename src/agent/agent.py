import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

from langchain.messages import HumanMessage, SystemMessage
from langchain.tools import InjectedState, tool
from langgraph.graph import END, START
from langgraph.graph.state import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from pydantic import ValidationError

# from langgraph.checkpoint.memory import InMemorySaver
# from langchain_tavily import TavilySearch
from src.agent.model import ScenarAIstModelFactory
from src.agent.state import JsonResponse, NodeEnum, OrchestratorState, Scenario, ScenarioStep

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig


LOGGER = logging.getLogger(__name__)


class ScenarAIstAgent:
    """Сборщик агента-Сценариста с инструментами и источниками знаний."""

    def __init__(self, model: ScenarAIstModelFactory):
        self._model = model

        # ? SQLite/Postgres Checkpointer
        # self.checkpointer = InMemorySaver()
        self._checkpointer = None

        self._tools = [
            self.get_scenario,
            self.insert_step,
            self.update_step,
            self.delete_action,
        ]
        self._tools_llm = self._model.chat.bind_tools(self._tools)
        self._tool_node = ToolNode(self._tools)

        (name_get, name_add, name_update, name_delete) = (tool_item.name for tool_item in self._tools)
        tools_prompt = (
            "При работе с tools всегда считай их результат истинным и окончательным."
            " С помощью tools ты можешь управлять текущим Сценарием:"
            f"  1) получить текущий Сценарий целиком - '{name_get}',"
            f"  2) добавлять Шаги в Сценарий после определённых hash-id - '{name_add}',"
            f"  3) изменять существующие Шаги - '{name_update}',"
            f"  4) удалять Шаги по их hash-id - '{name_delete}'."
            f" Прежде чем менять Сценарий, всегда получай его актуальное состояние"
            f" через '{name_get}', чтобы знать существующие hash-id Шагов."
        )

        self._model.chat_cfg.system_prompt = (
            "<prompt>"
            + self._model.chat_cfg.system_prompt
            + "</prompt>"
            + f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"
            + "<tools>"
            + tools_prompt
            + "</tools>"
        )

        LOGGER.debug(self._model.chat_cfg.model_dump_json())

    def build(self) -> None:
        """Сборка LLM-агента."""

        builder = StateGraph(OrchestratorState)

        builder.add_node(NodeEnum.CHAT, self._chat_node)
        builder.add_node(NodeEnum.FORMAT, self._format_node)

        if self._model.retrievers:
            builder.add_edge(START, NodeEnum.RETRIEVE)
            builder.add_node(NodeEnum.RETRIEVE, self._retrieve_node)
            builder.add_edge(NodeEnum.RETRIEVE, NodeEnum.CHAT)
        else:
            builder.add_edge(START, NodeEnum.CHAT)

        conditional_edges = [NodeEnum.FORMAT.value]
        if self._tools:
            conditional_edges.append(NodeEnum.TOOLS.value)
            # builder.add_node(NodeEnum.TOOLS, self._tools_node)
            builder.add_node(NodeEnum.TOOLS, self._tool_node)
            builder.add_edge(NodeEnum.TOOLS, NodeEnum.CHAT)
        builder.add_conditional_edges(NodeEnum.CHAT, self._router_node, conditional_edges)

        builder.add_edge(NodeEnum.FORMAT, END)

        self.agent = builder.compile(checkpointer=self._checkpointer)
        LOGGER.debug("Схема графа (Mermaid):\n%s", self.agent.get_graph().draw_mermaid())

    def invoke(self, text: str) -> JsonResponse:
        """Метод-обёртка (API) для отправки запросов LLM-агенту."""

        LOGGER.debug(text)
        system_prompt = self._model.chat_cfg.system_prompt
        add_instruct = ""
        try:
            back_request = JsonResponse.model_validate_json(text)
        except ValidationError:
            LOGGER.debug("Запрос не является JSON-структурой")
        else:
            text = back_request.query
            add_instruct = back_request.add_instruct
            system_prompt += f"<add_instruct>{add_instruct}</add_instruct>"

        scenario = Scenario()
        self._rebuild_index_cache(scenario.steps)

        state: OrchestratorState = {
            # ? NOTTODO можно ли избаватья от HumanMessage?
            "messages": [HumanMessage(text)],
            "query": text,
            "system_prompt": system_prompt,
            "sources": {},
            "scenario": scenario,
            "add_instruct": add_instruct,
            "steps_count": 0,
        }
        LOGGER.debug("Начальный state -- %s", state)

        run_cfg: RunnableConfig = {"configurable": {"thread_id": uuid.uuid4().hex}}
        response = self.agent.invoke(input=state, config=run_cfg)

        result = response["result"]
        return JsonResponse.model_validate(result)

    # ? NOTTODO доделать
    # ! [AI Note] Не добавлять в документацию
    def _retrieve_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел поиска релевантных документов по запросу."""
        query = state["query"]
        docs = [doc for r in self._model.retrievers for doc in r.invoke(query)]
        LOGGER.info(
            "Контекст собран из %d документов:\n%s",
            len(docs),
            "\n".join(f"- {doc} [{len(doc.page_content)} симв.]" for doc in docs),
        )

        sources = {
            index: {
                "source": f"<source>{doc.metadata.get('source', '-')}</source>",
                "content": f"<content>{doc.page_content}</content>",
            }
            for index, doc in enumerate(docs, start=1)
        }

        LOGGER.debug("%s -- %s", self._retrieve_node.__name__, sources)
        return {"sources": sources, "steps_count": 1}

    # ! [AI Note] Не добавлять в документацию
    def _chat_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел вызова LLM."""
        messages = state["messages"]
        system_prompt = state["system_prompt"]
        docs = state.get("docs", "")
        system_prompt += f"<context>{docs}</context>"
        response = self._tools_llm.invoke(input=[SystemMessage(system_prompt), *messages])
        LOGGER.debug("%s -- %s", self._chat_node.__name__, response.content)
        return {"messages": [response], "steps_count": 1}

    # ! [AI Note] Не добавлять в документацию
    def _router_node(self, state: OrchestratorState) -> str:
        """Ветвление."""
        messages = state["messages"]
        last_content = messages[-1].content if messages else ""
        tool_calls = getattr(last_content, "tool_calls", [])
        step = state["steps_count"]
        if tool_calls and self._tools and step < self._model.chat_cfg.max_steps:
            LOGGER.debug("%s -- step %s -- %s", self._router_node.__name__, step, NodeEnum.TOOLS)
            return NodeEnum.TOOLS
        LOGGER.debug("%s -- step %s -- %s", self._router_node.__name__, step, NodeEnum.FORMAT)
        return NodeEnum.FORMAT

    # # ! [AI Note] Не добавлять в документацию
    # def _tools_node(self, state: OrchestratorState) -> dict[str, Any]:
    #     """Узел исполнения инструментов, выбранных LLM."""
    #     result = self._tool_node.invoke(state)
    #     LOGGER.debug("%s:\n%s", self._tools_node.__name__, result)
    #     return {
    #         **result,
    #         "steps_count": 1,
    #     }

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

        LOGGER.debug("%s:\n%s", self._format_node.__name__, result)
        return {"result": result, "steps_count": 1}

    @tool
    def get_scenario(self, state: Annotated[OrchestratorState, InjectedState]) -> Command:
        """Возвращает текущий Сценарий целиком с актуальными порядковыми номерами."""
        scenario = state["scenario"]
        steps = [
            step.model_copy(update={"order": order}) for order, step in enumerate(scenario.steps, start=1)
        ]
        LOGGER.debug("%s -- %d Шагов", self.get_scenario.__name__, len(steps))
        return Command(update={"steps_count": 1}, value=steps)

    @tool(parse_docstring=True)
    def insert_step(
        self,
        state: Annotated[OrchestratorState, InjectedState],
        steps: list[tuple[str | None, ScenarioStep]],
    ) -> Command:
        """Добавляет Шаги в Сценарий после указанных id Шагов.

        Args:
            steps: Список кортежей, где первый элемент — это `id` шага (или None/пустая строка,
                если нужно добавить в самый конец), после которого нужно вставить новый шаг,
                а второй элемент — сам объект нового шага `ScenarioStep`.
        """
        used_ids = set(self._index_cache.keys())
        parsed: list[tuple[str, ScenarioStep]] = []
        for after_id, step in steps:
            if after_id and self._find_index(after_id) is None:
                LOGGER.warning("%s -- Шаг '%s' не найден, отмена", self.insert_step.__name__, after_id)
                return Command(update={"steps_count": 1}, value=0)
            parsed.append((after_id, self._with_unique_hash_id(step, used_ids)))

        indexed_inserts: list[tuple[int, ScenarioStep]] = []
        append_steps: list[ScenarioStep] = []
        inserted_counters: dict[str, int] = {}
        for after_id, step in parsed:
            if after_id:
                base_idx = self._find_index(after_id)
                shift = inserted_counters.get(after_id, 0)
                inserted_counters[after_id] = shift + 1
                indexed_inserts.append((base_idx + 1 + shift, step))
            else:
                append_steps.append(step)

        scenario = state["scenario"]
        new_steps = list(scenario.steps)
        for target_idx, step in sorted(indexed_inserts, key=lambda x: x[0]):
            new_steps.insert(target_idx, step)
        self._rebuild_index_cache(scenario.steps)

        LOGGER.info("%s -- добавлено: %d", self.insert_step.__name__, len(parsed))
        return Command(update={"scenario": scenario, "steps_count": 1}, value=len(parsed))

    @tool(parse_docstring=True)
    def update_step(
        self,
        state: Annotated[OrchestratorState, InjectedState],
        steps: list[tuple[str, ScenarioStep]],
    ) -> Command:
        """Изменяет существующие Шаги Сценария.

        Args:
            steps: Список кортежей, где первый элемент — это `id` (hash_id) существующего шага,
                который нужно обновить, а второй — объект `ScenarioStep` с новыми данными.
        """
        parsed: list[tuple[int, ScenarioStep]] = []
        for step_id, new_step in steps:
            index = self._find_index(step_id)
            if index is None:
                LOGGER.warning("%s -- Шаг '%s' не найден, отмена", self.update_step.__name__, step_id)
                return Command(update={"steps_count": 1}, value=0)
            parsed.append((index, new_step.model_copy(update={"hash_id": step_id})))

        scenario = state["scenario"]
        for index, new_step in parsed:
            scenario.steps[index] = new_step

        LOGGER.info("%s -- изменено: %d", self.update_step.__name__, len(parsed))
        return Command(update={"scenario": scenario, "steps_count": 1}, value=len(parsed))

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
        missing = [i for i in step_ids if self._find_index(i) is None]
        if missing:
            LOGGER.warning("%s -- Шаги %s не найдены, отмена.", self.delete_action.__name__, missing)
            return Command(update={"steps_count": 1}, value=0)

        scenario = state["scenario"]
        scenario.steps = [s for s in scenario.steps if s.hash_id not in step_ids]
        self._rebuild_index_cache(scenario.steps)

        LOGGER.info("%s -- удалено: %d", self.delete_action.__name__, len(step_ids))
        return Command(update={"scenario": scenario, "steps_count": 1}, value=len(step_ids))

    # ! [AI Note] Не добавлять в документацию
    def _rebuild_index_cache(self, steps: list[ScenarioStep]) -> None:
        """Перестраивает карту индексов шагов."""
        self._index_cache = {step.hash_id: i for i, step in enumerate(steps) if step.hash_id}

    # ! [AI Note] Не добавлять в документацию
    def _find_index(self, hash_id: str) -> int | None:
        """Возвращает позицию Шага с данным hash-id за O(1)."""
        return self._index_cache.get(hash_id)

    # ! [AI Note] Не добавлять в документацию
    def _with_unique_hash_id(self, step: ScenarioStep, used_ids: set[str]) -> ScenarioStep:
        """Гарантирует уникальный hash-id Шага (генерирует 6-значный при отсутствии или коллизии)."""
        if step.hash_id and step.hash_id not in used_ids:
            used_ids.add(step.hash_id)
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
