from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient, ASCENDING, DESCENDING
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
from pathlib import Path

class MongoDBManager:
    _instance = None
    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None
    _sync_client: Optional[MongoClient] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            self.db_name = os.getenv("MONGODB_DB_NAME", "support_agent")
            self.use_mongodb = os.getenv("USE_MONGODB", "false").lower() == "true"
    
    async def connect(self):
        if self._client is None and self.use_mongodb:
            self._client = AsyncIOMotorClient(self.mongodb_uri)
            self._db = self._client[self.db_name]
            await self._create_indexes()
            print(f"Connected to MongoDB: {self.db_name}")
    
    def connect_sync(self):
        if self._sync_client is None and self.use_mongodb:
            self._sync_client = MongoClient(self.mongodb_uri)
            return self._sync_client[self.db_name]
        return None
    
    async def _create_indexes(self):
        if self._db is None:
            return
        
        # Tickets collection indexes
        await self._db.tickets.create_index([("ticket_id", ASCENDING)], unique=True)
        await self._db.tickets.create_index([("status", ASCENDING)])
        await self._db.tickets.create_index([("category", ASCENDING)])
        await self._db.tickets.create_index([("severity", ASCENDING)])
        await self._db.tickets.create_index([("priority", ASCENDING)])
        await self._db.tickets.create_index([("created_at", DESCENDING)])
        await self._db.tickets.create_index([("customer.email", ASCENDING)])
        await self._db.tickets.create_index([("product", ASCENDING)])
        await self._db.tickets.create_index([("assignee", ASCENDING)])
        await self._db.tickets.create_index([("tags", ASCENDING)])
        
        # Knowledge base indexes
        await self._db.knowledge_base.create_index([("article_id", ASCENDING)], unique=True)
        await self._db.knowledge_base.create_index([("category", ASCENDING)])
        await self._db.knowledge_base.create_index([("is_active", ASCENDING)])
        await self._db.knowledge_base.create_index([("product", ASCENDING)])
        await self._db.knowledge_base.create_index([("tags", ASCENDING)])
        await self._db.knowledge_base.create_index([("created_at", DESCENDING)])
        
        # Retrieval logs indexes
        await self._db.retrieval_logs.create_index([("ticket_id", ASCENDING)])
        await self._db.retrieval_logs.create_index([("created_at", DESCENDING)])
        
        # Solution feedback indexes
        await self._db.solution_feedback.create_index([("ticket_id", ASCENDING)])
        await self._db.solution_feedback.create_index([("created_at", DESCENDING)])
        
        # Routing logs indexes
        await self._db.routing_logs.create_index([("ticket_id", ASCENDING)])
        await self._db.routing_logs.create_index([("created_at", DESCENDING)])
        
        # Conversations indexes
        await self._db.conversations.create_index([("ticket_id", ASCENDING)])
        await self._db.conversations.create_index([("created_at", ASCENDING)])

        # AI chat indexes (agent-AI contextual chat per ticket)
        await self._db.ai_chat.create_index([("ticket_id", ASCENDING)])
        await self._db.ai_chat.create_index([("created_at", ASCENDING)])

        # Ticket solutions — heavy AI output stored separately from ticket doc
        await self._db.ticket_solutions.create_index(
            [("ticket_id", ASCENDING)], unique=True
        )
        await self._db.ticket_solutions.create_index([("created_at", DESCENDING)])

        # Users collection indexes
        await self._db.users.create_index([("user_id", ASCENDING)], unique=True)
        await self._db.users.create_index([("email", ASCENDING)], unique=True)
        await self._db.users.create_index([("role", ASCENDING)])
        await self._db.users.create_index([("team", ASCENDING)])

        print("MongoDB indexes created successfully")
    
    async def close(self):
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
    
    def get_database(self) -> Optional[AsyncIOMotorDatabase]:
        return self._db
    
    def is_connected(self) -> bool:
        return self._db is not None

# Global instance
mongodb_manager = MongoDBManager()
