from typing import List, Dict, Any, Optional
from sentence_transformers import CrossEncoder
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model: Optional[CrossEncoder] = None

    def _load_model(self):
        if self._model is None:
            try:
                self._model = CrossEncoder(self.model_name)
            except Exception as e:
                print(f"Failed to load reranker model: {e}")
                self._model = None

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        if not documents:
            return []

        self._load_model()
        
        if self._model is None:
            return documents[:top_k]

        try:
            texts = [doc.get("text", "") for doc in documents]
            pairs = [[query, text] for text in texts]
            
            scores = self._model.predict(pairs)
            
            for i, doc in enumerate(documents):
                doc["rerank_score"] = float(scores[i])
            
            reranked = sorted(documents, key=lambda x: x.get("rerank_score", 0), reverse=True)
            
            return reranked[:top_k]
        except Exception as e:
            print(f"Reranking failed: {e}")
            return documents[:top_k]

    def rerank_simple(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Fallback heuristic-based reranking without ML model"""
        if not documents:
            return []

        query_terms = set(query.lower().split())
        
        for doc in documents:
            text = doc.get("text", "").lower()
            text_terms = set(text.split())
            
            # Calculate term overlap
            overlap = len(query_terms & text_terms)
            
            # Boost score based on overlap
            original_score = doc.get("score", 0)
            boost = overlap * 0.1
            doc["rerank_score"] = original_score + boost
        
        reranked = sorted(documents, key=lambda x: x.get("rerank_score", 0), reverse=True)
        return reranked[:top_k]
    
    def mmr_rerank(
        self,
        query_embedding: List[float],
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        lambda_param: float = 0.7,
        embedding_key: str = "embedding"
    ) -> List[Dict[str, Any]]:
        """
        Maximal Marginal Relevance (MMR) reranking.
        Balances relevance to query with diversity among results.
        
        Args:
            query_embedding: Query embedding vector
            documents: List of documents with embeddings
            top_k: Number of results to return
            lambda_param: Trade-off between relevance (1.0) and diversity (0.0)
                         Default 0.7 = 70% relevance, 30% diversity
            embedding_key: Key in document dict containing embedding
        
        Returns:
            Reranked documents with MMR scores
        """
        if not documents or top_k <= 0:
            return []
        
        # Filter documents that have embeddings
        docs_with_embeddings = [
            doc for doc in documents 
            if embedding_key in doc and doc[embedding_key] is not None
        ]
        
        if not docs_with_embeddings:
            # Fallback: return by original score
            return sorted(documents, key=lambda x: x.get("score", 0), reverse=True)[:top_k]
        
        try:
            # Convert to numpy arrays
            query_emb = np.array(query_embedding).reshape(1, -1)
            doc_embeddings = np.array([doc[embedding_key] for doc in docs_with_embeddings])
            
            # Calculate relevance scores (similarity to query)
            relevance_scores = cosine_similarity(query_emb, doc_embeddings)[0]
            
            # MMR algorithm
            selected_indices = []
            remaining_indices = list(range(len(docs_with_embeddings)))
            
            while len(selected_indices) < min(top_k, len(docs_with_embeddings)):
                best_score = -float('inf')
                best_idx = None
                
                for idx in remaining_indices:
                    # Relevance component
                    relevance = relevance_scores[idx]
                    
                    # Diversity component (max similarity to already selected)
                    if selected_indices:
                        selected_embeddings = doc_embeddings[selected_indices]
                        current_embedding = doc_embeddings[idx].reshape(1, -1)
                        similarities = cosine_similarity(current_embedding, selected_embeddings)[0]
                        max_similarity = np.max(similarities)
                    else:
                        max_similarity = 0.0
                    
                    # MMR score: balance relevance and diversity
                    mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                    
                    if mmr_score > best_score:
                        best_score = mmr_score
                        best_idx = idx
                
                if best_idx is not None:
                    selected_indices.append(best_idx)
                    remaining_indices.remove(best_idx)
                else:
                    break
            
            # Build result with MMR scores
            result = []
            for rank, idx in enumerate(selected_indices):
                doc = docs_with_embeddings[idx].copy()
                doc['mmr_score'] = float(relevance_scores[idx])
                doc['mmr_rank'] = rank + 1
                result.append(doc)
            
            return result
            
        except Exception as e:
            print(f"MMR reranking failed: {e}")
            # Fallback to original order
            return sorted(documents, key=lambda x: x.get("score", 0), reverse=True)[:top_k]
    
    def combined_rerank(
        self,
        query: str,
        query_embedding: Optional[List[float]],
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        use_mmr: bool = True,
        mmr_lambda: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Combined reranking: Cross-encoder + MMR for best results.
        
        Args:
            query: Query text
            query_embedding: Query embedding (for MMR)
            documents: Documents to rerank
            top_k: Number of results
            use_mmr: Whether to apply MMR after cross-encoder
            mmr_lambda: MMR relevance/diversity trade-off
        
        Returns:
            Reranked documents
        """
        if not documents:
            return []
        
        # Step 1: Cross-encoder reranking (get more candidates)
        cross_encoder_k = min(top_k * 2, len(documents))
        reranked = self.rerank(query, documents, top_k=cross_encoder_k)
        
        # Step 2: MMR for diversity (if enabled and embeddings available)
        if use_mmr and query_embedding and len(reranked) > top_k:
            reranked = self.mmr_rerank(
                query_embedding,
                reranked,
                top_k=top_k,
                lambda_param=mmr_lambda
            )
        else:
            reranked = reranked[:top_k]
        
        return reranked
