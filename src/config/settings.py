"""Application configuration and settings management."""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM API (DeepSeek - OpenAI Compatible)
    deepseek_api_key: str = Field(..., description="DeepSeek API key")
    llm_provider: str = Field(default="deepseek", description="LLM provider (deepseek, anthropic, openai)")
    llm_base_url: str = Field(default="https://api.deepseek.com", description="LLM API base URL")

    # Milvus Configuration
    milvus_host: str = Field(default="localhost", description="Milvus server host")
    milvus_port: int = Field(default=19530, description="Milvus server port")
    collection_name: str = Field(default="parking_knowledge", description="Vector collection name")

    # LLM Settings
    default_model: str = Field(default="deepseek-chat", description="Default LLM model")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="LLM temperature")
    max_tokens: int = Field(default=1024, ge=1, description="Max tokens in response")

    # Embedding Settings
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Embedding model name"
    )
    chunk_size: int = Field(default=500, ge=1, description="Document chunk size")
    chunk_overlap: int = Field(default=50, ge=0, description="Document chunk overlap")

    # Database
    database_url: str = Field(default="sqlite:///./data/parking.db", description="Database connection URL")

    # Application
    log_level: str = Field(default="INFO", description="Logging level")
    max_context_length: int = Field(default=10, ge=1, description="Max conversation history")

    @property
    def milvus_uri(self) -> str:
        """Get Milvus connection URI."""
        return f"http://{self.milvus_host}:{self.milvus_port}"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
