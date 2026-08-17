from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    foundry_embedding_model: str = "qwen3-embedding-0.6b"
    foundry_chat_model: str = "qwen2.5-0.5b"
    repolens_data_dir: str = "./data"
    repolens_max_upload_mb: int = 25
    repolens_max_uncompressed_mb: int = 200
    repolens_max_files: int = 5000
    repolens_max_source_file_kb: int = 512
    repolens_embedding_batch_size: int = Field(default=32, ge=1)
    repolens_top_k: int = Field(default=4, ge=1, le=20)
    repolens_min_similarity: float = Field(default=0.35, ge=-1.0, le=1.0)
    repolens_chat_max_tokens: int = Field(default=512, ge=1, le=4096)
    repolens_chat_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    repolens_max_context_chars: int = Field(default=24000, ge=1000)
    repolens_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.repolens_allowed_origins.split(",") if origin.strip()]


settings = Settings()
