"""Build and compile a LangGraph agent."""

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .tools import MATH_TOOLS

if TYPE_CHECKING:
    from langchain.chat_models import BaseChatModel

logger = logging.getLogger(__name__)
Agent = CompiledStateGraph[Any, Any, Any, Any]


def build_agent(llm: BaseChatModel) -> Agent:
    """Build and compile the agent state graph."""
    llm_with_tools = llm.bind_tools(MATH_TOOLS)

    def chatbot(state: MessagesState) -> MessagesState:
        """Invoke the LLM with the current message history."""
        logger.debug("Invoking chatbot with %d messages", len(state["messages"]))
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    tool_node = ToolNode(MATH_TOOLS)

    builder = StateGraph(MessagesState)
    builder.add_node("chatbot", chatbot)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "chatbot")
    builder.add_conditional_edges("chatbot", tools_condition)
    builder.add_edge("tools", "chatbot")

    agent = builder.compile()
    logger.info("Agent graph compiled successfully")
    return agent


EXIT_COMMANDS = {"exit", "quit"}


def run_conversation(agent: Agent) -> None:
    """Run an interactive conversation loop with the agent."""
    history: list[AnyMessage] = []

    print("scenarAIst agent ready. Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            text = input("> ").strip()
        except EOFError, KeyboardInterrupt:
            print("\nGoodbye!")
            break

        if not text:
            continue

        if text.lower() in EXIT_COMMANDS:
            print("Goodbye!")
            break

        history.append(HumanMessage(content=text))

        try:
            logger.debug("User input: %s", text)
            result = agent.invoke({"messages": history})
            history = result["messages"]
            # TODO? Иногда content бывает не строкой (например, списком блоков контента)
            response = history[-1].content
            print(response)
        except Exception:
            logger.exception("Error during agent invocation")
            print("An error occurred. Please try again.")
