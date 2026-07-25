"""Сборка и компиляция графа LangGraph."""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langchain.chat_models import BaseChatModel
from langchain.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage, trim_messages
from langchain.tools import BaseTool, tool
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, add_messages
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field, ValidationError

LOGGER = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "<prompt>You are a helpful assistant. Respond in the same language as the user's request.\n"
    "The agent may use tools whenever they are necessary to answer the user's request.\n"
    "The agent MUST use the web search tool whenever the answer depends on current or external information.\n"
    "The agent MUST use the format_response tool to produce the final answer.\n"
    "Never output the literal text 'format_response' in the final response.</prompt>\n"
)


class OrchestratorState(TypedDict, total=False):
    """Состояние графа оркестратора."""

    messages: Annotated[list[AnyMessage], add_messages]
    max_llm_calls: int
    llm_calls: int
    query: str
    documents: list[Document]


def build_agent(
    chat: BaseChatModel,
    checkpointer: BaseCheckpointSaver,
    tools: list[BaseTool],
    retriever: BaseRetriever,
    max_tokens: int,
) -> CompiledStateGraph:
    """Собрать и скомпилировать граф состояний агента."""

    llm_with_tools = chat.bind_tools([*tools, format_response])

    def chat_node(state: OrchestratorState) -> OrchestratorState:
        """Узел вызова LLM с текущей историей сообщений."""
        messages = state["messages"]
        LOGGER.info("Chat node with %d messages", len(messages))

        messages = prepare_messages(messages, max_tokens)
        docs = state.get("documents", [])
        query = state.get("query") or extract_query(messages)

        system_content = SYSTEM_PROMPT + f"<today>{datetime.now(UTC):%B %d, %Y}.</today>"
        if context := prepare_context_documents(docs):
            system_content += f"<context>{context}</context>"

        prompt: list[AnyMessage] = [SystemMessage(content=system_content)]
        prompt.extend(messages)

        response = llm_with_tools.invoke(prompt)

        return {
            "messages": [response],
            "llm_calls": state.get("llm_calls", 0) + 1,
            "query": query,
        }

    def retrieve_node(state: OrchestratorState) -> OrchestratorState:
        """Узел поиска документов по запросу."""
        LOGGER.info("Retrieve node")

        query = state.get("query") or extract_query(state["messages"])
        docs = retriever.invoke(query)

        return {
            "query": query,
            "documents": docs,
        }

    builder = StateGraph(OrchestratorState)

    # Узлы графа
    builder.add_node(NodeName.RETRIEVE, retrieve_node)
    builder.add_node(NodeName.CHAT, chat_node)
    builder.add_node(NodeName.TOOLS, ToolNode(tools))
    builder.add_node(NodeName.FINAL, final_node)

    # Структура графа
    builder.add_edge(START, NodeName.RETRIEVE)
    builder.add_edge(NodeName.RETRIEVE, NodeName.CHAT)
    builder.add_conditional_edges(
        NodeName.CHAT,
        router_node,
        {
            NodeName.TOOLS: NodeName.TOOLS,
            NodeName.FINAL: NodeName.FINAL,
        },
    )
    builder.add_edge(NodeName.TOOLS, NodeName.CHAT)
    builder.add_edge(NodeName.FINAL, END)

    # Сборка агента
    agent = builder.compile(checkpointer=checkpointer)
    # ? debug схемы структуры графа
    LOGGER.info("Граф скомпилирован")
    return agent


class NodeName(StrEnum):
    """Имена узлов графа с инструментами."""

    CHAT = "chat_node"
    TOOLS = "tool_node"
    RETRIEVE = "retrieve_node"
    FINAL = "final_node"


class JsonResponse(BaseModel):
    """Структура JSON-ответа."""

    status: str = Field(..., description="Статус ответа: 'OK' или 'ERROR'.")
    message: str = Field(..., description="Текстовое сообщение для пользователя.")
    data: dict[str, Any] = Field(default_factory=dict, description="Словарь с техническими данными.")


# ? упростить
@tool(args_schema=JsonResponse)
def format_response(**_: Any) -> None:
    """Маркер финального ответа LLM для завершения графа."""


def prepare_messages(messages: list[AnyMessage], max_tokens: int) -> list[AnyMessage]:
    # ? суммаризация
    # ? SQLite/Postgres Checkpointer
    return trim_messages(
        messages,
        max_tokens=max_tokens,
        strategy="last",
        token_counter=lambda msgs: len(str(msgs)),  # либо tokenizer модели
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


def prepare_context_documents(docs: list[Document]) -> str:
    """Формирует текст контекста из найденных документов."""
    if not docs:
        return ""
    # ! source нет такого поля
    return "\n\n".join(
        f"<source>{doc.metadata.get('source', '-')}</source><documents>{doc.page_content}</documents>"
        for doc in docs
    )


def router_node(state: OrchestratorState) -> NodeName:
    """Ветвление после вызова LLM."""
    LOGGER.info("Router node")

    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", [])
    non_final = [tc for tc in tool_calls if tc["name"] != format_response.name]

    if non_final and state.get("llm_calls", 0) < state.get("max_llm_calls", 20):
        return NodeName.TOOLS

    return NodeName.FINAL


# LLM
# ↓
# нет format_response
# ↓
# добавить SystemMessage
# "You MUST call format_response."
# ↓
# LLM


def final_node(state: OrchestratorState) -> OrchestratorState:
    """Узел гарантированного форматирования ответа."""
    LOGGER.info("Final node")

    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", [])
    call = next((tc for tc in tool_calls if tc["name"] == format_response.name), None)

    if call is not None:
        try:
            response = JsonResponse(**call["args"])
        except ValidationError as e:
            LOGGER.warning("Некорректный JSON от модели: %s", e)
            response = JsonResponse(
                status="ERROR",
                message="Модель сформировала некорректный ответ.",
                data={"validation_error": e.errors()},
            )

        payload = response.model_dump_json(indent=2)
        return {
            "messages": [
                ToolMessage(content=payload, tool_call_id=call["id"], name=format_response.name),
                AIMessage(content=payload),
            ],
        }

    content = getattr(last, "content", "")
    fallback = JsonResponse(
        status="ERROR",
        message="Модель не вызвала format_response.",
        data={"raw_content": str(content)},
    )

    return {
        "messages": [AIMessage(content=fallback.model_dump_json(indent=2))],
    }
