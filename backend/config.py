from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # OpenRouter settings (required)
    openrouter_api_key: str
    openrouter_chat_model: str = "openai/gpt-oss-120b:free"  # Default to a free model
    
    # Zendesk settings (optional)
    zendesk_subdomain: Optional[str] = None
    zendesk_email: Optional[str] = None
    zendesk_api_token: Optional[str] = None

    # Storage paths
    faiss_index_path: str = "backend/data/index.faiss"
    faiss_meta_path: str = "backend/data/meta.json"

    # CORS settings
    allowed_origins: List[str] = ["*"]
    
    # Embedding settings
    embedding_model: str = "openai/text-embedding-3-small"  # OpenRouter model id
    embedding_dim: int = 1536  # Dimension of the embedding vectors

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra="ignore"
    )
