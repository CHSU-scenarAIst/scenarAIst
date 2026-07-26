"""Сборка и компиляция графа LangGraph."""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from langchain.chat_models import BaseChatModel
from langchain.messages import AnyMessage, HumanMessage, SystemMessage, trim_messages
from langchain.tools import BaseTool
from langchain_core.documents import Document
from langchain_core.messages.utils import count_tokens_approximately
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


SYSTEM_PROMPT = (
    "<prompt>"
    "You are a helpful assistant. Respond in the same language as the user's request.\n"
    "The agent may use tools whenever they are necessary to answer the user's request.\n"
    "The agent MUST use the web search tool whenever the answer depends on current or external information.\n"
    "</prompt>"
)

FORMAT_PROMPT = (
    "<prompt>"
    "You are a formatter."
    "Convert the assistant answer into the required JSON schema:"
    f"{JsonResponse.model_json_schema()}."
    "DON'T change original answer!."
    "</prompt>"
)


# class AgentGraphBuilder: ...


# ? переписать на объектный подход
def build_agent(
    chat: BaseChatModel,
    checkpointer: BaseCheckpointSaver,
    tools: list[BaseTool],
    max_tokens: int,
    retriever: BaseRetriever | None = None,
    max_steps: int = 20,
) -> CompiledStateGraph:
    """Собрать и скомпилировать граф состояний агента."""

    agent_llm = chat.bind_tools(tools)
    structured_llm = chat.with_structured_output(JsonResponse)
    tool_node = ToolNode(tools)

    def retrieve_node(state: OrchestratorState) -> OrchestratorState:
        """Узел поиска документов по запросу."""
        LOGGER.critical("Retrieve node")

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
        LOGGER.critical("Chat node with %d messages", len(messages))

        messages = prepare_messages(messages, max_tokens)
        docs = state.get("documents", None)
        system_content = SYSTEM_PROMPT + f"<today>{datetime.now(UTC):%B %d, %Y}.</today>"

        if context := prepare_context_documents(docs):
            system_content += f"<context>{context}</context>"

        response = agent_llm.invoke([SystemMessage(system_content), *messages])
        LOGGER.critical("LLM response: response=%s", response)

        return {
            "messages": [response],
            "steps": state.get("steps", 0) + 1,
        }

    def router_node(state: OrchestratorState) -> NodeEnum:
        """Ветвление после вызова LLM."""
        LOGGER.critical("Router node")

        last = state["messages"][-1]
        tool_calls = getattr(last, "tool_calls", [])

        if tool_calls and state.get("steps", 0) < max_steps:
            return NodeEnum.TOOLS

        return NodeEnum.FINAL

    def tools_node(state: OrchestratorState) -> OrchestratorState:
        result = tool_node.invoke(state)
        return {
            **result,
            "steps": state.get("steps", 0) + 1,
        }

    def format_node(state: OrchestratorState) -> OrchestratorState:
        """TODO"""
        LOGGER.critical("Format node")

        messages = state["messages"]
        messages = prepare_messages(messages, max_tokens)
        response = structured_llm.invoke([SystemMessage(FORMAT_PROMPT), *messages])
        LOGGER.critical("Formatter raw: %s", response)

        return {
            "response": response,
            "steps": state.get("steps", 0) + 1,
        }

    builder = StateGraph(OrchestratorState)

    # Узлы графа
    if retriever:
        builder.add_node(NodeEnum.RETRIEVE, retrieve_node)
    builder.add_node(NodeEnum.CHAT, chat_node)
    builder.add_node(NodeEnum.TOOLS, tools_node)
    builder.add_node(NodeEnum.FINAL, format_node)

    # Структура графа
    if retriever:
        builder.add_edge(START, NodeEnum.RETRIEVE)
        builder.add_edge(NodeEnum.RETRIEVE, NodeEnum.CHAT)
    else:
        builder.add_edge(START, NodeEnum.CHAT)

    builder.add_conditional_edges(
        NodeEnum.CHAT,
        router_node,
        {
            NodeEnum.TOOLS: NodeEnum.TOOLS,
            NodeEnum.FINAL: NodeEnum.FINAL,
        },
    )
    builder.add_edge(NodeEnum.TOOLS, NodeEnum.CHAT)
    builder.add_edge(NodeEnum.FINAL, END)

    # Сборка агента
    agent = builder.compile(checkpointer=checkpointer)
    # ? debug схемы структуры графа
    LOGGER.critical("Граф скомпилирован")
    return agent


class NodeEnum(StrEnum):
    """Имена узлов графа с инструментами."""

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FINAL = "final_node"


def prepare_messages(messages: list[AnyMessage], max_tokens: int) -> list[AnyMessage]:
    """TODO"""
    # ? tokenizer конкретной модели.
    return trim_messages(
        messages,
        max_tokens=max_tokens,
        strategy="last",
        token_counter=count_tokens_approximately,
        include_system=False,
        start_on="human",
    )


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
