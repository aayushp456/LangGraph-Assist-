from typing import List, Dict, Any, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
import hashlib


class DocumentChunker:
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        if separators is None:
            separators = ["\n\n", "\n", ". ", " ", ""]
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
        )

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        source_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        chunks = self.splitter.split_text(text)
        
        result = []
        for i, chunk in enumerate(chunks):
            chunk_meta = metadata.copy() if metadata else {}
            chunk_meta["chunk_index"] = i
            chunk_meta["total_chunks"] = len(chunks)
            
            if source_id:
                chunk_meta["source_id"] = source_id
            
            result.append({
                "text": chunk,
                "metadata": chunk_meta,
                "id": self._generate_chunk_id(chunk, source_id, i),
            })
        
        return result

    def chunk_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        all_chunks = []
        
        for doc in documents:
            text = doc.get("text", "")
            metadata = doc.get("metadata") or {}
            source_id = doc.get("id")
            
            chunks = self.chunk_text(text, metadata, source_id)
            all_chunks.extend(chunks)
        
        return all_chunks

    @staticmethod
    def _generate_chunk_id(text: str, source_id: Optional[str], chunk_index: int) -> str:
        content = f"{source_id or ''}_{chunk_index}_{text[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    def compute_text_hash(text: str) -> str:
        normalized = " ".join(text.strip().split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def deduplicate_chunks(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        seen_hashes = set()
        unique_chunks = []
        
        for chunk in chunks:
            text = chunk.get("text", "")
            text_hash = self.compute_text_hash(text)
            
            if text_hash not in seen_hashes:
                seen_hashes.add(text_hash)
                chunk["text_hash"] = text_hash
                unique_chunks.append(chunk)
        
        return unique_chunks
