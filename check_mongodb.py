#!/usr/bin/env python3
"""Check MongoDB connection status"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Load environment variables
load_dotenv()

def check_mongodb():
    """Check if MongoDB is accessible"""
    
    use_mongodb = os.getenv("USE_MONGODB", "false").lower() == "true"
    
    if not use_mongodb:
        print("❌ MongoDB is disabled in .env (USE_MONGODB=false)")
        print("   Using SQLite instead")
        return False
    
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "support_agent")
    
    print(f"🔍 Checking MongoDB connection...")
    print(f"   URI: {mongodb_uri}")
    print(f"   Database: {db_name}")
    print()
    
    try:
        # Create client with short timeout
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        
        # Get database info
        db = client[db_name]
        collections = db.list_collection_names()
        
        print("✅ MongoDB is RUNNING and accessible!")
        print(f"   Collections: {collections if collections else 'None (empty database)'}")
        
        # Get document counts
        if collections:
            print("\n📊 Collection Statistics:")
            for collection in collections:
                count = db[collection].count_documents({})
                print(f"   - {collection}: {count} documents")
        
        client.close()
        return True
        
    except ConnectionFailure:
        print("❌ MongoDB connection FAILED")
        print("   Error: Cannot connect to MongoDB server")
        print("\n💡 Solutions:")
        print("   1. Start MongoDB locally: brew services start mongodb-community")
        print("   2. Use MongoDB Atlas (cloud): Update MONGODB_URI in .env")
        print("   3. Disable MongoDB: Set USE_MONGODB=false in .env")
        return False
        
    except ServerSelectionTimeoutError:
        print("❌ MongoDB connection TIMEOUT")
        print("   Error: Server not responding")
        print("\n💡 Solutions:")
        print("   1. Check if MongoDB is running: brew services list")
        print("   2. Verify MONGODB_URI in .env is correct")
        print("   3. Check network/firewall settings")
        return False
        
    except Exception as e:
        print(f"❌ MongoDB connection ERROR: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("MongoDB Connection Check")
    print("=" * 60)
    print()
    
    is_connected = check_mongodb()
    
    print()
    print("=" * 60)
    
    if is_connected:
        print("✅ MongoDB is ready to use!")
    else:
        print("⚠️  MongoDB is not available. Using SQLite fallback.")
    
    print("=" * 60)
