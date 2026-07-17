"""Описания инструментов агента scenarAIst."""

from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class JsonResponse(BaseModel):
    """Структура JSON-ответа."""

    status: str = Field(
        ...,
        description="Статус ответа: 'success' или 'error'.",
    )
    message: str = Field(
        ...,
        description="Текстовое сообщение для пользователя.",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Словарь с техническими данными.",
    )


# TODO хрупкость в том, что любое изменение роутера может сломать эту логику.
@tool(args_schema=JsonResponse)
def format_response(**_: Any) -> None:
    """Маркер финального ответа для LLM."""
