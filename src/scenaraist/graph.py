"""Сборка и компиляция графа LangGraph."""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langchain.chat_models import BaseChatModel
from langchain.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage, trim_messages
from langchain.tools import BaseTool, tool
from langchain_core.retrievers import BaseRetriever
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, add_messages
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field, ValidationError

LOGGER = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a helpful assistant. Отвечай на языке поступившего запроса.\n"
    "Используй инструменты, когда они необходимы для получения ответа.\n"
    "Use the web search tool whenever the answer depends on current or external information.\n"
    "Always use the format_response tool for your final answer.\n"
    "Never write format_response as plain text.\n"
)


class OrchestratorState(TypedDict):
    """Состояние графа оркестратора."""

    messages: Annotated[list[AnyMessage], add_messages]
    max_llm_calls: int = 20
    llm_calls: int
    query: str
    retriever: BaseRetriever
    documents: list[Document]


def build_agent(
    chat: BaseChatModel,
    checkpointer: BaseCheckpointSaver,
    tools: list[BaseTool],
    retriever: BaseRetriever,
    max_tokens: int,
) -> CompiledStateGraph:
    """Собрать и скомпилировать граф состояний агента."""

    llm_with_tools = chat.bind_tools(tools)

    def chat_node(state: OrchestratorState) -> OrchestratorState:
        """Узел вызова LLM с текущей историей сообщений."""

        messages = state["messages"]
        LOGGER.debug("Вызов чатбота с %d сообщениями", len(messages))

        messages = prepare_messages(messages, max_tokens)
        content = SYSTEM_PROMPT + f"Today's date is {datetime.now(UTC):%B %d, %Y}."
        prompt = [SystemMessage(content), *messages]

        return {
            "messages": [llm_with_tools.invoke(prompt)],
            "llm_calls": state.get("llm_calls", 0) + 1,
            "query": "#TODO",
        }

    builder = StateGraph(OrchestratorState)

    builder.state_schema["retriever"] = retriever

    # Узлы графа
    builder.add_node(NodeName.CHAT, chat_node)
    builder.add_node(NodeName.TOOLS, ToolNode(tools))
    builder.add_node(NodeName.RETRIEVE, retrieve_node)
    builder.add_node(NodeName.FINAL, final_node)

    # Структура графа
    builder.add_edge(START, NodeName.CHAT)
    builder.add_conditional_edges(
        NodeName.CHAT,
        router_node,
        {
            NodeName.TOOLS: NodeName.TOOLS,
            NodeName.RETRIEVE: NodeName.RETRIEVE,
            NodeName.FINAL: NodeName.FINAL,
        },
    )
    builder.add_edge(NodeName.TOOLS, NodeName.CHAT)
    builder.add_edge(NodeName.RETRIEVE, NodeName.CHAT)
    builder.add_edge(NodeName.FINAL, END)

    # Сборка агента
    agent = builder.compile(checkpointer=checkpointer)
    LOGGER.info("Граф скомпилирован")
    return agent


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


class NodeName(StrEnum):
    """Имена узлов графа с инструментами."""

    CHAT = "chat_node"
    TOOLS = "tool_node"
    RETRIEVE = "retrieve_node"
    FINAL = "final_node"


def router_node(state: OrchestratorState) -> NodeName:
    """Ветвление между узлами графа."""

    LOGGER.info("Router node")

    last = state["messages"][-1]
    tool_calls = last.tool_calls
    non_final = [tc for tc in tool_calls if tc["name"] != format_response.name]

    if non_final and state["llm_calls"] < state["max_llm_calls"]:
        return NodeName.TOOLS

    return NodeName.FINAL


def retrieve_node(state: OrchestratorState):
    """TODO"""

    LOGGER.info("Retrieve node")

    retriever = state["retriever"]
    query = state["query"]
    docs = retriever.invoke(query)

    # ? для отладки
    for d in docs:
        print(d.metadata.get("source", "-"))
        print(d.page_content[:300])

    return {
        "documents": docs,
    }
    # return "\n\n".join(f"Источник: {d.metadata.get('source', '-')}\n{d.page_content}" for d in docs)


def final_node(state: OrchestratorState) -> OrchestratorState:
    """Узел гарантированного форматирования ответа."""

    LOGGER.info("Final node")

    last = state["messages"][-1]
    tool_calls = last.tool_calls
    call = tool_calls[0] if tool_calls else None

    if call and call["name"] == format_response.name:
        try:
            response = JsonResponse(**call["args"])
        except ValidationError as e:
            LOGGER.warning("Некорректный JSON от модели: %s", e)
            response = JsonResponse(
                status="ERROR",
                message="Модель сформировала некорректный ответ.",
                data={"validation_error": e.errors()},
            )
        return {
            "messages": [
                ToolMessage(
                    content=response.model_dump_json(),
                    tool_call_id=call["id"],
                    name=format_response.name,
                ),
                AIMessage(content=response.model_dump_json(indent=2)),
            ],
        }

    # LLM
    # ↓
    # нет format_response
    # ↓
    # добавить SystemMessage
    # "You MUST call format_response."
    # ↓
    # LLM

    content = getattr(last, "content", "")
    fallback = JsonResponse(
        status="ERROR",
        message="Модель не вызвала format_response.",
        data={"raw_content": str(content)},
    )

    return {"messages": [AIMessage(content=fallback.model_dump_json(indent=2))]}


class JsonResponse(BaseModel):
    """Структура JSON-ответа."""

    status: str = Field(
        ...,
        description="Статус ответа: 'OK' или 'ERROR'.",
    )
    message: str = Field(
        ...,
        description="Текстовое сообщение для пользователя.",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Словарь с техническими данными.",
    )


# ? упростить
@tool(args_schema=JsonResponse)
def format_response(**_: Any) -> None:
    """Маркер финального ответа LLM для завершения графа."""
