"""Типы состояний для графа агента."""

from typing import Annotated, TypedDict

from langchain.messages import AnyMessage
from langgraph.graph import add_messages


class OrchestratorState(TypedDict):
    """Состояние графа оркестратора."""

    messages: Annotated[list[AnyMessage], add_messages]
    llm_calls: int
    db_path: str  # Путь к SQLite базе
    urls: list[str]  # Найденные ссылки
    # topic: str  # Тема исследования
    # csv_path: str  # Путь к CSV файлу
    # report_path: str  # Путь к итоговому отчёту
