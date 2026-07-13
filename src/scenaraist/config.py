"""Управление конфигурацией агента scenarAIst."""

import os
from dataclasses import dataclass, field
from functools import cache

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    """Настройки приложения, загружаемые из переменных окружения."""

    gigachat_credentials: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_CREDENTIALS", ""),
    )
    gigachat_model: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_MODEL", "GigaChat-2"),
    )
    verify_ssl_certs: bool = field(
        default_factory=lambda: _get_bool("GIGACHAT_VERIFY_SSL_CERTS"),
    )

    def __post_init__(self) -> None:
        if not self.gigachat_credentials:
            raise ValueError(
                "Отсутствует обязательная переменная окружения: GIGACHAT_CREDENTIALS",
            )


def _get_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@cache
def load_settings() -> Settings:
    """Загрузить переменные окружения из .env файла и вернуть настройки."""
    load_dotenv(override=False)
    return Settings()
