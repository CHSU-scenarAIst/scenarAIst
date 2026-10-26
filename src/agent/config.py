"""Конфигурация работы программы."""

from pydantic import BaseModel, Field

# TODO дать описание каждому полю через Field


class CompletionConfig(BaseModel):
    provider: str

    api_key: str = Field(repr=False)
    verify_ssl_certs: bool = False
    base_url: str | None = None
    model: str | None = None
    temperature: float = 0.1
    max_tokens: int = 10000
    timeout: int = 60
    max_steps: int = Field(default=20, ge=1)
    system_prompt: str = "You are a scenarAIst."


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


# class TavilyConfig(BaseModel):
#     api_key: str = Field(repr=False)
#     top_k: int = 3
#
# def from_cfg(self, cfg) -> Self:
#     return self.model_validate(cfg["tavily"])
