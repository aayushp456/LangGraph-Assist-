"""
Pinecone Vector Store Implementation
Replaces FAISS with cloud-based Pinecone for scalable vector search
"""

from typing import List, Dict, Any, Optional
import uuid
from pinecone import Pinecone, ServerlessSpec
import time

from backend.services.embeddings import EmbeddingsService


class PineconeVectorStore:
    """
    Pinecone-based vector store for semantic search
    Provides cloud-based, scalable vector database
    """

    def __init__(
        self,
        embeddings_service: EmbeddingsService,
        api_key: str,
        index_name: str = "support-agent-kb",
        dimension: int = 1536,  # OpenAI embedding dimension
        metric: str = "cosine",
        cloud: str = "aws",
        region: str = "us-east-1"
    ):
        self.embeddings_service = embeddings_service
        self.index_name = index_name
        self.dimension = dimension

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=api_key)

        # Create index if it doesn't exist
        if index_name not in self.pc.list_indexes().names():
            print(f"Creating Pinecone index: {index_name}")
            self.pc.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
                spec=ServerlessSpec(
                    cloud=cloud,
                    region=region
                )
            )
            # Wait for index to be ready
            while not self.pc.describe_index(index_name).status['ready']:
                time.sleep(1)
            print(f"✓ Pinecone index '{index_name}' created")
        else:
            print(f"✓ Using existing Pinecone index: {index_name}")

        # Connect to index
        self.index = self.pc.Index(index_name)

    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        namespace: str = "knowledge_base"
    ) -> List[str]:
        """
        Add documents to Pinecone index

        Args:
            texts: List of text documents to add
            metadatas: Optional metadata for each document
            ids: Optional IDs for documents (auto-generated if not provided)

        Returns:
            List of document IDs
        """
        if not texts:
            return []

        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]

        # Generate embeddings
        embeddings = self.embeddings_service.embed_texts(texts)

        # Prepare metadata
        if metadatas is None:
            metadatas = [{} for _ in texts]

        # Add text to metadata for retrieval
        for i, text in enumerate(texts):
            metadatas[i]["text"] = text

        # Prepare vectors for upsert
        vectors = [
            {
                "id": doc_id,
                "values": embedding,
                "metadata": metadata
            }
            for doc_id, embedding, metadata in zip(ids, embeddings, metadatas)
        ]

        # Upsert to Pinecone in batches
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace=namespace)

        print(f"✓ Added {len(texts)} documents to Pinecone (namespace={namespace})")
        return ids

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        namespace: str = "knowledge_base"
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents

        Args:
            query: Search query text
            top_k: Number of results to return
            filter: Optional metadata filter

        Returns:
            List of matching documents with scores
        """
        # Generate query embedding
        query_embedding = self.embeddings_service.embed_query(query)

        # Search in Pinecone
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filter,
            include_metadata=True,
            namespace=namespace
        )

        # Format results
        documents = []
        for match in results.matches:
            doc = {
                "id": match.id,
                "score": float(match.score),
                "metadata": match.metadata,
                "text": match.metadata.get("text", "")
            }
            documents.append(doc)

        return documents

    def index_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        namespace: str = "knowledge_base"
    ) -> int:
        """
        Index texts into Pinecone (called by KB API and RAG service).
        Delegates to add_documents().

        Returns:
            Number of documents indexed
        """
        if not texts:
            return 0
        doc_ids = self.add_documents(texts, metadatas=metadatas, ids=ids, namespace=namespace)
        return len(doc_ids)

    def delete(self, ids: List[str], namespace: str = "knowledge_base") -> None:
        """Delete documents by IDs"""
        self.index.delete(ids=ids, namespace=namespace)
        print(f"✓ Deleted {len(ids)} documents from Pinecone (namespace={namespace})")

    def delete_all(self, namespace: Optional[str] = None) -> None:
        """Delete all documents from index. If namespace is None, clears all namespaces."""
        if namespace:
            self.index.delete(delete_all=True, namespace=namespace)
            print(f"✓ Deleted all documents from Pinecone (namespace={namespace})")
        else:
            # Clear both namespaces
            for ns in ["knowledge_base", "tickets"]:
                try:
                    self.index.delete(delete_all=True, namespace=ns)
                except Exception:
                    pass
            print("✓ Deleted all documents from all Pinecone namespaces")

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get index statistics, optionally filtered by namespace"""
        stats = self.index.describe_index_stats()
        result = {
            "total_vectors": stats.total_vector_count,
            "dimension": stats.dimension,
            "index_fullness": stats.index_fullness,
            "namespaces": {}
        }
        if hasattr(stats, 'namespaces') and stats.namespaces:
            for ns_name, ns_stats in stats.namespaces.items():
                result["namespaces"][ns_name] = {
                    "vector_count": ns_stats.vector_count
                }
        if namespace and namespace in result["namespaces"]:
            result["namespace_vectors"] = result["namespaces"][namespace]["vector_count"]
        return result

    def update_metadata(self, id: str, metadata: Dict[str, Any], namespace: str = "knowledge_base") -> None:
        """Update metadata for a document"""
        self.index.update(id=id, set_metadata=metadata, namespace=namespace)

    def fetch(self, ids: List[str], namespace: str = "knowledge_base") -> Dict[str, Any]:
        """Fetch documents by IDs"""
        return self.index.fetch(ids=ids, namespace=namespace)
