"""Конфигурация LLM."""

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class ChatConfig:
    provider: str
    api_key: str = field(repr=False)
    verify_ssl_certs: bool = False
    base_url: str | None = None
    model: str | None = None
    temperature: float = 0.8
    max_tokens: int = 10000
    system_prompt: str = "You are a helpful assistant."


@dataclass(slots=True, frozen=True)
class CollectionConfig:
    path: str
    name: str
    top_k: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 64


@dataclass(slots=True, frozen=True)
class EmbeddingConfig:
    provider: str
    api_key: str = field(repr=False)
    collections: list[CollectionConfig]
    verify_ssl_certs: bool = False
    base_url: str | None = None
    model: str | None = None
    dim: int = 1024
    db_path: str = "./rag.sqlite3"


@dataclass(slots=True, frozen=True)
class TavilyConfig:
    api_key: str = field(repr=False)
    top_k: int = 3
