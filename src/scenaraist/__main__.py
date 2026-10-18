"""Точка входа scenarAIst."""

import json
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
from scenaraist.qml.handlers.backend import HandlerBackend
from scenaraist.retriever import SQLiteVecRetriever

LOGGER = logging.getLogger(__name__)
QML_DIR = Path(__file__).parent / "qml"
CONFIG_FILE = Path("config.yaml")
LOG_FILE = "scenarAIst.log"
TRANSLATABLE = QML_DIR / Path("translations.json")


def main() -> int:
    LOGGER.info("Запуск СценарИИста")

    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    with CONFIG_FILE.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    with TRANSLATABLE.open("r", encoding="utf-8") as f:
        trl = json.load(f)

    try:
        chat_cfg = CompletionConfig.model_validate(cfg["completion"])
        LOGGER.debug(chat_cfg)
        chat = CHAT_FACTORIES[chat_cfg.provider.strip().lower()](chat_cfg)
    except Exception:
        LOGGER.exception("Ошибка загрузки конфигурации модели")
        return -1

    retriever = None
    try:
        embed_cfg = EmbeddingConfig.model_validate(cfg["embeddings"])
        try:
            LOGGER.debug(embed_cfg)
            embed = EMBEDDING_FACTORIES[embed_cfg.provider.strip().lower()](embed_cfg)
            retriever = SQLiteVecRetriever().from_config(embed_cfg, embed)
        except Exception:
            LOGGER.exception("Ошибка загрузки конфигурации эмбеддингов")
    except Exception:
        # ? пропуск по причине ...
        ...

    tools = []
    try:
        tavily = TavilyConfig.model_validate(cfg["tavily"])
        LOGGER.debug(tavily)
        web_search = TavilySearch(tavily_api_key=tavily.api_key, max_results=tavily.top_k, topic="general")
        tools.append(web_search)
    except Exception:
        # ? пропуск по причине ...
        ...

    # ? SQLite/Postgres Checkpointer
    checkpointer = InMemorySaver()

    agent = build_agent(chat, chat_cfg.system_prompt, checkpointer, tools, retriever)

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    # engine.addImportPath(sys.path[0])
    engine.addImportPath(QML_DIR)

    handler_backend = HandlerBackend(agent=agent, json=trl)
    engine.rootContext().setContextProperty("handlerBackend", handler_backend)
    engine.load(QML_DIR / "Main.qml")

    if not engine.rootObjects():
        return -1

    exit_code = app.exec()
    LOGGER.info("Завершение работы...")
    del engine
    return exit_code


if __name__ == "__main__":
    logging.basicConfig(
        filename="scenarAIst.log",
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())
