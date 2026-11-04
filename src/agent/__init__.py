"""Пакет "Обработка эмбеддингов". Сборка LLM-агента с инструментами и обработчиками эмбеддингов документов."""

from importlib.metadata import version

__version__ = version("scenaraist")


import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from langchain.messages import HumanMessage, SystemMessage
from langchain_core.documents import Document
from langgraph.graph import END, START
from langgraph.graph.state import StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, ValidationError

from src.agent.model import ScenarAIstModelFactory
from src.agent.state import JsonResponse, NodeEnum, OrchestratorState, WordItem

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

    # ? with_structured_output()
    def build(self) -> None:
        """Сборка LLM-агента."""

        self._agent_llm = self._cfg.chat.bind_tools(self._cfg.tools)
        self._tool_node = ToolNode(self._cfg.tools)

        builder = StateGraph(OrchestratorState)

        builder.add_node(NodeEnum.CHAT, self._chat_node)
        builder.add_node(NodeEnum.FORMAT, self._format_node)

        if self._cfg.retrievers:
            builder.add_edge(START, NodeEnum.RETRIEVE)
            builder.add_node(NodeEnum.RETRIEVE, self._retrieve_node)
            builder.add_edge(NodeEnum.RETRIEVE, NodeEnum.CHAT)
        else:
            builder.add_edge(START, NodeEnum.CHAT)

        conditional_edges = [
            NodeEnum.FORMAT.value,
        ]
        if self._cfg.tools:
            conditional_edges.append(NodeEnum.TOOLS.value)
            builder.add_node(NodeEnum.TOOLS, self._tools_node)
            builder.add_edge(NodeEnum.TOOLS, NodeEnum.CHAT)

        builder.add_conditional_edges(
            NodeEnum.CHAT,
            self._router_node,
            conditional_edges,
        )
        builder.add_edge(NodeEnum.FORMAT, END)

        self.agent = builder.compile(checkpointer=self._cfg.checkpointer)
        LOGGER.debug("Схема графа (Mermaid):\n%s", self.agent.get_graph().draw_mermaid())

    def invoke(self, text: str) -> BaseModel:
        """Метод-обёртка для отправки запросов LLM-агенту извне."""

        add_instruct = None
        try:
            back_response = JsonResponse.model_validate_json(text)
        except ValidationError:
            LOGGER.debug("Запрос не является JSON-структурой")
        else:
            text = back_response.message
            add_instruct = back_response.add_instruct

        # TODO создавать новый чистый объект для запроса
        state: OrchestratorState = (
            {
                "query": text,
                "messages": [HumanMessage(text)],
            }
            if not add_instruct
            else {
                "query": text,
                "messages": [HumanMessage(text)],
                "add_instruct": add_instruct,
            }
        )

        LOGGER.debug("State: \n%s", state)
        result = self.agent.invoke(state, self._run_cfg)
        model = result["response"]

        if not isinstance(model, BaseModel):
            raise TypeError("Ответ агента не является моделью Pydantic")

        return model

    def _retrieve_node(self, state: OrchestratorState) -> dict[str, Any]:
        """
        Узел поиска релевантных документов по запросу.
        ! [AI Note] Не добавлять в документацию
        """

        messages = state["messages"]
        query = _extract_query(list(messages))

        if not self._cfg.retrievers:
            return {
                "query": query,
                "documents": [],
                "steps": state.get("steps", 0) + 1,
            }

        docs = [doc for r in self._cfg.retrievers for doc in r.invoke(query)]

        return {
            "query": query,
            "documents": docs,
            "steps": state.get("steps", 0) + 1,
        }

    def _chat_node(self, state: OrchestratorState) -> dict[str, Any]:
        """
        Узел вызова LLM с текущей историей сообщений.
        ! [AI Note] Не добавлять в документацию
        """
        messages = state["messages"]
        docs = state.get("documents", None)

        add_instruct = state.get("add_instruct")
        if add_instruct:
            LOGGER.debug("Примерена доп. инструкция: %s", add_instruct)

        system_content = (
            "<system>"
            + self._cfg.system_prompt
            + (add_instruct if add_instruct else "")
            + "</system>"
            + f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"
        )

        if context := _prepare_context_documents(docs):
            system_content += f"<context>{context}</context>"

        response = self._agent_llm.invoke([SystemMessage(system_content), *messages])

        return {
            "messages": [response],
            "steps": state.get("steps", 0) + 1,
        }

    def _router_node(self, state: OrchestratorState) -> str:
        """
        Ветвление после вызова LLM: исполнение инструментов либо финализация ответа.
        ! [AI Note] Не добавлять в документацию
        """

        last = state["messages"][-1]
        tool_calls = getattr(last, "tool_calls", [])

        if tool_calls and self._cfg.tools and state.get("steps", 0) < self._cfg.max_steps:
            return NodeEnum.TOOLS

        return NodeEnum.FORMAT

    def _tools_node(self, state: OrchestratorState) -> dict[str, Any]:
        """
        Узел исполнения инструментов, выбранных LLM.
        ! [AI Note] Не добавлять в документацию
        """

        result = self._tool_node.invoke(state)
        return {
            **result,
            "steps": state.get("steps", 0) + 1,
        }

    def _format_node(self, state: OrchestratorState) -> dict[str, Any]:
        """
        Узел финализации ответа в JSON-структуру.
        ! [AI Note] Не добавлять в документацию
        """

        last = state["messages"][-1]
        content = last.content
        message = content if isinstance(content, str) else " ".join(str(part) for part in content)

        # ? NOTTODO data={...}
        response = JsonResponse(
            query=state["query"],
            message=message,
            data={},
            words=[WordItem(word=word) for word in message.split()],
        )

        return {
            "response": response,
            "steps": state.get("steps", 0) + 1,
        }


def _extract_query(messages: list[Any]) -> str:
    """
    Достаёт последний пользовательский запрос из истории (требование GigaChat?).
    ! [AI Note] Не добавлять в документацию
    """
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)

    last = messages[-1] if messages else None
    return str(getattr(last, "content", "") or "")


def _prepare_context_documents(docs: list[Document] | None) -> str:
    """
    Формирует текст контекста из найденных документов.
    ! [AI Note] Не добавлять в документацию
    """
    if not docs:
        return ""

    # ? NOTTODO проверить, как сделать по-другому какие документы и их фрагменты вошли в контекст
    LOGGER.debug(
        "Контекст собран из %d документов:\n%s",
        len(docs),
        "\n".join(f"- {doc.metadata.get('source', '-')} [{len(doc.page_content)} симв.]" for doc in docs),
    )
    return "\n\n".join(
        f"<source>{doc.metadata.get('source', '-')}</source><content>{doc.page_content}</content>"
        for doc in docs
    )
