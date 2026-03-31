#!/usr/bin/env python3
"""
Verify Pinecone Setup
Checks if Pinecone is properly configured and working
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.config import Settings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def verify_pinecone_config():
    """Verify Pinecone configuration"""
    print("🔍 Verifying Pinecone Configuration...\n")
    
    settings = Settings()
    
    # Check USE_PINECONE flag
    print(f"1. USE_PINECONE: {settings.use_pinecone}")
    if not settings.use_pinecone:
        print("   ❌ Pinecone is disabled. Set USE_PINECONE=true in .env")
        return False
    else:
        print("   ✓ Pinecone is enabled")
    
    # Check API key
    print(f"\n2. PINECONE_API_KEY: {'*' * 20 if settings.pinecone_api_key else 'NOT SET'}")
    if not settings.pinecone_api_key or settings.pinecone_api_key == "your_pinecone_api_key_here":
        print("   ❌ Pinecone API key not set. Get one from https://www.pinecone.io/")
        print("   Add to .env: PINECONE_API_KEY=your-actual-api-key")
        return False
    else:
        print("   ✓ API key is set")
    
    # Check index name
    print(f"\n3. PINECONE_INDEX_NAME: {settings.pinecone_index_name}")
    print("   ✓ Index name configured")
    
    # Check cloud and region
    print(f"\n4. PINECONE_CLOUD: {settings.pinecone_cloud}")
    print(f"5. PINECONE_REGION: {settings.pinecone_region}")
    print("   ✓ Cloud settings configured")
    
    # Check embedding dimension
    print(f"\n6. EMBEDDING_DIM: {settings.embedding_dim}")
    print("   ✓ Embedding dimension set")
    
    print("\n" + "="*50)
    print("✅ Configuration looks good!")
    print("="*50)
    
    return True


def test_pinecone_connection():
    """Test actual Pinecone connection"""
    print("\n🔌 Testing Pinecone Connection...\n")
    
    try:
        from backend.services.embeddings import EmbeddingsService
        from backend.services.pinecone_store import PineconeVectorStore
        
        settings = Settings()
        
        print("Initializing embeddings service...")
        embeddings = EmbeddingsService(settings)
        print("✓ Embeddings service initialized")
        
        print("\nConnecting to Pinecone...")
        store = PineconeVectorStore(
            embeddings_service=embeddings,
            api_key=settings.pinecone_api_key,
            index_name=settings.pinecone_index_name,
            dimension=settings.embedding_dim,
            cloud=settings.pinecone_cloud,
            region=settings.pinecone_region
        )
        print("✓ Connected to Pinecone!")
        
        # Get stats
        print("\nFetching index stats...")
        stats = store.get_stats()
        print(f"✓ Index stats:")
        print(f"  - Total vectors: {stats['total_vectors']}")
        print(f"  - Dimension: {stats['dimension']}")
        print(f"  - Index fullness: {stats['index_fullness']:.2%}")
        
        # Test upload
        print("\nTesting document upload...")
        test_docs = [
            "This is a test document for Pinecone verification",
            "Another test document to ensure uploads work"
        ]
        test_metadata = [
            {"test": True, "category": "verification"},
            {"test": True, "category": "verification"}
        ]
        
        ids = store.add_documents(test_docs, test_metadata)
        print(f"✓ Uploaded {len(ids)} test documents")
        
        # Test search
        print("\nTesting search...")
        results = store.search("test document", top_k=2)
        print(f"✓ Search returned {len(results)} results")
        if results:
            print(f"  - Top result score: {results[0]['score']:.4f}")
        
        # Clean up test documents
        print("\nCleaning up test documents...")
        store.delete(ids)
        print("✓ Test documents deleted")
        
        print("\n" + "="*50)
        print("🎉 Pinecone is fully functional!")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check your Pinecone API key is correct")
        print("2. Verify you have internet connection")
        print("3. Check Pinecone dashboard: https://app.pinecone.io/")
        print("4. Make sure you have the pinecone-client package: pip install pinecone-client")
        return False


if __name__ == "__main__":
    print("="*50)
    print("   PINECONE SETUP VERIFICATION")
    print("="*50 + "\n")
    
    # Step 1: Verify configuration
    config_ok = verify_pinecone_config()
    
    if not config_ok:
        print("\n❌ Configuration issues found. Please fix them and try again.")
        sys.exit(1)
    
    # Step 2: Test connection
    connection_ok = test_pinecone_connection()
    
    if not connection_ok:
        print("\n❌ Connection test failed. Please check the errors above.")
        sys.exit(1)
    
    print("\n✅ All checks passed! Pinecone is ready to use.")
    print("\nNext steps:")
    print("1. Restart your backend: ./start_backend.sh")
    print("2. You should see: '✓ Pinecone vector store initialized'")
    print("3. Upload your knowledge base")
    print("4. Test with: curl http://localhost:8000/api/kb/stats")
