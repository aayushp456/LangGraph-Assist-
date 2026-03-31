#!/usr/bin/env python3
"""
Fix Pinecone Dimension Mismatch
Deletes the existing index and recreates it with the correct dimension (1536)
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.config import Settings
from dotenv import load_dotenv
from pinecone import Pinecone
import time

# Load environment variables
load_dotenv()

def fix_dimension():
    """Delete and recreate Pinecone index with correct dimension"""
    
    settings = Settings()
    
    print("🔧 Fixing Pinecone Dimension Mismatch\n")
    print(f"Current index: {settings.pinecone_index_name}")
    print(f"Expected dimension: {settings.embedding_dim}")
    
    # Initialize Pinecone
    pc = Pinecone(api_key=settings.pinecone_api_key)
    
    # Check if index exists
    existing_indexes = pc.list_indexes().names()
    
    if settings.pinecone_index_name in existing_indexes:
        print(f"\n⚠️  Index '{settings.pinecone_index_name}' exists with wrong dimension (1024)")
        
        # Get user confirmation
        response = input("\nDelete and recreate index? This will delete all existing vectors. (yes/no): ")
        
        if response.lower() != 'yes':
            print("❌ Aborted. No changes made.")
            return False
        
        print(f"\n🗑️  Deleting index '{settings.pinecone_index_name}'...")
        pc.delete_index(settings.pinecone_index_name)
        print("✓ Index deleted")
        
        # Wait for deletion to complete
        print("Waiting for deletion to complete...")
        time.sleep(5)
    
    # Create new index with correct dimension
    print(f"\n🔨 Creating index '{settings.pinecone_index_name}' with dimension {settings.embedding_dim}...")
    
    from pinecone import ServerlessSpec
    
    pc.create_index(
        name=settings.pinecone_index_name,
        dimension=settings.embedding_dim,
        metric='cosine',
        spec=ServerlessSpec(
            cloud=settings.pinecone_cloud,
            region=settings.pinecone_region
        )
    )
    
    # Wait for index to be ready
    print("Waiting for index to be ready...")
    while not pc.describe_index(settings.pinecone_index_name).status['ready']:
        time.sleep(1)
    
    print(f"✓ Index '{settings.pinecone_index_name}' created with dimension {settings.embedding_dim}")
    
    # Verify
    index_info = pc.describe_index(settings.pinecone_index_name)
    print(f"\n✅ Verification:")
    print(f"  - Index name: {settings.pinecone_index_name}")
    print(f"  - Dimension: {index_info.dimension}")
    print(f"  - Status: {index_info.status['ready']}")
    
    print("\n🎉 Dimension fixed! You can now restart your backend.")
    return True


if __name__ == "__main__":
    try:
        success = fix_dimension()
        if success:
            print("\nNext steps:")
            print("1. Restart backend: ./start_backend.sh")
            print("2. Upload your knowledge base")
            print("3. Test: curl http://localhost:8000/api/kb/stats")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
