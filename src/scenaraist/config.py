"""Управление конфигурацией СценарИИста."""

import os
from dataclasses import dataclass, field
from functools import cache

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    """Настройки приложения, загружаемые из переменных окружения."""

    gigachat_api: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_CREDENTIALS", ""),
    )
    gigachat_model: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_MODEL", "GigaChat-2"),
    )
    gigachat_verify_ssl_certs: bool = field(
        default_factory=lambda: _get_bool("GIGACHAT_VERIFY_SSL_CERTS"),
    )

    openrouter_api: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""),
    )
    openrouter_model: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL", "openrouter/free"),
    )

    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.ofox.ai/v1")
    )
    openai_api: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "z-ai/glm-4.7-flash:free")
    )

    tavily_api: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))

    # TODO Проверка требует, чтобы все ключи были пустыми для ошибки, вместо проверки,
    # что хотя бы один нужный ключ предоставлен. Пользователь может выбрать GigaChat,
    # но не иметь GigaChat API ключа — ошибка не возникнет, если есть любой другой ключ.
    def __post_init__(self) -> None:
        if (
            not self.gigachat_api
            and not self.openrouter_api
            and not self.openai_api
            and not self.tavily_api
        ):
            raise ValueError(
                "Отсутствует обязательная переменная окружения API",
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
