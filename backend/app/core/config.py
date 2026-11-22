"""Application configuration using Pydantic Settings (Pydantic v2)."""
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    PROJECT_NAME: str = "EHR Media Intelligence Platform"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    DEBUG: bool = Field(default=True, description="Debug mode flag")
    API_HOST: str = Field(default="127.0.0.1", description="Host interface for API")
    API_PORT: int = Field(default=8000, description="Port for API")
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://127.0.0.1:8000", "http://localhost:8000"],
        description="Allowed CORS origins",
    )

    # Local persistence paths
    SQLITE_DB_PATH: str = Field(
        default="./ehr_intelligence.db",
        description="SQLite database file path",
    )
    CHROMA_PERSIST_DIRECTORY: str = Field(
        default="./chroma_db",
        description="ChromaDB persistence directory",
    )

    # AI Summarization settings
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="Optional API key for LLM provider; offline fallback is used when absent",
    )
    LLM_PROVIDER: str = Field(
        default="offline_fallback",
        description="LLM provider name: 'openai' or 'offline_fallback'",
    )
    LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Model identifier for LLM provider",
    )
    LLM_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for LLM API calls",
    )
    LLM_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        description="Timeout in seconds for external LLM API requests",
    )
    SUMMARY_PROMPT_VERSION: str = Field(
        default="v1.0",
        description="Version string for summary prompt template used in cache keys",
    )

    # Semantic search settings
    EMBEDDING_MODEL_NAME: str = Field(
        default="all-MiniLM-L6-v2",
        description="HuggingFace model name for sentence embeddings",
    )
    CHROMA_COLLECTION_NAME: str = Field(
        default="clinical_records",
        description="Collection name for clinical record vector storage",
    )
    VECTOR_STORE_BACKEND: str = Field(
        default="auto",
        description="Vector store backend: 'auto', 'chromadb', or 'embedded'",
    )

    # Frontend / Static paths
    FRONTEND_DIR: Path = Field(
        default_factory=lambda: (
            Path(__file__).resolve().parent.parent.parent.parent / "frontend"
            if (Path(__file__).resolve().parent.parent.parent.parent / "frontend").exists()
            else Path("frontend")
        ),
        description="Directory containing frontend static assets",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
