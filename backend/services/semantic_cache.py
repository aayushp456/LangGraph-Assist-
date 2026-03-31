"""
Semantic Cache for RAG Retrieval
Caches query results based on semantic similarity to reduce latency and API calls
"""

from typing import Dict, List, Optional
import time
import hashlib
from collections import OrderedDict
import numpy as np


class SemanticCache:
    """
    Semantic cache that stores query results and matches similar queries
    using cosine similarity on embeddings.
    """
    
    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        """
        Initialize semantic cache.
        
        Args:
            max_size: Maximum number of cache entries (default: 500)
            ttl_seconds: Time-to-live for cache entries in seconds (default: 3600 = 1 hour)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, Dict] = OrderedDict()
        self.hits = 0
        self.misses = 0
        
    def _compute_cache_key(self, query_embedding: List[float]) -> str:
        """Create hash from embedding for exact match lookup"""
        # Convert to string and hash for fast lookup
        embedding_str = ','.join(f"{x:.6f}" for x in query_embedding[:10])  # Use first 10 dims
        return hashlib.md5(embedding_str.encode()).hexdigest()
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors"""
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def get(self, query: str, query_embedding: List[float], 
            similarity_threshold: float = 0.92) -> Optional[Dict]:
        """
        Get cached result if semantically similar query exists.
        
        Args:
            query: Original query text
            query_embedding: Query embedding vector
            similarity_threshold: Minimum cosine similarity (0.92 = very similar)
        
        Returns:
            Cached result if found, None otherwise
        """
        current_time = time.time()
        
        # Check for exact embedding match first (fastest path)
        cache_key = self._compute_cache_key(query_embedding)
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if current_time - entry['timestamp'] < self.ttl_seconds:
                # Move to end (LRU)
                self.cache.move_to_end(cache_key)
                self.hits += 1
                print(f"    [cache] EXACT HIT for query: '{query[:50]}...'")
                return entry['result']
            else:
                # Expired, remove
                del self.cache[cache_key]
        
        # Semantic similarity search (slower but catches variations)
        best_similarity = 0.0
        best_entry = None
        best_key = None
        
        for key, entry in list(self.cache.items()):
            # Check TTL
            if current_time - entry['timestamp'] >= self.ttl_seconds:
                del self.cache[key]
                continue
            
            # Compute cosine similarity
            similarity = self._cosine_similarity(
                query_embedding, 
                entry['query_embedding']
            )
            
            if similarity > best_similarity and similarity >= similarity_threshold:
                best_similarity = similarity
                best_entry = entry
                best_key = key
        
        if best_entry:
            # Move to end (LRU)
            if best_key:
                self.cache.move_to_end(best_key)
            self.hits += 1
            print(f"    [cache] SEMANTIC HIT: similarity={best_similarity:.3f} for query: '{query[:50]}...'")
            return best_entry['result']
        
        self.misses += 1
        print(f"    [cache] MISS for query: '{query[:50]}...'")
        return None
    
    def set(self, query: str, query_embedding: List[float], result: Dict):
        """
        Cache a query result.
        
        Args:
            query: Original query text
            query_embedding: Query embedding vector
            result: Result to cache (retrieval results, routing decision, etc.)
        """
        cache_key = self._compute_cache_key(query_embedding)
        
        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            print(f"    [cache] Evicted oldest entry (cache full)")
        
        self.cache[cache_key] = {
            'query': query,
            'query_embedding': query_embedding,
            'result': result,
            'timestamp': time.time()
        }
        print(f"    [cache] STORED result for query: '{query[:50]}...'")
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        print("    [cache] Cleared all entries")
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        current_time = time.time()
        valid_entries = sum(
            1 for entry in self.cache.values() 
            if current_time - entry['timestamp'] < self.ttl_seconds
        )
        
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_entries': len(self.cache),
            'valid_entries': valid_entries,
            'max_size': self.max_size,
            'ttl_seconds': self.ttl_seconds,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate_percent': round(hit_rate, 2),
            'total_requests': total_requests
        }
    
    def cleanup_expired(self):
        """Remove expired entries from cache"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time - entry['timestamp'] >= self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            print(f"    [cache] Cleaned up {len(expired_keys)} expired entries")
        
        return len(expired_keys)
