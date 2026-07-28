"""Точка входа для запуска агента scenarAIst как модуля."""

import logging
from dataclasses import dataclass

import yaml
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import InMemorySaver

from scenaraist.chat import run
from scenaraist.config import ChatConfig, EmbeddingConfig, TavilyConfig
from scenaraist.graph import build_agent
from scenaraist.model import CHAT_FACTORIES, EMBEDDING_FACTORIES, IChat, IEmbeddings
from scenaraist.retriever import StorageRetriever

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Provider:
    chat: IChat | None = None
    embeddings: IEmbeddings | None = None


def main() -> int:
    """Запустить чат-бота scenarAIst."""
    LOGGER.info("Запуск СценарИИста")

    with open("config.yaml") as f:
        data = yaml.safe_load(f)

    try:
        chat_cfg = ChatConfig.model_validate(data["completion"])
        LOGGER.debug(chat_cfg)
        chat = CHAT_FACTORIES[chat_cfg.provider.strip().lower()](chat_cfg)
    except Exception:
        LOGGER.exception("Error loading chat config")
        raise

    try:
        embed_cfg = EmbeddingConfig.model_validate(data["embeddings"])
        LOGGER.debug(embed_cfg)
        embed = EMBEDDING_FACTORIES[embed_cfg.provider.strip().lower()](embed_cfg)
        retriever = StorageRetriever().from_config(embed_cfg, embed)
    except Exception:
        LOGGER.exception("Error loading embeddings config")
        retriever = []

    tools = []
    try:
        tavily = TavilyConfig.model_validate(data["tavily"])
        LOGGER.debug(tavily)
        web_search = TavilySearch(tavily_api_key=tavily.api_key, max_results=tavily.top_k, topic="general")
        tools.append(web_search)
    except Exception:
        ...

    # ? SQLite/Postgres Checkpointer
    checkpointer = InMemorySaver()

    try:
        agent = build_agent(chat, chat_cfg.system_prompt, checkpointer, tools, retriever)
        run(agent)
    except Exception:
        LOGGER.exception("Ошибка работы")

    LOGGER.info("Завершение работы...")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        # filename="scenarAIst.log",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())
