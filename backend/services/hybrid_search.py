"""
Hybrid Search for RAG Retrieval
Combines vector search with keyword matching for technical terms
"""

import re
from typing import List, Dict, Set, Optional


class HybridSearcher:
    """
    Hybrid search that combines vector similarity with keyword matching.
    Particularly useful for technical queries with error codes, API endpoints, etc.
    """
    
    def __init__(self, product_names: Optional[Set[str]] = None):
        """
        Initialize hybrid searcher.
        
        Args:
            product_names: Set of product names to match (e.g., {'dashboard', 'api', 'mobile app'})
        """
        # Patterns for technical term extraction
        self.error_code_pattern = re.compile(r'\b[45]\d{2}\b')  # 4xx, 5xx error codes
        self.api_endpoint_pattern = re.compile(r'/api/[\w/-]+')  # API endpoints
        self.http_method_pattern = re.compile(r'\b(GET|POST|PUT|DELETE|PATCH)\b', re.IGNORECASE)
        
        # Product names (can be configured)
        self.product_names = product_names or {
            'dashboard', 'api', 'platform', 'mobile app', 'web app',
            'backend', 'frontend', 'database', 'server'
        }
        
        # Common technical terms
        self.technical_terms = {
            'authentication', 'authorization', 'oauth', 'jwt', 'token',
            'ssl', 'tls', 'https', 'cors', 'webhook', 'websocket',
            'timeout', 'latency', 'memory', 'cpu', 'disk', 'cache',
            'deployment', 'scaling', 'cluster', 'load balancer'
        }
    
    def extract_keywords(self, query: str) -> Dict[str, Set[str]]:
        """
        Extract technical keywords from query.
        
        Args:
            query: Search query
            
        Returns:
            Dictionary with categorized keywords
        """
        keywords = {
            'error_codes': set(),
            'api_endpoints': set(),
            'http_methods': set(),
            'products': set(),
            'technical_terms': set()
        }
        
        # Error codes (4xx, 5xx)
        error_codes = self.error_code_pattern.findall(query)
        keywords['error_codes'].update(error_codes)
        
        # API endpoints
        endpoints = self.api_endpoint_pattern.findall(query)
        keywords['api_endpoints'].update(endpoints)
        
        # HTTP methods
        methods = self.http_method_pattern.findall(query)
        keywords['http_methods'].update([m.upper() for m in methods])
        
        # Product names
        query_lower = query.lower()
        for product in self.product_names:
            if product in query_lower:
                keywords['products'].add(product)
        
        # Technical terms
        for term in self.technical_terms:
            if term in query_lower:
                keywords['technical_terms'].add(term)
        
        return keywords
    
    def get_all_keywords(self, keywords_dict: Dict[str, Set[str]]) -> Set[str]:
        """Get all keywords as a flat set"""
        all_keywords = set()
        for keyword_set in keywords_dict.values():
            all_keywords.update(keyword_set)
        return all_keywords
    
    def keyword_match_score(self, keywords: Set[str], document: str) -> float:
        """
        Calculate keyword match score for a document.
        
        Args:
            keywords: Set of keywords to match
            document: Document text
            
        Returns:
            Match score between 0.0 and 1.0
        """
        if not keywords:
            return 0.0
        
        doc_lower = document.lower()
        matches = sum(1 for kw in keywords if kw.lower() in doc_lower)
        
        return matches / len(keywords)  # Percentage of keywords matched
    
    def calculate_keyword_boost(
        self, 
        keywords_dict: Dict[str, Set[str]], 
        document: str
    ) -> float:
        """
        Calculate keyword boost with weighted importance.
        
        Args:
            keywords_dict: Categorized keywords
            document: Document text
            
        Returns:
            Boost score (higher = more keyword matches)
        """
        doc_lower = document.lower()
        boost = 0.0
        
        # Error codes: highest weight (exact match is critical)
        for error_code in keywords_dict['error_codes']:
            if error_code in doc_lower:
                boost += 0.6  # Very high boost for error code match
        
        # API endpoints: high weight
        for endpoint in keywords_dict['api_endpoints']:
            if endpoint.lower() in doc_lower:
                boost += 0.5
        
        # HTTP methods: medium weight
        for method in keywords_dict['http_methods']:
            if method.lower() in doc_lower:
                boost += 0.3
        
        # Products: medium weight
        for product in keywords_dict['products']:
            if product in doc_lower:
                boost += 0.4
        
        # Technical terms: lower weight (more common)
        for term in keywords_dict['technical_terms']:
            if term in doc_lower:
                boost += 0.2
        
        return min(boost, 1.5)  # Cap at 1.5 to allow strong keyword matches to dominate
    
    def hybrid_rerank(
        self, 
        query: str, 
        vector_results: List[Dict], 
        vector_weight: float = 0.7
    ) -> List[Dict]:
        """
        Combine vector search with keyword matching.
        
        Args:
            query: Original query
            vector_results: Results from vector search
            vector_weight: Weight for vector score (0.7 = 70% vector, 30% keyword)
        
        Returns:
            Reranked results with hybrid scores
        """
        keywords_dict = self.extract_keywords(query)
        all_keywords = self.get_all_keywords(keywords_dict)
        
        if not all_keywords:
            # No keywords found, return vector results as-is
            print(f"    [hybrid] No keywords extracted, using vector scores only")
            return vector_results
        
        print(f"    [hybrid] Extracted keywords: {all_keywords}")
        
        keyword_weight = 1.0 - vector_weight
        
        for result in vector_results:
            # Get document text (combine text and metadata)
            doc_text = result.get('text', '')
            metadata = result.get('metadata', {})
            metadata_text = ' '.join(str(v) for v in metadata.values())
            full_text = f"{doc_text} {metadata_text}"
            
            # Calculate keyword boost
            keyword_boost = self.calculate_keyword_boost(keywords_dict, full_text)
            
            # Get matched keywords for transparency
            matched = [kw for kw in all_keywords if kw.lower() in full_text.lower()]
            
            # Combine scores
            vector_score = result.get('score', 0.0)
            hybrid_score = (vector_weight * vector_score) + (keyword_weight * keyword_boost)
            
            # Store hybrid search metadata
            result['hybrid_score'] = hybrid_score
            result['keyword_boost'] = keyword_boost
            result['matched_keywords'] = matched
            result['original_vector_score'] = vector_score
        
        # Sort by hybrid score
        vector_results.sort(key=lambda x: x.get('hybrid_score', 0), reverse=True)
        
        # Log top results
        if vector_results:
            top_result = vector_results[0]
            print(f"    [hybrid] Top result: vector={top_result.get('original_vector_score', 0):.3f}, "
                  f"keyword={top_result.get('keyword_boost', 0):.3f}, "
                  f"hybrid={top_result.get('hybrid_score', 0):.3f}, "
                  f"matched={top_result.get('matched_keywords', [])}")
        
        return vector_results
    
    def is_technical_query(self, query: str) -> bool:
        """
        Determine if query contains technical terms.
        
        Args:
            query: Search query
            
        Returns:
            True if query has technical keywords
        """
        keywords_dict = self.extract_keywords(query)
        all_keywords = self.get_all_keywords(keywords_dict)
        return len(all_keywords) > 0
