import os
import json
import uuid
import pickle
from pathlib import Path
from typing import List, Optional, Dict, Any

import faiss
import numpy as np

from backend.services.embeddings import EmbeddingsService


class FAISSVectorStore:
    def __init__(
        self,
        embeddings: EmbeddingsService,
        index_path: str = "backend/data/index.faiss",
        meta_path: str = "backend/data/meta.json",
    ):
        self.embeddings = embeddings
        self.index_path = index_path
        self.meta_path = meta_path
        self.dimension = embeddings.settings.embedding_dim
        self.index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []
        self._ensure_dir()
        self._load_or_create_index()

    def _ensure_dir(self):
        for path in [self.index_path, self.meta_path]:
            d = os.path.dirname(path)
            if d and not os.path.exists(d):
                os.makedirs(d, exist_ok=True)

    def _load_or_create_index(self):
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.meta_path, "r") as f:
                    self.metadata = json.load(f)
            except Exception as e:
                print(f"Failed to load existing index: {e}. Creating new index.")
                self._create_new_index()
        else:
            self._create_new_index()

    def _create_new_index(self):
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []

    def _save_index(self):
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w") as f:
            json.dump(self.metadata, f)

    def index_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> int:
        if not texts:
            return 0

        embs = self.embeddings.embed_texts(texts)
        vectors = np.array(embs, dtype=np.float32)

        current_count = self.index.ntotal
        self.index.add(vectors)

        for i, text in enumerate(texts):
            meta = {
                "id": (ids[i] if ids and i < len(ids) else str(uuid.uuid4())),
                "text": text,
                "metadata": (metadatas[i] if metadatas and i < len(metadatas) else {}),
                "index_position": current_count + i,
            }
            self.metadata.append(meta)

        self._save_index()
        return len(texts)

    def count(self) -> int:
        return self.index.ntotal if self.index else 0

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.index or self.index.ntotal == 0:
            return []

        q_emb = self.embeddings.embed_text(query)
        q_vec = np.array([q_emb], dtype=np.float32)

        k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(q_vec, k)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            # Convert L2 distance to similarity score (inverse, normalized to 0-1 range)
            # Lower distance = higher similarity
            distance = float(distances[0][i])
            score = 1.0 / (1.0 + distance)
            
            results.append({
                "id": meta.get("id"),
                "text": meta.get("text"),
                "metadata": meta.get("metadata") or {},
                "score": score,
            })

        return results

    def clear(self):
        self._create_new_index()
        self._save_index()

    def migrate_from_jsonl(self, jsonl_path: str) -> int:
        if not os.path.exists(jsonl_path):
            return 0

        texts = []
        metadatas = []
        ids = []

        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    texts.append(entry.get("text", ""))
                    metadatas.append(entry.get("metadata") or {})
                    ids.append(entry.get("id"))
                except Exception:
                    continue

        if texts:
            return self.index_texts(texts, metadatas, ids)
        return 0
