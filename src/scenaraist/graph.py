"""Сборка и компиляция графа LangGraph."""

import logging
from datetime import UTC, datetime
from typing import Any

from langchain.chat_models import BaseChatModel
from langchain.messages import SystemMessage
from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode

from .nodes import ToolName, final, router
from .state import OrchestratorState
from .tools import MATH_TOOLS, format_response, web_search

LOGGER = logging.getLogger(__name__)


def build_agent(llm: BaseChatModel) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Собрать и скомпилировать граф состояний агента."""

    web_tool = web_search().as_tool()
    all_tools = [*MATH_TOOLS, format_response, web_tool]
    llm_with_tools = llm.bind_tools(all_tools)

    def chat(state: OrchestratorState) -> OrchestratorState:
        """Узел вызова LLM с текущей историей сообщений."""
        LOGGER.debug("Вызов чатбота с %d сообщениями", len(state["messages"]))
        prompt = [
            SystemMessage(
                content=(
                    "You are a helpful assistant. Отвечай на языке поступившего запроса.\n"
                    "Используй инструменты, когда они необходимы для получения ответа.\n"
                    "Use web search to find accurate, up-to-date information.\n"
                    f"Today's date is {datetime.now(UTC):%B %d, %Y}."
                )
            ),
            *state["messages"],
        ]
        return {
            "messages": [llm_with_tools.invoke(prompt)],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

    # TODO Математические инструменты сгруппированы в один ToolNode, а веб-поиск — в отдельный.
    # Это архитектурное решение вынуждает роутер выбирать только один путь, и если
    # модель вызывает add и web_search одновременно, второй вызов будет проигнорирован.
    math_tool_node = ToolNode(MATH_TOOLS)
    web_tool_node = ToolNode([web_tool])
    builder = StateGraph(OrchestratorState)

    # Узлы графа
    builder.add_node(chat.__name__, chat)
    builder.add_node(ToolName.MATH, math_tool_node)
    builder.add_node(ToolName.WEB, web_tool_node)
    builder.add_node(ToolName.FINAL, final)

    # Структура графа
    builder.add_edge(START, chat.__name__)
    builder.add_edge(ToolName.MATH, chat.__name__)
    builder.add_edge(ToolName.WEB, chat.__name__)
    builder.add_conditional_edges(
        chat.__name__,
        router,
        {ToolName.MATH: ToolName.MATH, ToolName.FINAL: ToolName.FINAL, ToolName.WEB: ToolName.WEB},
    )
    builder.add_edge(ToolName.FINAL, END)

    # Сборка агента
    agent = builder.compile()
    # display(Image(graph.get_graph().draw_mermaid_png()))
    LOGGER.info("Граф скомпилирован")
    return agent
