from __future__ import annotations

from typing import List, Optional

from langchain_openai import OpenAIEmbeddings

from backend.config import Settings


class EmbeddingsService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        if not self.settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for embeddings.")

        self._embeddings = OpenAIEmbeddings(
            model=self.settings.embedding_model,
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": self.settings.openrouter_site_url,
                "X-Title": self.settings.openrouter_app_name,
            },
        )

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self._embeddings.embed_documents(texts)

    def embed_text(self, text: str) -> List[float]:
        return self._embeddings.embed_query(text)
