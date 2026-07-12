"""Tool definitions for the scenarAIst agent."""

from langchain_core.tools import tool

# __all__ = [
#     "MATH_TOOLS",
# ]


@tool
def multiply(a: int, b: int) -> int:
    """Use this tool when the user asks to multiply two integers."""
    return a * b


@tool
def add(a: int, b: int) -> int:
    """Use this tool to calculate the sum of two integers."""
    return a + b


MATH_TOOLS = (
    add,
    multiply,
)
