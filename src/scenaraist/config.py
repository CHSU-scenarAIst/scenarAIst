"""Конфигурация LLM."""

from pydantic import BaseModel, Field


class CompletionConfig(BaseModel):
    provider: str
    api_key: str = Field(repr=False)
    verify_ssl_certs: bool = False
    base_url: str | None = None
    model: str | None = None
    temperature: float = 0.8
    max_tokens: int = 10000
    system_prompt: str = "You are a helpful assistant."
    timeout: int = 60


class CollectionConfig(BaseModel):
    path: str
    name: str
    top_k: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 64


class EmbeddingConfig(BaseModel):
    provider: str
    api_key: str = Field(default="None", repr=False)
    collections: list[CollectionConfig]
    verify_ssl_certs: bool = False
    base_url: str | None = None
    model: str | None = None
    dim: int = 1024
    db_path: str = "./rag.sqlite3"
    batch_size: int = 4
    timeout: int = 60


class TavilyConfig(BaseModel):
    api_key: str = Field(repr=False)
    top_k: int = 3
