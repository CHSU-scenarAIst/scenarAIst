"""Точка входа для запуска агента scenarAIst как модуля."""

import logging

import questionary
from langchain_gigachat import GigaChat
from langchain_openai import ChatOpenAI
from langchain_openrouter import ChatOpenRouter

from .app import run
from .config import load_settings

# from .db import make_db
from .graph import build_agent

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Запустить чат-бота scenarAIst."""

    # TODO
    # make_db()

    LOGGER.info("Запуск СценарИИста")

    try:
        settings = load_settings()
    except ValueError as exc:
        LOGGER.error("Ошибка конфигурации: %s", exc)
        return 1

    choice = questionary.select(
        "Выберите провайдера LLM:",
        choices=[
            "1. GigaChat",
            "2. OpenRouter",
            "3. OpenAI",
        ],
    ).ask()

    try:
        if str(choice).startswith("1"):
            llm = GigaChat(
                credentials=settings.gigachat_api,
                model=settings.gigachat_model,
                verify_ssl_certs=settings.gigachat_verify_ssl_certs,
                timeout=60.0,
            )
        elif str(choice).startswith("2"):
            llm = ChatOpenRouter(
                api_key=settings.openrouter_api,
                model=settings.openrouter_model,
                timeout=60.0,
            )
        elif str(choice).startswith("3"):
            llm = ChatOpenAI(
                base_url=settings.openai_base_url,
                api_key=settings.openai_api,
                model=settings.openai_model,
                timeout=60.0,
            )
    except Exception as e:
        LOGGER.error(f"Ошибка LLM: {e}")
        return 1

    agent = build_agent(llm)
    run(agent)

    LOGGER.info("Завершение работы...")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())
