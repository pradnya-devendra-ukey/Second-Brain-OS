import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "Second Brain OS"
    API_V1_STR: str = "/api/v1"
    
    # Security
    CORS_ORIGINS: list[str] = ["*"]
    
    # Databases
    SQLITE_DB_PATH: str = "second_brain.db"
    LANCEDB_DIR: str = "./lancedb_data"
    
    # Gemini LLM Settings
    GEMINI_API_KEY: str = Field(default="", validation_alias="GEMINI_API_KEY")
    LLM_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    GEMINI_EMBEDDING_DIMENSION: int = 768
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        return f"sqlite:///./{self.SQLITE_DB_PATH}"

settings = Settings()
