"""
Knowledge Base API endpoints — MongoDB-only, Pinecone knowledge_base namespace
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json

router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class IndexDocumentRequest(BaseModel):
    content: str = Field(..., description="Document content")
    title: Optional[str] = Field(None, description="Document title")
    category: Optional[str] = Field(None, description="Category: BUG, PERFORMANCE, API_ISSUE, SECURITY, INFRASTRUCTURE, FEATURE_REQUEST, GENERAL_INQUIRY")
    product: Optional[str] = Field(None, description="Product or service name")
    version: Optional[str] = Field(None, description="Product version")
    severity: Optional[str] = Field(None, description="Severity: SEV1-SEV4")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags")
    author: Optional[str] = Field(None, description="Author")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class BulkIndexRequest(BaseModel):
    documents: List[IndexDocumentRequest]


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = Field(5, description="Number of results to return")
    category_filter: Optional[str] = Field(None, description="Filter by category")
    min_score: Optional[float] = Field(0.0, description="Minimum similarity score")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/index")
async def index_document(request: IndexDocumentRequest):
    """
    Index a single document into the knowledge base.
    Stores in MongoDB + Pinecone knowledge_base namespace.
    """
    from backend.main import store, chunker
    from backend.db.repositories import KnowledgeBaseRepository

    if not store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        # 1. Save article to MongoDB
        article_data = {
            "title": request.title or "Untitled",
            "content": request.content,
            "category": (request.category or "GENERAL_INQUIRY").upper(),
            "product": request.product,
            "version": request.version,
            "severity": request.severity,
            "tags": request.tags or [],
            "author": request.author or "system",
        }
        article_id = await KnowledgeBaseRepository.create(article_data)

        # 2. Chunk and embed into Pinecone knowledge_base namespace
        chunk_metadata = {
            "article_id": article_id,
            "title": article_data["title"],
            "category": article_data["category"],
            "product": request.product or "",
            "severity": request.severity or "",
        }
        chunks = chunker.chunk_text(request.content, metadata=chunk_metadata)
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]

        store.index_texts(texts, metadatas=metadatas, namespace="knowledge_base")

        # Emit kb:updated so frontend refreshes via WebSocket
        try:
            from backend.websocket_manager import manager
            await manager.emit_event("kb:updated", {"action": "indexed", "article_id": article_id})
        except Exception:
            pass

        return {
            "success": True,
            "article_id": article_id,
            "chunks_created": len(chunks),
            "message": f"Indexed {len(chunks)} chunks from document",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@router.post("/index/bulk")
async def bulk_index_documents(request: BulkIndexRequest):
    results = []
    errors = []
    for idx, doc in enumerate(request.documents):
        try:
            result = await index_document(doc)
            results.append({"index": idx, "title": doc.title, **result})
        except Exception as e:
            errors.append({"index": idx, "title": doc.title, "error": str(e)})
    return {
        "total": len(request.documents),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


@router.post("/index/file")
async def index_file(
    file: UploadFile = File(...),
    category: Optional[str] = None,
    title: Optional[str] = None,
    product: Optional[str] = None,
):
    """Upload and index a file (txt, json, csv)"""
    from backend.main import store, chunker

    if not store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        content = await file.read()
        text = content.decode("utf-8")

        if file.filename and file.filename.endswith(".json"):
            data = json.loads(text)
            if isinstance(data, list):
                documents = []
                for item in data:
                    if isinstance(item, dict):
                        doc_content = item.get("text", "") or item.get("content", "") or str(item)
                        doc_title = item.get("title", "") or item.get("question", "")
                        doc_category = item.get("category", category or "GENERAL_INQUIRY")
                        documents.append(IndexDocumentRequest(
                            content=doc_content,
                            title=doc_title,
                            category=doc_category,
                            product=item.get("product", product),
                            tags=item.get("tags", []),
                            metadata=item,
                        ))
                return await bulk_index_documents(BulkIndexRequest(documents=documents))
            else:
                text = json.dumps(data, indent=2)

        doc_request = IndexDocumentRequest(
            content=text,
            title=title or file.filename,
            category=category or "GENERAL_INQUIRY",
            product=product,
        )
        return await index_document(doc_request)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File indexing failed: {str(e)}")


@router.post("/search")
async def semantic_search(request: SearchRequest):
    """Semantic search on the knowledge_base namespace in Pinecone."""
    from backend.main import store

    if not store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        results = store.search(
            request.query,
            top_k=request.top_k,
            namespace="knowledge_base",
        )

        if request.category_filter:
            results = [
                r for r in results
                if r.get("metadata", {}).get("category") == request.category_filter.upper()
            ]

        if request.min_score:
            results = [r for r in results if r.get("score", 0) >= request.min_score]

        return {"query": request.query, "total_results": len(results), "results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/stats")
async def get_kb_stats():
    """Get knowledge base statistics from MongoDB + Pinecone."""
    from backend.main import store
    from backend.db.repositories import KnowledgeBaseRepository

    mongo_stats = await KnowledgeBaseRepository.get_stats()

    stats: Dict[str, Any] = {
        "total_articles": mongo_stats.get("total", 0),
        "categories": mongo_stats.get("categories", {}),
    }

    if store:
        try:
            pinecone_stats = store.get_stats(namespace="knowledge_base")
            stats["vector_store"] = {
                "initialized": True,
                "provider": "pinecone",
                "total_vectors": pinecone_stats.get("total_vectors", 0),
                "kb_vectors": pinecone_stats.get("namespace_vectors", 0),
                "dimension": pinecone_stats.get("dimension", 0),
                "index_fullness": pinecone_stats.get("index_fullness", 0.0),
                "namespaces": pinecone_stats.get("namespaces", {}),
            }
        except Exception as e:
            stats["vector_store"] = {"initialized": True, "provider": "pinecone", "error": str(e)}
    else:
        stats["vector_store"] = {"initialized": False}

    return stats


@router.delete("/clear")
async def clear_knowledge_base():
    """Clear all KB entries from MongoDB + Pinecone knowledge_base namespace."""
    from backend.main import store
    from backend.db.repositories import KnowledgeBaseRepository

    try:
        deleted = await KnowledgeBaseRepository.clear_all()

        if store:
            store.delete_all(namespace="knowledge_base")

        # Emit kb:updated so frontend refreshes via WebSocket
        try:
            from backend.websocket_manager import manager
            await manager.emit_event("kb:updated", {"action": "cleared"})
        except Exception:
            pass

        return {
            "success": True,
            "message": f"Cleared {deleted} MongoDB articles + Pinecone knowledge_base namespace",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clear failed: {str(e)}")


@router.get("/list")
async def list_kb_articles(
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List all knowledge base articles from MongoDB."""
    from backend.db.repositories import KnowledgeBaseRepository

    articles = await KnowledgeBaseRepository.find_all(
        category=category.upper() if category else None,
        limit=limit,
        offset=offset,
    )
    total = await KnowledgeBaseRepository.count(
        {"category": category.upper()} if category else None
    )

    return {"total": total, "limit": limit, "offset": offset, "items": articles}
