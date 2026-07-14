"""Точка входа для запуска агента scenarAIst как модуля."""

import logging

# from langchain_gigachat import GigaChat
from langchain_openrouter import ChatOpenRouter

from .app import run
from .config import load_settings
from .graph import build_agent

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Запустить чат-бота scenarAIst."""

    LOGGER.info("Запуск scenarAIst")

    try:
        settings = load_settings()
    except ValueError as exc:
        LOGGER.error("Ошибка конфигурации: %s", exc)
        return 1

    try:
        # llm = GigaChat(
        #     credentials=settings.gigachat_credentials,
        #     model=settings.gigachat_model,
        #     verify_ssl_certs=settings.verify_ssl_certs,
        # )

        print(settings.openrouter_model)
        print(settings.openrouter_credentials[:10] + "...")

        llm = ChatOpenRouter(
            api_key=settings.openrouter_credentials,
            model=settings.openrouter_model,
        )
    except Exception as e:
        LOGGER.exception(f"Неожиданная ошибка: {e}")

    agent = build_agent(llm)
    run(agent)

    LOGGER.info("Завершение работы")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())

# TODO: метод для смены модели в зависимости от поставщика
