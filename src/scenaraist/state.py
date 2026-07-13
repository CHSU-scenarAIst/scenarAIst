"""Типы состояний для графа агента."""

from typing import Annotated, TypedDict

from langchain.messages import AnyMessage  # noqa: TC002
from langgraph.graph import add_messages


class OrchestratorState(TypedDict):
    """Состояние графа оркестратора."""

    messages: Annotated[list[AnyMessage], add_messages]
    # topic: str  # Тема исследования
    # urls: list[str]  # Найденные ссылки
    # db_path: str  # Путь к SQLite базе
    # csv_path: str  # Путь к CSV файлу
    # report_path: str  # Путь к итоговому отчёту
