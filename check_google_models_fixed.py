#!/usr/bin/env python3
"""
Check available Google models with correct API
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

def check_models():
    """Check available Google models"""
    print("🔍 Checking Available Google Models...\n")
    
    api_key = None
    try:
        from backend.config import Settings
        settings = Settings()
        api_key = settings.google_ai_api_key
    except:
        import os
        api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ GOOGLE_API_KEY not found")
        return
    
    print(f"✓ API Key found: {api_key[:20]}...")
    
    try:
        genai.configure(api_key=api_key)
        
        # List all models
        models = list(genai.list_models())
        
        print(f"\n✓ Found {len(models)} models:")
        
        embedding_models = []
        for model in models:
            if "embed" in model.name.lower() or "embedding" in model.name.lower():
                embedding_models.append(model)
                print(f"  📝 {model.name} - {model.display_name}")
                print(f"     Supported methods: {model.supported_generation_methods}")
        
        if not embedding_models:
            print("\n❌ No embedding models found!")
            print("\nAvailable models:")
            for model in models[:10]:  # Show first 10
                print(f"  • {model.name} - {model.display_name}")
        else:
            print(f"\n✓ Found {len(embedding_models)} embedding models")
            
            # Try the first embedding model
            first_model = embedding_models[0]
            print(f"\n🔍 Trying model: {first_model.name}")
            
            try:
                # For embeddings, we need to use the embed_content method directly
                result = genai.embed_content(
                    model=first_model.name,
                    content="Test embedding",
                    task_type="retrieval_document"
                )
                print(f"✓ Embedding works! Dimensions: {len(result['embedding'])}")
                print(f"✓ Recommended model name: {first_model.name}")
                
            except Exception as e:
                print(f"❌ Error testing model: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_models()
