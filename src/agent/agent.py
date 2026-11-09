import logging
import uuid
import zlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from langchain.messages import HumanMessage, SystemMessage
from langchain.tools import BaseTool, tool
from langgraph.graph import END, START
from langgraph.graph.state import StateGraph
from langgraph.prebuilt import ToolNode
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

    def __init__(self, model: ScenarAIstModelFactory) -> None:
        self._model = model
        self._cfg: RunnableConfig = {
            "configurable": {
                "thread_id": uuid.uuid4().hex,
            }
        }

        # ? Текущий Сценарий (очередь Шагов), доступный инструментам агента
        self._scenario = Scenario()

        # ? SQLite/Postgres Checkpointer
        # self.checkpointer = InMemorySaver()
        self._checkpointer = None

        self._tools: list[BaseTool] = [
            tool(self.get_scenario),
            tool(self.add_action),
            tool(self.update_action),
            tool(self.delete_action),
        ]
        self._tools_llm = self._model.chat.bind_tools(self._tools)
        self._tool_node = ToolNode(self._tools)

        (name_get, name_add, name_update, name_delete) = (tool_item.name for tool_item in self._tools)
        self._tools_prompt = (
            "При работе с tools всегда считай их результат истинным и окончательным."
            " С помощью tools ты можешь управлять текущим Сценарием:"
            f"  1) получить текущий Сценарий целиком - '{name_get}',"
            f"  2) добавлять Шаги в Сценарий - '{name_add}',"
            f"  3) изменять существующие Шаги - '{name_update}',"
            f"  4) удалять Шаги по их hash-id - '{name_delete}'."
            f" Прежде чем менять Сценарий, всегда получай его актуальное состояние"
            f" через {name_get}, чтобы знать существующие hash-id Шагов."
        )

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
            builder.add_node(NodeEnum.TOOLS, self._tools_node)
            builder.add_edge(NodeEnum.TOOLS, NodeEnum.CHAT)
        builder.add_conditional_edges(NodeEnum.CHAT, self._router_node, conditional_edges)

        builder.add_edge(NodeEnum.FORMAT, END)

        self.agent = builder.compile(checkpointer=self._checkpointer)
        LOGGER.debug("Схема графа (Mermaid):\n%s", self.agent.get_graph().draw_mermaid())

    def invoke(self, text: str) -> JsonResponse:
        """Метод-обёртка (API) для отправки запросов LLM-агенту."""

        add_instruct = ""
        try:
            back_request = JsonResponse.model_validate_json(text)
        except ValidationError:
            LOGGER.debug("Запрос не является JSON-структурой")
        else:
            text = back_request.query
            add_instruct = back_request.add_instruct

        system_prompt = (
            "<prompt>"
            + self._model.system_prompt
            + "</prompt>"
            + (f"<add_instruct>{add_instruct}</add_instruct>" if add_instruct else "")
            + f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"
            + "<tools>"
            + self._tools_prompt
            + "</tools>"
        )
        state: OrchestratorState = {
            # ? NOTTODO можно ли избаватья от HumanMessage?
            "messages": [HumanMessage(text)],
            "query": text,
            "system_prompt": system_prompt,
            "sources": {},
            "scenario": self._scenario,
            "add_instruct": add_instruct,
            "steps_count": 0,
        }
        LOGGER.debug("Начальный OrchestratorState -- %s", state)
        response = self.agent.invoke(input=state, config=self._cfg)
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

        LOGGER.debug("%s -- %s", self._retrieve_node, sources)
        return {
            "sources": sources,
            "steps_count": state["steps_count"] + 1,
        }

    # ! [AI Note] Не добавлять в документацию
    def _chat_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел вызова LLM."""
        messages = state["messages"]
        system_prompt = state["system_prompt"]
        docs = state.get("docs", "")
        system_prompt += f"<context>{docs}</context>"
        response = self._tools_llm.invoke(
            input=[SystemMessage(system_prompt), *messages],
            # config=self._cfg,
        )
        LOGGER.debug("%s -- %s", self._chat_node, response.content)
        return {
            "messages": [response],
            "steps_count": state["steps_count"] + 1,
        }

    # ! [AI Note] Не добавлять в документацию
    def _router_node(self, state: OrchestratorState) -> str:
        """Ветвление."""
        messages = state["messages"]
        last_content = messages[-1].content if messages else ""
        tool_calls = getattr(last_content, "tool_calls", [])
        step = state["steps_count"]
        if tool_calls and self._tools and step < self._model.max_steps:
            LOGGER.debug("%s -- step %s -- %s", self._router_node, step, NodeEnum.TOOLS)
            return NodeEnum.TOOLS
        LOGGER.debug("%s -- step %s -- %s", self._router_node, step, NodeEnum.FORMAT)
        return NodeEnum.FORMAT

    # ! [AI Note] Не добавлять в документацию
    def _tools_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел исполнения инструментов, выбранных LLM."""
        result = self._tool_node.invoke(state)
        LOGGER.debug("%s:\n%s", self._tools_node, result)
        return {
            **result,
            "steps_count": state["steps_count"] + 1,
        }

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
            scenario=state.get("scenario"),
        )

        LOGGER.debug("%s:\n%s", self._format_node, result)
        return {"result": result}

    def get_scenario(self) -> Scenario:
        """Возвращает текущий Сценарий целиком."""
        steps = [
            step.model_copy(update={"order": order})
            for order, step in enumerate(self._scenario.steps, start=1)
        ]
        LOGGER.debug("%s -- %d Шагов", self.get_scenario, len(steps))
        return Scenario(steps=steps)

    def add_action(self, steps: list[tuple[str, ScenarioStep]]) -> bool:
        """
        Добавляет Шаги в Сценарий.
        Args:
            steps: Список пар (hash-id Шага, после которого вставить, новый Шаг).
                Пустая строка вместо hash-id означает добавление в конец Сценария.
        """
        used_ids: set[str] = set()

        # ? Сначала валидация всех Шагов (атомарность), потом вставка
        parsed: list[tuple[str, ScenarioStep]] = []
        for raw_after_id, step in steps:
            after_id = str(raw_after_id)
            if after_id and self._find_index(after_id) is None:
                LOGGER.warning(
                    "%s -- Шаг с hash-id '%s' не найден, вставка отменена",
                    self.add_action,
                    after_id,
                )
                return False
            parsed.append((after_id, self._with_unique_hash_id(step, used_ids)))

        inserted_after: dict[str, int] = {}
        for after_id, step in parsed:
            if after_id:
                # ? Смещение сохраняет порядок пар при нескольких
                #     вставках после одного и того же hash-id
                shift = inserted_after.get(after_id, 0)
                inserted_after[after_id] = shift + 1
                self._scenario.steps.insert(self._find_index(after_id) + 1 + shift, step)
            else:
                self._scenario.steps.append(step)

        LOGGER.info("%s -- добавлено Шагов: %d", self.add_action, len(parsed))
        return True

    def update_action(self, steps: list[tuple[str, ScenarioStep]]) -> bool:
        """
        Изменяет существующие Шаги Сценария.
        Args:
            steps: Список пар (hash-id изменяемого Шага, новая версия Шага).
        """
        # ? Сначала валидация всех Шагов (атомарность), потом замена
        parsed: list[tuple[int, ScenarioStep]] = []
        for raw_hash_id, new_step in steps:
            hash_id = str(raw_hash_id)
            index = self._find_index(hash_id)
            if index is None:
                LOGGER.warning(
                    "%s -- Шаг с hash-id '%s' не найден, замена отменена",
                    self.update_action,
                    hash_id,
                )
                return False
            # ? hash-id новой версии принудительно совпадает со старым,
            #     чтобы не ломать ссылки на Шаг
            parsed.append((index, new_step.model_copy(update={"hash_id": hash_id})))

        for index, new_step in parsed:
            self._scenario.steps[index] = new_step

        LOGGER.info("%s -- изменено Шагов: %d", self.update_action, len(parsed))
        return True

    def delete_action(self, step_ids: list[str]) -> bool:
        """
        Удаляет Шаги из Сценария по их hash-id.
        Args:
            step_ids: Список hash-id удаляемых Шагов.
        """
        ids = {str(step_id) for step_id in step_ids}
        missing = [hash_id for hash_id in ids if self._find_index(hash_id) is None]
        if missing:
            LOGGER.warning(
                "%s -- Шаги с hash-id %s не найдены, удаление отменено",
                self.delete_action,
                missing,
            )
            return False
        self._scenario.steps = [step for step in self._scenario.steps if step.hash_id not in ids]
        LOGGER.info("%s -- удалено Шагов: %d", self.delete_action, len(ids))
        return True

    # ! [AI Note] Не добавлять в документацию
    def _find_index(self, hash_id: str) -> int | None:
        """Возвращает позицию Шага с данным hash-id в очереди Сценария."""
        for index, step in enumerate(self._scenario.steps):
            if step.hash_id == hash_id:
                return index
        return None

    # ! [AI Note] Не добавлять в документацию
    def _with_unique_hash_id(self, step: ScenarioStep, used_ids: set[str]) -> ScenarioStep:
        """Гарантирует уникальный hash-id Шага (генерирует 6-значный при отсутствии или коллизии)."""
        if step.hash_id and step.hash_id not in used_ids and self._find_index(step.hash_id) is None:
            used_ids.add(step.hash_id)
            return step

        # ? Детерминированный 6-значный hash-id из содержимого Шага
        payload = step.model_dump_json().encode()
        salt = 0
        while True:
            hash_id = f"{zlib.crc32(payload + salt.to_bytes(4, 'big')) % 1_000_000:06d}"
            salt += 1
            if hash_id not in used_ids and self._find_index(hash_id) is None:
                used_ids.add(hash_id)
                LOGGER.debug("%s -- сгенерирован hash-id '%s'", self._with_unique_hash_id, hash_id)
                return step.model_copy(update={"hash_id": hash_id})
