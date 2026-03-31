from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.db.mongodb import mongodb_manager


class UserRepository:
    @staticmethod
    def _generate_user_id() -> str:
        return f"USR-{uuid.uuid4().hex[:12]}"

    @staticmethod
    async def create(
        email: str,
        password_hash: str,
        name: str,
        role: str = "customer",
        team: Optional[str] = None,
    ) -> str:
        db = mongodb_manager.get_database()
        if db is None:
            raise RuntimeError("Database not available")

        user_id = UserRepository._generate_user_id()
        now = datetime.utcnow()
        doc = {
            "user_id": user_id,
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "name": name.strip(),
            "role": role,
            "team": team,
            "created_at": now,
            "updated_at": now,
        }
        await db.users.insert_one(doc)
        return user_id

    @staticmethod
    async def find_by_email(email: str) -> Optional[Dict[str, Any]]:
        db = mongodb_manager.get_database()
        if db is None:
            return None
        user = await db.users.find_one({"email": email.lower().strip()})
        if user:
            user["_id"] = str(user["_id"])
        return user

    @staticmethod
    async def find_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        db = mongodb_manager.get_database()
        if db is None:
            return None
        user = await db.users.find_one({"user_id": user_id})
        if user:
            user["_id"] = str(user["_id"])
        return user

    @staticmethod
    async def find_all(role: Optional[str] = None, team: Optional[str] = None) -> List[Dict[str, Any]]:
        db = mongodb_manager.get_database()
        if db is None:
            return []
        query: Dict[str, Any] = {}
        if role:
            query["role"] = role
        if team:
            query["team"] = team
        cursor = db.users.find(query).sort("created_at", -1)
        users = await cursor.to_list(length=200)
        for u in users:
            u["_id"] = str(u["_id"])
            u.pop("password_hash", None)
        return users

    @staticmethod
    async def update(user_id: str, updates: Dict[str, Any]) -> bool:
        db = mongodb_manager.get_database()
        if db is None:
            return False
        updates["updated_at"] = datetime.utcnow()
        result = await db.users.update_one(
            {"user_id": user_id},
            {"$set": updates},
        )
        return result.modified_count > 0

    @staticmethod
    async def delete(user_id: str) -> bool:
        db = mongodb_manager.get_database()
        if db is None:
            return False
        result = await db.users.delete_one({"user_id": user_id})
        return result.deleted_count > 0
