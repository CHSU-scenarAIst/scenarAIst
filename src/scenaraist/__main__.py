"""Точка входа scenarAIst."""

import logging
import sys
from pathlib import Path

import yaml
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import InMemorySaver
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from scenaraist.config import CompletionConfig, EmbeddingConfig, TavilyConfig
from scenaraist.graph import build_agent
from scenaraist.model import CHAT_FACTORIES, EMBEDDING_FACTORIES
from scenaraist.qml.handlers.app_backend import AppBackend
from scenaraist.retriever import SQLiteVecRetriever

LOGGER = logging.getLogger(__name__)
QML_DIR = Path(__file__).parent / "qml"


def main() -> int:
    """Запустить чат-бота scenarAIst."""

    logging.basicConfig(
        filename="scenarAIst.log",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    LOGGER.info("Запуск СценарИИста")

    with open("config.yaml") as f:
        data = yaml.safe_load(f)

    try:
        chat_cfg = CompletionConfig.model_validate(data["completion"])
        LOGGER.debug(chat_cfg)
        chat = CHAT_FACTORIES[chat_cfg.provider.strip().lower()](chat_cfg)
    except Exception:
        LOGGER.exception("Ошибка загрузки конфигурации модели")
        raise

    try:
        embed_cfg = EmbeddingConfig.model_validate(data["embeddings"])
        LOGGER.debug(embed_cfg)
        embed = EMBEDDING_FACTORIES[embed_cfg.provider.strip().lower()](embed_cfg)
        retriever = SQLiteVecRetriever().from_config(embed_cfg, embed)
    except Exception:
        LOGGER.exception("Ошибка загрузки конфигурации эмбеддингов")
        retriever = []

    tools = []
    try:
        tavily = TavilyConfig.model_validate(data["tavily"])
        LOGGER.debug(tavily)
        web_search = TavilySearch(tavily_api_key=tavily.api_key, max_results=tavily.top_k, topic="general")
        tools.append(web_search)
    except Exception:
        # пропуск по причине ...
        ...

    # ? SQLite/Postgres Checkpointer
    checkpointer = InMemorySaver()

    agent = build_agent(chat, chat_cfg.system_prompt, checkpointer, tools, retriever)

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    engine.addImportPath(sys.path[0])

    app_backend = AppBackend(agent)

    engine.rootContext().setContextProperty("appBackend", app_backend)

    engine.load(QML_DIR / "Main.qml")

    if not engine.rootObjects():
        return -1

    exit_code = app.exec()
    LOGGER.info("Завершение работы...")
    del engine
    return exit_code


if __name__ == "__main__":
    """Запуск как модуль"""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())
