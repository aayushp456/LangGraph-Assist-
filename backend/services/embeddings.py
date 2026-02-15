from typing import List, Optional
from openai import OpenAI

from backend.config import Settings


class EmbeddingsService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        if not self.settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for embeddings.")
        # Initialize OpenRouter client with default headers
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.settings.openrouter_api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/aayushp456/LangGraph-Assist-",
                "X-Title": "Support Copilot",
            },
        )
        # Use an embedding model available via OpenRouter
        self.model = getattr(self.settings, "embedding_model", "openai/text-embedding-3-small")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # Use OpenRouter embeddings endpoint (OpenAI-compatible)
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    def embed_text(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]
