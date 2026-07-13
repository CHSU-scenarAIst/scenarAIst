"""Build and compile a LangGraph agent."""

import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, TypedDict

from langchain.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode

from .tools import MATH_TOOLS, JsonResponse, format

if TYPE_CHECKING:
    from langchain.chat_models import BaseChatModel
    from langgraph.graph.state import CompiledStateGraph

LOGGER = logging.getLogger(__name__)
MATH_TOOLS_NAMES = [tool.name for tool in MATH_TOOLS]


class ToolName(StrEnum):
    MATH = "math_tools"
    FINAL = "final_tool"


class OrchestratorState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # topic: str  # Тема исследования
    # urls: list[str]  # Найденные ссылки
    # db_path: str  # Путь к SQLite базе
    # csv_path: str  # Путь к CSV файлу
    # report_path: str  # Путь к итоговому отчёту


def build_agent(llm: BaseChatModel) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Build and compile the agent state graph."""

    llm_with_tools = llm.bind_tools([*MATH_TOOLS, format])

    def chat(state: OrchestratorState) -> OrchestratorState:
        """Нода Invoke the LLM with the current message history."""
        LOGGER.debug("Invoking chatbot with %d messages", len(state["messages"]))
        prompt = [
            SystemMessage(
                content="You are a helpful assistant. To solve any problem, you need use the tools."
            ),
            *state["messages"],
        ]
        return {"messages": [llm_with_tools.invoke(prompt)]}

    builder = StateGraph(OrchestratorState)

    # ноды (вершины графа)
    builder.add_node(chat.__name__, chat)
    builder.add_node(ToolName.MATH, ToolNode(MATH_TOOLS))
    builder.add_node(ToolName.FINAL, final)

    # структура графа
    builder.add_edge(START, chat.__name__)
    builder.add_edge(ToolName.MATH, chat.__name__)
    builder.add_conditional_edges(
        chat.__name__, router, {ToolName.MATH: ToolName.MATH, ToolName.FINAL: ToolName.FINAL}
    )
    builder.add_edge(ToolName.FINAL, END)

    # сборка агента
    agent = builder.compile()
    LOGGER.info("Agent graph compiled successfully")
    return agent


def router(state: OrchestratorState) -> ToolName:
    """Ветвление между нодами"""

    last = state["messages"][-1]

    if hasattr(last, "tool_calls") and last.tool_calls:
        if last.tool_calls[0]["name"] in MATH_TOOLS_NAMES:
            LOGGER.debug(f"Модель вызвала: {last.tool_calls[0]['name']}")
            return ToolName.MATH
        return ToolName.FINAL

    return ToolName.FINAL


def final(state: OrchestratorState) -> OrchestratorState:
    """Нода гарантированного форматирования ответа."""
    LOGGER.info("Форматирование финального ответа в JSON")

    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", [])

    if tool_calls and tool_calls[0]["name"] == format.name:
        call = tool_calls[0]
        return {
            "messages": [
                ToolMessage(
                    content="JSON сформирован успешно",
                    tool_call_id=call["id"],
                    name=format.name,
                ),
                AIMessage(content=JsonResponse(**call["args"]).model_dump_json(indent=2)),
            ]
        }

    fallback = JsonResponse(status="success", message=str(last.content or ""), data={})
    return {"messages": [AIMessage(content=fallback.model_dump_json(indent=2))]}
