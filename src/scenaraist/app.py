import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AnyMessage, HumanMessage

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


EXIT_COMMANDS = {"exit", "quit"}


logger = logging.getLogger(__name__)


def run(agent: CompiledStateGraph[Any, Any, Any, Any]) -> None:
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
