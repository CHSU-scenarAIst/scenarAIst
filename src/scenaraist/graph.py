"""Сборка и компиляция графа LangGraph."""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from langchain.chat_models import BaseChatModel
from langchain.messages import AnyMessage, HumanMessage, SystemMessage
from langchain.tools import BaseTool
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)


class JsonResponse(BaseModel):
    """Структура JSON-ответа."""

    status: str = Field(..., description="Статус ответа: 'OK' или 'ERROR'.")
    message: str = Field(..., description="Текстовое сообщение для пользователя.")
    data: dict[str, Any] = Field(default_factory=dict, description="Словарь с техническими данными.")


class OrchestratorState(MessagesState, total=False):
    """Состояние графа оркестратора."""

    steps: int
    query: str
    documents: list[Document] | None
    response: JsonResponse


# TODO class AgentGraphBuilder: переписать на объектный подход
def build_agent(
    chat: BaseChatModel,
    system_prompt: str,
    checkpointer: BaseCheckpointSaver,
    tools: list[BaseTool],
    retriever: BaseRetriever | None,
    # TODO в конфиг
    max_steps: int = 20,
) -> CompiledStateGraph:
    """Собрать и скомпилировать граф состояний агента."""

    agent_llm = chat.bind_tools(tools)
    tool_node = ToolNode(tools)

    def retrieve_node(state: OrchestratorState) -> OrchestratorState:
        """Узел поиска документов по запросу."""
        LOGGER.info("Retrieve node")

        if retriever is None:
            return {}

        query = extract_query(state["messages"])
        docs = retriever.invoke(query)

        return {
            "query": query,
            "documents": docs,
            "steps": state.get("steps", 0) + 1,
        }

    def chat_node(state: OrchestratorState) -> OrchestratorState:
        """Узел вызова LLM с текущей историей сообщений."""
        messages = state["messages"]
        LOGGER.info("Chat node with %d messages", len(messages))

        docs = state.get("documents", None)
        system_content = system_prompt + f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"

        if context := prepare_context_documents(docs):
            system_content += f"<context>{context}</context>"

        response = agent_llm.invoke([SystemMessage(system_content), *messages])
        LOGGER.info("LLM response: response=%s", response)

        return {
            "messages": [response],
            "steps": state.get("steps", 0) + 1,
        }

    def router_node(state: OrchestratorState) -> NodeEnum:
        """Ветвление после вызова LLM."""
        LOGGER.info("Router node")

        last = state["messages"][-1]
        tool_calls = getattr(last, "tool_calls", [])

        if tool_calls and state.get("steps", 0) < max_steps:
            return NodeEnum.TOOLS

        return NodeEnum.FORMAT

    def tools_node(state: OrchestratorState) -> OrchestratorState:
        """TODO"""
        result = tool_node.invoke(state)
        return {
            **result,
            "steps": state.get("steps", 0) + 1,
        }

    def format_node(state: OrchestratorState) -> OrchestratorState:
        """TODO"""
        LOGGER.info("Format node")

        last = state["messages"][-1]
        response = JsonResponse(
            status="OK",
            message=last.content,
            data={},
        )

        return {
            "messages": state["messages"],
            "response": response,
            "steps": state.get("steps", 0) + 1,
        }

    builder = StateGraph(OrchestratorState)

    # Узлы и Структура графа
    builder.add_node(NodeEnum.CHAT, chat_node)
    builder.add_node(NodeEnum.FORMAT, format_node)

    if retriever:
        builder.add_node(NodeEnum.RETRIEVE, retrieve_node)
        builder.add_edge(START, NodeEnum.RETRIEVE)
        builder.add_edge(NodeEnum.RETRIEVE, NodeEnum.CHAT)
    else:
        builder.add_edge(START, NodeEnum.CHAT)

    if tools:
        builder.add_node(NodeEnum.TOOLS, tools_node)
        conditional_edges = {NodeEnum.TOOLS: NodeEnum.TOOLS, NodeEnum.FORMAT: NodeEnum.FORMAT}
        builder.add_edge(NodeEnum.TOOLS, NodeEnum.CHAT)
    else:
        conditional_edges = {NodeEnum.FORMAT: NodeEnum.FORMAT}

    builder.add_conditional_edges(NodeEnum.CHAT, router_node, conditional_edges)
    builder.add_edge(NodeEnum.FORMAT, END)

    # Сборка агента
    agent = builder.compile(checkpointer=checkpointer)
    # ? debug схемы структуры графа
    LOGGER.info("Граф скомпилирован")
    return agent


class NodeEnum(StrEnum):
    """Имена узлов графа с инструментами."""

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FORMAT = "format_node"


def extract_query(messages: list[AnyMessage]) -> str:
    """Достаёт последний пользовательский запрос из истории."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    last = messages[-1] if messages else None
    return str(getattr(last, "content", "") or "")


def prepare_context_documents(docs: list[Document] | None) -> str:
    """Формирует текст контекста из найденных документов."""
    if not docs:
        return ""
    # ! TODO source нет такого поля
    return "\n\n".join(
        f"<source>{doc.metadata.get('source', '-')}</source><documents>{doc.page_content}</documents>"
        for doc in docs
    )
