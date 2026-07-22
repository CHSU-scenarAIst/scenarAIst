"""Сборка и компиляция графа LangGraph."""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langchain.chat_models import BaseChatModel
from langchain.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langchain.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
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


def build_agent(chat: BaseChatModel, tools: list[BaseTool] | None = None) -> CompiledStateGraph:
    """Собрать и скомпилировать граф состояний агента."""

    llm_with_tools = chat.bind_tools(tools)

    def chat_node(state: OrchestratorState) -> OrchestratorState:
        """Узел вызова LLM с текущей историей сообщений."""

        messages = state["messages"]
        LOGGER.debug("Вызов чатбота с %d сообщениями", len(messages))
        prompt = [
            SystemMessage(content=SYSTEM_PROMPT + f"Today's date is {datetime.now(UTC):%B %d, %Y}."),
            *messages,
        ]

        return {
            "messages": [llm_with_tools.invoke(prompt)],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

    builder = StateGraph(OrchestratorState)

    # Узлы графа
    builder.add_node(chat_node.__name__, chat_node)
    builder.add_node(NodeName.TOOLS, ToolNode(tools))
    builder.add_node(NodeName.FINAL, final_node)

    # Структура графа
    builder.add_edge(START, chat_node.__name__)
    builder.add_edge(NodeName.TOOLS, chat_node.__name__)
    builder.add_conditional_edges(
        chat_node.__name__,
        router_node,
        {
            NodeName.FINAL: NodeName.FINAL,
            NodeName.TOOLS: NodeName.TOOLS,
        },
    )
    builder.add_edge(NodeName.FINAL, END)

    # Сборка агента
    # ? InMemorySaver не сохраняет состояние между перезапусками.
    # Для production рекомендуется SQLiteSaver или PostgresSaver.
    checkpointer = InMemorySaver()
    agent = builder.compile(checkpointer=checkpointer)
    LOGGER.info("Граф скомпилирован")
    return agent


class OrchestratorState(TypedDict):
    """Состояние графа оркестратора."""

    messages: Annotated[list[AnyMessage], add_messages]
    # TODO История сообщений растёт бесконечно — каждое взаимодействие добавляет
    # HumanMessage, AIMessage и возможные ToolMessage. Нет механизма очистки или
    # сокращения контекста, что может привести к превышению лимита контекста LLM.
    # Рекомендуется: внедрить стратегию сокращения контекста (windowing, summarization)
    # или использовать checkpointer с поддержкой trimming.
    max_llm_calls: int = 20
    llm_calls: int
    folder_path: str
    # ? использовать
    db_path: str  # Путь к SQLite базе


class NodeName(StrEnum):
    """Имена узлов графа с инструментами."""

    TOOLS = "tool_node"
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

    # ? fallback: при отсутствии format_response создаётся ответ с сырым content. Может быть невалидным JSON.
    content = getattr(last, "content", "")
    fallback = JsonResponse(
        status="OK",
        message=str(content),
        data={},
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


@tool(args_schema=JsonResponse)
def format_response(**_: Any) -> None:
    """Маркер финального ответа LLM для завершения графа."""
