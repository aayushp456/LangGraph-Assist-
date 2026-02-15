import os
import json
import uuid
from typing import List, Optional, Dict, Any

import numpy as np

from backend.services.embeddings import EmbeddingsService


class SimpleVectorStore:
    def __init__(self, embeddings: EmbeddingsService, store_path: str = "backend/data/index.jsonl"):
        self.embeddings = embeddings
        self.store_path = store_path
        self._ensure_dir()

    def _ensure_dir(self):
        d = os.path.dirname(self.store_path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        if not os.path.exists(self.store_path):
            with open(self.store_path, "w") as f:
                pass

    def _iter_entries(self):
        if not os.path.exists(self.store_path):
            return
        with open(self.store_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue

    def _append_entries(self, entries: List[Dict[str, Any]]):
        with open(self.store_path, "a") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def index_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None, ids: Optional[List[str]] = None) -> int:
        if not texts:
            return 0
        embs = self.embeddings.embed_texts(texts)
        items = []
        for i, text in enumerate(texts):
            item = {
                "id": (ids[i] if ids and i < len(ids) else str(uuid.uuid4())),
                "text": text,
                "embedding": embs[i],
                "metadata": (metadatas[i] if metadatas and i < len(metadatas) else {}),
            }
            items.append(item)
        self._append_entries(items)
        return len(items)

    def count(self) -> int:
        return sum(1 for _ in self._iter_entries())

    @staticmethod
    def _cos_sim(a: np.ndarray, b: np.ndarray) -> float:
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        q = np.array(self.embeddings.embed_text(query), dtype=np.float32)
        results = []
        for e in self._iter_entries():
            v = np.array(e.get("embedding") or [], dtype=np.float32)
            if v.size == 0:
                continue
            score = self._cos_sim(q, v)
            results.append({
                "id": e.get("id"),
                "text": e.get("text"),
                "metadata": e.get("metadata") or {},
                "score": score,
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[: max(1, top_k)]
