"""Фабрики провайдеров LLM и эмбеддингов."""

from enum import StrEnum
from typing import Protocol

from langchain.chat_models import BaseChatModel
from langchain.embeddings import Embeddings
from langchain_gigachat import GigaChat
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from scenaraist.config import CompletionConfig, EmbeddingConfig


def __create_openai_compatible_chat(cfg: CompletionConfig) -> BaseChatModel:
    return ChatOpenAI(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model or "z-ai/glm-4.7-flash:free",
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def __create_gigachat_chat(cfg: CompletionConfig) -> BaseChatModel:
    return GigaChat(
        credentials=cfg.api_key,
        # model=cfg.model,
        model=cfg.model or "GigaChat-2",
        verify_ssl_certs=cfg.verify_ssl_certs,
        max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def __create_openai_embeddings(cfg: EmbeddingConfig) -> Embeddings:
    return OpenAIEmbeddings(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model or "text-embedding-multilingual-e5-large-instruct",
        dimensions=cfg.dim,
        chunk_size=cfg.batch_size,
        timeout=cfg.timeout,
    )


class Providers(StrEnum):
    OPENAI = "openai"
    GIGACHAT = "gigachat"


class IChat(Protocol):
    """Интерфейс фабрики для создания моделей чата."""

    def __call__(self, cfg: CompletionConfig) -> BaseChatModel: ...


class IEmbeddings(Protocol):
    """Интерфейс фабрики для создания моделей эмбеддингов."""

    def __call__(self, cfg: EmbeddingConfig) -> Embeddings: ...


CHAT_FACTORIES: dict[Providers, IChat] = {
    Providers.OPENAI: __create_openai_compatible_chat,
    Providers.GIGACHAT: __create_gigachat_chat,
}

EMBEDDING_FACTORIES: dict[str, IEmbeddings] = {
    Providers.OPENAI: __create_openai_embeddings,
}
