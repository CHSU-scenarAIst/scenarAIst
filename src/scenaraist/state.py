"""Типы состояний для графа агента."""

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, TypedDict

from langgraph.graph import add_messages

if TYPE_CHECKING:
    from langchain.messages import AnyMessage


class ToolName(StrEnum):
    """Имена узлов графа с инструментами."""

    MATH = "math_tools"
    FINAL = "final_tool"


class OrchestratorState(TypedDict):
    """Состояние графа оркестратора."""

    messages: Annotated[list[AnyMessage], add_messages]
    # topic: str  # Тема исследования
    # urls: list[str]  # Найденные ссылки
    # db_path: str  # Путь к SQLite базе
    # csv_path: str  # Путь к CSV файлу
    # report_path: str  # Путь к итоговому отчёту
