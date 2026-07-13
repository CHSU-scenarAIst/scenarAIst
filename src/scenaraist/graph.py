"""Сборка и компиляция графа LangGraph."""

import logging
from typing import TYPE_CHECKING, Any

from langchain.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .nodes import final, router
from .state import OrchestratorState, ToolName
from .tools import MATH_TOOLS, format_response

if TYPE_CHECKING:
    from langchain.chat_models import BaseChatModel
    from langgraph.graph.state import CompiledStateGraph

LOGGER = logging.getLogger(__name__)


def build_agent(llm: BaseChatModel) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Собрать и скомпилировать граф состояний агента."""

    llm_with_tools = llm.bind_tools([*MATH_TOOLS, format_response])

    def chat(state: OrchestratorState) -> OrchestratorState:
        """Узел вызова LLM с текущей историей сообщений."""
        LOGGER.debug("Вызов чатбота с %d сообщениями", len(state["messages"]))
        prompt = [
            SystemMessage(
                content="Вы — полезный ассистент. Для решения любых задач используйте инструменты."
            ),
            *state["messages"],
        ]
        return {"messages": [llm_with_tools.invoke(prompt)]}

    builder = StateGraph(OrchestratorState)

    # Узлы (вершины графа)
    builder.add_node(chat.__name__, chat)
    builder.add_node(ToolName.MATH, ToolNode(MATH_TOOLS))
    builder.add_node(ToolName.FINAL, final)

    # Структура графа
    builder.add_edge(START, chat.__name__)
    builder.add_edge(ToolName.MATH, chat.__name__)
    builder.add_conditional_edges(
        chat.__name__, router, {ToolName.MATH: ToolName.MATH, ToolName.FINAL: ToolName.FINAL}
    )
    builder.add_edge(ToolName.FINAL, END)

    # Сборка агента
    agent = builder.compile()
    LOGGER.info("Граф агента успешно скомпилирован")
    return agent
