import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START
from langgraph.graph.state import StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import ValidationError

from src.agent.model import ScenarAIstModelFactory
from src.agent.state import ActionItem, JsonResponse, NodeEnum, OrchestratorState

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig


LOGGER = logging.getLogger(__name__)


class ScenarAIstAgent:
    """Сборщик агента-Сценариста с инструментами и источниками знаний."""

    def __init__(self, cfg: ScenarAIstModelFactory) -> None:
        self._cfg = cfg
        self._run_cfg: RunnableConfig = {
            "configurable": {
                "thread_id": uuid.uuid4().hex,
            }
        }
        self._tools_llm = self._cfg.chat.bind_tools(self._cfg.tools)
        self._format_llm = self._cfg.chat.with_structured_output(ActionItem)
        self._tool_node = ToolNode(self._cfg.tools)

    def build(self) -> None:
        """Сборка LLM-агента."""

        builder = StateGraph(OrchestratorState)

        builder.add_node(NodeEnum.CHAT, self._chat_node)
        builder.add_node(NodeEnum.FORMAT, self._format_node)

        if self._cfg.retrievers:
            builder.add_edge(START, NodeEnum.RETRIEVE)
            builder.add_node(NodeEnum.RETRIEVE, self._retrieve_node)
            builder.add_edge(NodeEnum.RETRIEVE, NodeEnum.CHAT)
        else:
            builder.add_edge(START, NodeEnum.CHAT)

        conditional_edges = [NodeEnum.FORMAT.value]
        if self._cfg.tools:
            conditional_edges.append(NodeEnum.TOOLS.value)
            builder.add_node(NodeEnum.TOOLS, self._tools_node)
            builder.add_edge(NodeEnum.TOOLS, NodeEnum.CHAT)
        builder.add_conditional_edges(NodeEnum.CHAT, self._router_node, conditional_edges)

        builder.add_edge(NodeEnum.FORMAT, END)

        self.agent = builder.compile(checkpointer=self._cfg.checkpointer)
        LOGGER.debug("Схема графа (Mermaid):\n%s", self.agent.get_graph().draw_mermaid())

    def invoke(self, text: str) -> JsonResponse:
        """Метод-обёртка для отправки запросов LLM-агенту извне."""

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
            + self._cfg.system_prompt
            + "</prompt>"
            + (f"<add_instruct>{add_instruct}</add_instruct>" if add_instruct else "")
            + f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"
        )

        state: OrchestratorState = {
            "messages": [HumanMessage(text)],
            "query": text,
            "system_prompt": system_prompt,
            "actions": [],
            "sources": {},
            "add_instruct": add_instruct,
            "steps": 0,
        }

        LOGGER.debug("Начальный OrchestratorState -- %s", state)
        response = self.agent.invoke(input=state, config=self._run_cfg)
        result = response["result"]
        return JsonResponse.model_validate(result)

    # ! [AI Note] Не добавлять в документацию
    def _retrieve_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел поиска релевантных документов по запросу."""
        query = state["query"]
        docs = [doc for r in self._cfg.retrievers for doc in r.invoke(query)]

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
            "steps": state["steps"] + 1,
        }

    # ! [AI Note] Не добавлять в документацию
    def _chat_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел вызова LLM с текущей историей сообщений."""

        messages = state["messages"]
        system_prompt = state["system_prompt"]
        docs = state.get("docs", "")
        system_prompt += f"<context>{docs}</context>"

        response = self._tools_llm.invoke(
            input=[SystemMessage(system_prompt), *messages],
            # config=self._run_cfg,
        )

        LOGGER.debug("%s -- %s", self._chat_node, response.content)
        return {
            "messages": [response],
            "steps": state["steps"] + 1,
        }

    # ! [AI Note] Не добавлять в документацию
    def _router_node(self, state: OrchestratorState) -> str:
        """Ветвление после вызова LLM: исполнение инструментов либо финализация ответа."""

        messages = state["messages"]
        last_content = messages[-1].content if messages else ""
        tool_calls = getattr(last_content, "tool_calls", [])

        step = state["steps"]
        if tool_calls and self._cfg.tools and step < self._cfg.max_steps:
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
            "steps": state["steps"] + 1,
        }

    # ! [AI Note] Не добавлять в документацию
    def _format_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Узел финализации ответа в JSON-структуру."""

        messages = state["messages"]
        last_content = messages[-1].content if messages else ""

        system_prompt = "Систематизируй, отформатируй и упакуй итоговый ответ"
        response = self._format_llm.invoke(
            input=[SystemMessage(system_prompt), last_content],
            # config=self._run_cfg,
        )
        response = ActionItem.model_validate(response)

        result = JsonResponse(
            query=state["query"],
            add_instruct=state["add_instruct"],
            sources=state["sources"],
            actions=state["actions"],
        )

        LOGGER.debug("%s:\n%s", self._format_node, result)
        return {"result": result}
