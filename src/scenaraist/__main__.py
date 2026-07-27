"""Точка входа для запуска агента scenarAIst как модуля."""

import logging
from dataclasses import dataclass

import yaml
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import InMemorySaver

from scenaraist.chat import run
from scenaraist.config import CompletionConfig, EmbeddingConfig
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

    try:
        with open("config.yaml") as f:
            data = yaml.safe_load(f)

        completion = CompletionConfig(**data["completion"])
        model_completion = CHAT_FACTORIES[completion.provider.strip().lower()](completion)

        # TODO вынести в конфигурационный файл.
        folder_path: str = "./docs/zhopka"
        db_path: str = "rag.sqlite3"
        table = "documents"
        top_k = 5
        max_tokens = 10000
        chunk_size = 1000
        chunk_overlap = 200

        try:
            embedding = EmbeddingConfig(**data["embeddings"])
            model_embeddings = EMBEDDING_FACTORIES[embedding.provider.strip().lower()](embedding)

            retriever = StorageRetriever(
                folder_path, db_path, table, model_embeddings, chunk_size, chunk_overlap
            )
            retriever.get_storage_retriever(top_k)
        except Exception:
            retriever = None

    except Exception:
        LOGGER.exception("Ошибка конфигурации")
        raise

    tools = []

    try:
        tavily_api_key = EmbeddingConfig(**data["tavily_api_key"])
        web_search = TavilySearch(tavily_api_key=tavily_api_key, max_results=top_k, topic="general")
        tools.append(web_search)
    except Exception:
        ...

    # ? SQLite/Postgres Checkpointer
    checkpointer = InMemorySaver()

    try:
        agent = build_agent(model_completion, checkpointer, tools, max_tokens, retriever)
        run(agent)
    except Exception:
        LOGGER.exception("Ошибка работы")
        raise

    LOGGER.info("Завершение работы...")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.CRITICAL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())
