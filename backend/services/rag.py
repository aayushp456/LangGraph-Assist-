from typing import List, Optional, Dict, Any

from backend.services.llm import LLMProvider
from backend.services.store import SimpleVectorStore
from backend.services.summarizer import SummarizerService


class RAGRouterService:
    def __init__(
        self,
        llm: LLMProvider,
        store: Optional[SimpleVectorStore] = None,
        summarizer: Optional[SummarizerService] = None,
    ):
        self.llm = llm
        self.store = store
        self.summarizer = summarizer

    def route(self, message: str, top_k: int = 5) -> Dict[str, Any]:
        contexts: List[Dict[str, Any]] = []
        if self.store is not None and top_k > 0:
            try:
                contexts = self.store.search(message, top_k=top_k)
            except Exception:
                # If retrieval fails (e.g., embeddings auth), continue without context
                contexts = []

        context_text = "\n\n".join(
            [
                f"[score={c.get('score'):.3f}] {c.get('text')[:300]}"  # truncate text
                for c in contexts
            ]
        )
        system_prompt = (
            "You are a support routing agent. Use similar historical tickets if provided to inform your decision.\n"
            "Categories: FAQ, ESCALATE, SUMMARIZE.\n"
            "Return JSON: {\"category\": \"...\", \"confidence\": 0-1}."
        )
        user_content = (
            f"Ticket:\n{message}\n\n"
            f"Similar tickets (optional):\n{context_text if context_text else 'N/A'}\n"
        )
        result = self.llm.chat_json(system_prompt, user_content)
        # Attach context metadata for transparency
        result["top_matches"] = [
            {
                "id": c.get("id"),
                "score": c.get("score"),
                "metadata": c.get("metadata") or {},
                "text": (c.get("text") or "")[:300],
            }
            for c in contexts
        ]
        return result

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.store is None:
            raise RuntimeError("Vector store not configured (embeddings missing).")
        return self.store.search(query, top_k=top_k)

    def index(self, items: List[Dict[str, Any]]) -> int:
        if self.store is None:
            raise RuntimeError("Vector store not configured (embeddings missing).")
        texts = [i.get("text", "") for i in items]
        metas = [i.get("metadata") or {} for i in items]
        ids = [i.get("id") for i in items]
        return self.store.index_texts(texts, metas, ids)
