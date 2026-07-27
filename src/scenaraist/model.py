"""Фабрики провайдеров LLM и эмбеддингов."""

from enum import StrEnum
from typing import Protocol

from langchain.chat_models import BaseChatModel
from langchain.embeddings import Embeddings
from langchain_gigachat import GigaChat, GigaChatEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from scenaraist.config import CompletionConfig, EmbeddingConfig


class IChat(Protocol):
    """Интерфейс фабрики для создания моделей чата."""

    def __call__(self, cfg: CompletionConfig) -> BaseChatModel: ...


class IEmbeddings(Protocol):
    """Интерфейс фабрики для создания моделей эмбеддингов."""

    def __call__(self, cfg: EmbeddingConfig) -> Embeddings: ...


DEFAULT_TIMEOUT = 60


def __create_openai_compatible_chat(cfg: CompletionConfig) -> BaseChatModel:
    return ChatOpenAI(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model or "z-ai/glm-4.7-flash:free",
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        timeout=DEFAULT_TIMEOUT,
    )


def __create_gigachat_chat(cfg: CompletionConfig) -> BaseChatModel:
    return GigaChat(
        credentials=cfg.api_key,
        model=cfg.model or "GigaChat-2",
        verify_ssl_certs=cfg.verify_ssl_certs,
        timeout=DEFAULT_TIMEOUT,
    )


def __create_openai_embeddings(cfg: EmbeddingConfig) -> Embeddings:
    return OpenAIEmbeddings(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model,
    )


def __create_gigachat_embeddings(cfg: EmbeddingConfig) -> Embeddings:
    return GigaChatEmbeddings(
        credentials=cfg.api_key,
        model=cfg.model or "Embeddings",
    )


def __create_huggingface_embeddings(cfg: EmbeddingConfig) -> Embeddings:
    return HuggingFaceEmbeddings(
        model_name=cfg.model or "sentence-transformers/all-mpnet-base-v2",
    )


class Provider(StrEnum):
    OPENAI = "openai"
    GIGACHAT = "gigachat"
    HUGGINGFACE = "huggingface"


CHAT_FACTORIES: dict[Provider, IChat] = {
    Provider.OPENAI: __create_openai_compatible_chat,
    Provider.GIGACHAT: __create_gigachat_chat,
}

EMBEDDING_FACTORIES: dict[str, IEmbeddings] = {
    Provider.OPENAI: __create_openai_embeddings,
    Provider.GIGACHAT: __create_gigachat_embeddings,
    Provider.HUGGINGFACE: __create_huggingface_embeddings,
}
