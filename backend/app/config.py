import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "Second Brain OS"
    API_V1_STR: str = "/api/v1"
    
    # Security
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    
    # Databases
    SQLITE_DB_PATH: str = "second_brain.db"
    LANCEDB_DIR: str = "./lancedb_data"
    
    # LLM Settings
    OPENAI_API_KEY: str = Field(default="", validation_alias="OPENAI_API_KEY")
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Ollama settings (for local RAG)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "llama3"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # RAG settings
    USE_LOCAL_LLM: bool = False  # Set to True to use Ollama instead of OpenAI
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        return f"sqlite:///./{self.SQLITE_DB_PATH}"

settings = Settings()
