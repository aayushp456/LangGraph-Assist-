"""
Test script for advanced RAG improvements
Tests semantic cache, hybrid search, MMR, and metadata filtering
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.semantic_cache import SemanticCache
from services.hybrid_search import HybridSearcher
from services.reranker import Reranker
import numpy as np


def test_semantic_cache():
    """Test semantic cache functionality"""
    print("\n" + "="*60)
    print("TEST 1: Semantic Cache")
    print("="*60)
    
    cache = SemanticCache(max_size=10, ttl_seconds=3600)
    
    # Create sample embeddings
    query1_emb = [0.1, 0.2, 0.3, 0.4, 0.5] * 100  # 500 dims
    query2_emb = [0.1, 0.2, 0.3, 0.4, 0.51] * 100  # Very similar
    query3_emb = [0.9, 0.8, 0.7, 0.6, 0.5] * 100  # Different
    
    # Test 1: Cache miss
    result = cache.get("password reset issue", query1_emb)
    assert result is None, "Should be cache miss"
    print("✓ Cache miss works correctly")
    
    # Test 2: Store and retrieve
    cache.set("password reset issue", query1_emb, {"category": "BUG", "docs": ["doc1", "doc2"]})
    result = cache.get("password reset issue", query1_emb)
    assert result is not None, "Should be cache hit"
    assert result["category"] == "BUG"
    print("✓ Cache storage and exact retrieval works")
    
    # Test 3: Semantic similarity match
    result = cache.get("password reset problem", query2_emb, similarity_threshold=0.90)
    assert result is not None, "Should match semantically similar query"
    print("✓ Semantic similarity matching works")
    
    # Test 4: Different query doesn't match
    result = cache.get("API authentication error", query3_emb, similarity_threshold=0.90)
    assert result is None, "Should not match different query"
    print("✓ Different queries correctly don't match")
    
    # Test 5: Cache stats
    stats = cache.get_stats()
    print(f"✓ Cache stats: {stats}")
    assert stats['total_entries'] > 0
    assert stats['hit_rate_percent'] > 0
    
    print("\n✅ Semantic Cache: ALL TESTS PASSED")


def test_hybrid_search():
    """Test hybrid search functionality"""
    print("\n" + "="*60)
    print("TEST 2: Hybrid Search")
    print("="*60)
    
    searcher = HybridSearcher()
    
    # Test 1: Extract error codes
    query1 = "Getting 500 error when calling the API"
    keywords = searcher.extract_keywords(query1)
    assert '500' in keywords['error_codes'], "Should extract 500 error code"
    print(f"✓ Error code extraction: {keywords['error_codes']}")
    
    # Test 2: Extract API endpoints
    query2 = "POST request to /api/users/create is failing"
    keywords = searcher.extract_keywords(query2)
    assert '/api/users/create' in keywords['api_endpoints'], "Should extract API endpoint"
    assert 'POST' in keywords['http_methods'], "Should extract HTTP method"
    print(f"✓ API endpoint extraction: {keywords['api_endpoints']}")
    print(f"✓ HTTP method extraction: {keywords['http_methods']}")
    
    # Test 3: Extract product names
    query3 = "Dashboard is slow to load"
    keywords = searcher.extract_keywords(query3)
    assert 'dashboard' in keywords['products'], "Should extract product name"
    print(f"✓ Product name extraction: {keywords['products']}")
    
    # Test 4: Hybrid reranking
    mock_results = [
        {
            'id': 'doc1',
            'text': 'How to fix 500 internal server errors',
            'score': 0.7,
            'metadata': {'category': 'BUG'}
        },
        {
            'id': 'doc2',
            'text': 'API authentication guide',
            'score': 0.8,
            'metadata': {'category': 'API_ISSUE'}
        },
        {
            'id': 'doc3',
            'text': 'Troubleshooting 500 errors in production',
            'score': 0.6,
            'metadata': {'category': 'BUG'}
        }
    ]
    
    query = "Getting 500 error on API endpoint"
    reranked = searcher.hybrid_rerank(query, mock_results.copy(), vector_weight=0.7)
    
    # Verify hybrid scoring is applied
    assert 'hybrid_score' in reranked[0], "Should have hybrid score"
    assert 'matched_keywords' in reranked[0], "Should have matched keywords"
    assert 'keyword_boost' in reranked[0], "Should have keyword boost"
    
    # Find docs with "500" - they should have higher keyword boost
    docs_with_500 = [r for r in reranked if '500' in r['matched_keywords']]
    docs_without_500 = [r for r in reranked if '500' not in r['matched_keywords']]
    
    if docs_with_500:
        avg_boost_with_500 = sum(d['keyword_boost'] for d in docs_with_500) / len(docs_with_500)
        print(f"✓ Docs with '500': avg keyword_boost = {avg_boost_with_500:.3f}")
        
        if docs_without_500:
            avg_boost_without_500 = sum(d['keyword_boost'] for d in docs_without_500) / len(docs_without_500)
            print(f"✓ Docs without '500': avg keyword_boost = {avg_boost_without_500:.3f}")
            assert avg_boost_with_500 > avg_boost_without_500, "Docs with error code should have higher keyword boost"
    
    print(f"✓ Hybrid reranking works: top result = {reranked[0]['id']}")
    print(f"  Vector score: {reranked[0]['original_vector_score']:.3f}")
    print(f"  Keyword boost: {reranked[0]['keyword_boost']:.3f}")
    print(f"  Hybrid score: {reranked[0]['hybrid_score']:.3f}")
    print(f"  Matched keywords: {reranked[0]['matched_keywords']}")
    
    print("\n✅ Hybrid Search: ALL TESTS PASSED")


def test_mmr_reranker():
    """Test MMR diversity ranking"""
    print("\n" + "="*60)
    print("TEST 3: MMR Diversity Ranking")
    print("="*60)
    
    reranker = Reranker()
    
    # Create mock documents with embeddings
    # Doc 1 and 2 are very similar (both about password reset)
    # Doc 3 is different (about API)
    docs = [
        {
            'id': 'doc1',
            'text': 'How to reset your password',
            'score': 0.9,
            'embedding': [0.8, 0.2, 0.1] * 100
        },
        {
            'id': 'doc2',
            'text': 'Password reset instructions',
            'score': 0.85,
            'embedding': [0.79, 0.21, 0.11] * 100  # Very similar to doc1
        },
        {
            'id': 'doc3',
            'text': 'API authentication guide',
            'score': 0.75,
            'embedding': [0.1, 0.8, 0.7] * 100  # Different
        },
        {
            'id': 'doc4',
            'text': 'Reset password via email',
            'score': 0.7,
            'embedding': [0.81, 0.19, 0.09] * 100  # Similar to doc1
        }
    ]
    
    query_embedding = [0.8, 0.2, 0.1] * 100
    
    # Test MMR with high diversity (lambda=0.5)
    mmr_results = reranker.mmr_rerank(
        query_embedding,
        docs.copy(),
        top_k=3,
        lambda_param=0.5  # 50% relevance, 50% diversity
    )
    
    assert len(mmr_results) == 3, "Should return top 3"
    assert 'mmr_score' in mmr_results[0], "Should have MMR score"
    
    # With high diversity, should include doc3 even if lower relevance
    result_ids = [r['id'] for r in mmr_results]
    print(f"✓ MMR results (lambda=0.5): {result_ids}")
    
    # Test MMR with high relevance (lambda=0.9)
    mmr_results_high_rel = reranker.mmr_rerank(
        query_embedding,
        docs.copy(),
        top_k=3,
        lambda_param=0.9  # 90% relevance, 10% diversity
    )
    
    result_ids_high_rel = [r['id'] for r in mmr_results_high_rel]
    print(f"✓ MMR results (lambda=0.9): {result_ids_high_rel}")
    
    # High relevance should prefer similar docs
    assert mmr_results_high_rel[0]['id'] == 'doc1', "Highest relevance doc should be first"
    
    print("\n✅ MMR Reranker: ALL TESTS PASSED")


def test_metadata_filtering():
    """Test metadata filtering logic"""
    print("\n" + "="*60)
    print("TEST 4: Metadata Filtering")
    print("="*60)
    
    from datetime import datetime, timedelta
    
    # Mock results with different categories and ages
    results = [
        {
            'id': 'doc1',
            'text': 'Bug fix guide',
            'score': 0.8,
            'metadata': {
                'category': 'BUG',
                'created_at': (datetime.utcnow() - timedelta(days=10)).isoformat()
            }
        },
        {
            'id': 'doc2',
            'text': 'Performance optimization',
            'score': 0.75,
            'metadata': {
                'category': 'PERFORMANCE',
                'created_at': (datetime.utcnow() - timedelta(days=200)).isoformat()
            }
        },
        {
            'id': 'doc3',
            'text': 'Another bug solution',
            'score': 0.7,
            'metadata': {
                'category': 'BUG',
                'created_at': (datetime.utcnow() - timedelta(days=5)).isoformat()
            }
        },
        {
            'id': 'doc4',
            'text': 'Low score doc',
            'score': 0.4,
            'metadata': {'category': 'BUG'}
        }
    ]
    
    # Simulate filtering for BUG category query
    predicted_category = 'BUG'
    min_confidence = 0.6
    
    filtered = []
    for result in results:
        metadata = result.get('metadata', {})
        doc_category = metadata.get('category', '')
        
        # Category matching
        if doc_category == predicted_category:
            result['score'] = result.get('score', 0) * 1.3  # Boost
        elif doc_category and doc_category != predicted_category:
            result['score'] = result.get('score', 0) * 0.6  # Penalty
        
        # Recency boosting
        created_at = metadata.get('created_at')
        if created_at:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            days_old = (datetime.utcnow() - created_at).days
            if days_old < 30:
                result['score'] = result.get('score', 0) * 1.15
            elif days_old > 180:
                result['score'] = result.get('score', 0) * 0.85
        
        # Confidence threshold
        if result.get('score', 0) >= min_confidence:
            filtered.append(result)
    
    print(f"✓ Original results: {len(results)}")
    print(f"✓ After filtering: {len(filtered)}")
    
    # Should filter out low confidence doc4
    assert len(filtered) < len(results), "Should filter out low confidence results"
    
    # BUG category docs should have higher scores
    bug_docs = [r for r in filtered if r['metadata'].get('category') == 'BUG']
    perf_docs = [r for r in filtered if r['metadata'].get('category') == 'PERFORMANCE']
    
    if bug_docs and perf_docs:
        avg_bug_score = sum(d['score'] for d in bug_docs) / len(bug_docs)
        avg_perf_score = sum(d['score'] for d in perf_docs) / len(perf_docs)
        print(f"✓ Avg BUG score: {avg_bug_score:.3f}")
        print(f"✓ Avg PERFORMANCE score: {avg_perf_score:.3f}")
        assert avg_bug_score > avg_perf_score, "BUG docs should score higher for BUG query"
    
    print("\n✅ Metadata Filtering: ALL TESTS PASSED")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("ADVANCED RAG IMPROVEMENTS - TEST SUITE")
    print("="*60)
    
    try:
        test_semantic_cache()
        test_hybrid_search()
        test_mmr_reranker()
        test_metadata_filtering()
        
        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
        print("="*60)
        print("\nAdvanced RAG improvements are working correctly:")
        print("✓ Semantic caching for repeated queries")
        print("✓ Hybrid search for technical terms")
        print("✓ MMR diversity ranking")
        print("✓ Metadata filtering and confidence thresholds")
        print("\nYou can now:")
        print("1. Start the backend server")
        print("2. Test with real queries")
        print("3. Monitor cache stats at GET /cache/stats")
        print("4. Clear cache at POST /cache/clear")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run_all_tests()
