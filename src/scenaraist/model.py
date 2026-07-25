"""Конфигурация и фабрики провайдеров LLM и эмбеддингов."""

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass

from langchain.chat_models import BaseChatModel
from langchain.embeddings import Embeddings
from langchain_gigachat import GigaChat, GigaChatEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_openrouter import ChatOpenRouter

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Provider:
    """Провайдер LLM, содержащий фабрики для чата и эмбеддингов."""

    # TODO Callable заменить на Protocol с методом __call__().
    chat: Callable[[], BaseChatModel] | None = None
    embeddings: Callable[[], Embeddings] | None = None


PROVIDERS: dict[str, Provider] = {
    "gigachat": Provider(
        chat=lambda: GigaChat(
            credentials=os.getenv("GIGACHAT_CREDENTIALS"),
            model=os.getenv("GIGACHAT_MODEL", "GigaChat-2"),
            verify_ssl_certs=os.getenv("GIGACHAT_VERIFY_SSL_CERTS", str(False)).strip().lower()
            in {"1", "true", "yes", "on"},
            timeout=60,
        ),
        embeddings=lambda: GigaChatEmbeddings(
            credentials=os.getenv("GIGACHAT_CREDENTIALS"),
            model=os.getenv("GIGACHAT_EMBEDDING_MODEL", "Embeddings"),
        ),
    ),
    "openrouter": Provider(
        chat=lambda: ChatOpenRouter(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            timeout=60,
        ),
    ),
    "openai": Provider(
        chat=lambda: ChatOpenAI(
            base_url=os.getenv("OPENAI_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL"),
            timeout=60,
        ),
        embeddings=lambda: OpenAIEmbeddings(
            base_url=os.getenv("OPENAI_EMBEDDING_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_EMBEDDING_MODEL"),
        ),
    ),
    "huggingface": Provider(
        embeddings=lambda: HuggingFaceEmbeddings(
            model_name=os.getenv("HUGGINGFACE_EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2"),
        ),
    ),
}


def get_chat_model(provider: str) -> BaseChatModel:
    """Создать модель чата по имени провайдера."""

    factory = PROVIDERS.get(provider).chat
    if factory is None:
        raise KeyError("Провайдер '%s' не поддерживает чат.", provider)
    LOGGER.info("Выбран провайдер чата: %s", provider)
    return factory()


def get_embeddings(provider: str) -> Embeddings:
    """Создать модель эмбеддингов по имени провайдера."""

    factory = PROVIDERS.get(provider).embeddings
    if factory is None:
        raise KeyError("Провайдер '%s' не поддерживает эмбеддинги.", provider)
    LOGGER.info("Выбран провайдер эмбеддингов: %s", provider)
    return factory()
