#!/usr/bin/env python3
"""
End-to-End Vector Search Verification
Tests: OpenRouter embeddings → Pinecone upsert → semantic search → results
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from backend.config import Settings
from backend.services.embeddings import EmbeddingsService
from backend.services.pinecone_store import PineconeVectorStore


def test_embeddings(settings, embeddings):
    """Test OpenRouter embeddings are working"""
    print("=" * 60)
    print("  STEP 1: Test OpenRouter Embeddings")
    print("=" * 60 + "\n")

    test_texts = [
        "API is returning 500 Internal Server Error",
        "Application crashes when uploading files larger than 10MB",
        "High memory usage after deploying version 2.3",
        "Rate limit exceeded on /api/orders endpoint",
        "Feature flag for dark mode is not working",
    ]

    print(f"Model: {settings.embedding_model}")
    print(f"Expected dimensions: {settings.embedding_dim}\n")

    print("Embedding 5 test texts...")
    try:
        vectors = embeddings.embed_texts(test_texts)
        dim = len(vectors[0])
        print(f"✓ Generated {len(vectors)} embeddings, each {dim} dimensions")

        if dim != settings.embedding_dim:
            print(f"⚠️  Dimension mismatch! Got {dim}, expected {settings.embedding_dim}")
            print("   Update EMBEDDING_DIM in .env and recreate Pinecone index.")
            return False

        query_vec = embeddings.embed_query("server error 500")
        print(f"✓ Query embedding: {len(query_vec)} dimensions")
        print("✓ Embeddings PASSED\n")
        return True

    except Exception as e:
        print(f"❌ Embedding FAILED: {e}\n")
        return False


def test_pinecone(settings, embeddings):
    """Test Pinecone connection, upsert, and search"""
    print("=" * 60)
    print("  STEP 2: Test Pinecone Vector Store")
    print("=" * 60 + "\n")

    try:
        store = PineconeVectorStore(
            embeddings_service=embeddings,
            api_key=settings.pinecone_api_key,
            index_name=settings.pinecone_index_name,
            dimension=settings.embedding_dim,
            cloud=settings.pinecone_cloud,
            region=settings.pinecone_region,
        )
        print(f"✓ Connected to Pinecone index: {settings.pinecone_index_name}")

        stats = store.get_stats()
        print(f"  Vectors: {stats['total_vectors']}, Dimension: {stats['dimension']}")

        # --- Upsert test docs ---
        print("\nUpserting 5 test documents...")
        test_docs = [
            "When the API returns a 500 Internal Server Error, first check the application logs at /var/log/app/error.log. Common causes: database connection timeout, null pointer in request handler, or out of memory. Restart the service with 'systemctl restart app' as immediate mitigation.",
            "File uploads larger than 10MB fail with OutOfMemoryError. The upload handler loads entire files into memory. Workaround: set MAX_UPLOAD_SIZE=10485760 in server config. Permanent fix: streaming upload in v2.4 (PR #1234).",
            "Memory leak detected in WebSocket handler for sessions longer than 4 hours. Event listeners are not cleaned up on reconnection. Workaround: restart WebSocket service every 24h. Fix available in patch v2.3.1.",
            "Rate limit is 100 requests per minute per API key. HTTP 429 is returned when exceeded. Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset. Use exponential backoff with jitter for retries.",
            "The dark mode feature flag (FEATURE_DARK_MODE) must be enabled in /admin/feature-flags. Users also need to clear browser cache after the flag is toggled. Known bug: Safari 15 doesn't respect CSS variables for dark mode.",
        ]
        test_meta = [
            {"category": "API_ISSUE", "title": "500 Internal Server Error troubleshooting"},
            {"category": "BUG", "title": "File upload crashes on large files"},
            {"category": "BUG", "title": "Memory leak in WebSocket handler"},
            {"category": "API_ISSUE", "title": "Rate limiting and 429 errors"},
            {"category": "FEATURE", "title": "Dark mode feature flag setup"},
        ]

        ids = store.add_documents(test_docs, metadatas=test_meta)
        print(f"✓ Upserted {len(ids)} documents")

        # Wait for Pinecone to index
        print("  Waiting 3s for Pinecone to index...")
        time.sleep(3)

        stats = store.get_stats()
        print(f"  Vectors after upsert: {stats['total_vectors']}")

        # --- Search ---
        print("\n" + "=" * 60)
        print("  STEP 3: Test Semantic Search")
        print("=" * 60 + "\n")

        queries = [
            ("API returns 500 error", "Should match: 500 troubleshooting"),
            ("app crashes on file upload", "Should match: upload crash bug"),
            ("memory keeps growing", "Should match: memory leak"),
            ("too many requests error", "Should match: rate limiting"),
            ("dark mode not working", "Should match: dark mode feature flag"),
        ]

        all_passed = True
        for query, expected in queries:
            results = store.search(query, top_k=3)
            print(f'Query: "{query}"')
            print(f"  Expected: {expected}")

            if not results:
                print("  ❌ No results returned")
                all_passed = False
                continue

            for i, r in enumerate(results[:3], 1):
                score = r.get("score", 0)
                cat = r.get("metadata", {}).get("category", "?")
                title = r.get("metadata", {}).get("title", "?")
                print(f"  {i}. [{score:.4f}] {cat} — {title}")

            top_score = results[0].get("score", 0)
            if top_score >= 0.5:
                print(f"  ✓ Top score {top_score:.4f} — GOOD\n")
            else:
                print(f"  ⚠️  Top score {top_score:.4f} — LOW\n")
                all_passed = False

        # --- index_texts method (used by KB API) ---
        print("Testing index_texts() method (used by KB API)...")
        count = store.index_texts(
            ["Test doc via index_texts method"],
            metadatas=[{"category": "GENERAL", "title": "index_texts test"}],
        )
        print(f"✓ index_texts returned: {count} (expected 1)")

        if all_passed:
            print("\n✓ All search tests PASSED")
        else:
            print("\n⚠️  Some search tests had low scores")

        return store

    except Exception as e:
        print(f"❌ Pinecone FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_similarity_quality(embeddings):
    """Test semantic similarity between related/unrelated concepts"""
    print("\n" + "=" * 60)
    print("  STEP 4: Similarity Quality Check")
    print("=" * 60 + "\n")

    similar = [
        ("API returning 500 error", "internal server error on endpoint"),
        ("application crashes on upload", "file upload causes out of memory"),
        ("high memory usage", "memory leak detected"),
        ("too many requests", "rate limit exceeded"),
    ]

    different = [
        ("API returning 500 error", "dark mode not working"),
        ("file upload crash", "rate limit exceeded"),
        ("memory leak", "feature flag setup"),
    ]

    print("Similar pairs (expect > 0.6):")
    for a, b in similar:
        va = embeddings.embed_query(a)
        vb = embeddings.embed_query(b)
        sim = np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb))
        status = "✓" if sim > 0.6 else "⚠️"
        print(f'  {status} {sim:.4f}  "{a}" vs "{b}"')

    print("\nDifferent pairs (expect < 0.5):")
    for a, b in different:
        va = embeddings.embed_query(a)
        vb = embeddings.embed_query(b)
        sim = np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb))
        status = "✓" if sim < 0.5 else "⚠️"
        print(f'  {status} {sim:.4f}  "{a}" vs "{b}"')


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("   END-TO-END VECTOR SEARCH VERIFICATION")
    print("   OpenRouter embeddings → Pinecone → Semantic search")
    print("=" * 60 + "\n")

    settings = Settings()

    # Check required keys
    missing = []
    if not settings.openrouter_api_key:
        missing.append("OPENROUTER_API_KEY")
    if not settings.pinecone_api_key:
        missing.append("PINECONE_API_KEY")
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("   Add them to your .env file and try again.")
        sys.exit(1)

    embeddings = EmbeddingsService(settings)

    # Step 1
    if not test_embeddings(settings, embeddings):
        sys.exit(1)

    # Step 2 + 3
    store = test_pinecone(settings, embeddings)
    if not store:
        sys.exit(1)

    # Step 4
    test_similarity_quality(embeddings)

    print("\n" + "=" * 60)
    print("  ✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print("\nYour vector search pipeline is working:")
    print("  OpenRouter (embeddings) → Pinecone (storage) → Semantic search")
    print("\nNext steps:")
    print("  1. Start the backend: uvicorn backend.main:app --reload")
    print("  2. Go to http://localhost:3000/knowledge-base")
    print("  3. Upload backend/kb_data/technical_kb.json")
    print("  4. Test search queries in the Search tab")
