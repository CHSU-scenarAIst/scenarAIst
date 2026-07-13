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


@tool(args_schema=JsonResponse)
def format_response(**kwargs: Any) -> str:
    """Собирает валидную JSON-строку."""
    try:
        return JsonResponse(**kwargs).model_dump_json(indent=2)
    except Exception as e:
        return JsonResponse(
            status="error", message="Ошибка валидации", data={"trace": str(e)}
        ).model_dump_json(indent=2)
