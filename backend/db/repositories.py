from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.db.mongodb import mongodb_manager
import uuid


# ---------------------------------------------------------------------------
# Ticket Repository — new flat metadata schema
# ---------------------------------------------------------------------------
class TicketRepository:

    @staticmethod
    def _generate_ticket_id() -> str:
        """Generate a human-readable ticket ID like TKT-20240321-abcd."""
        now = datetime.utcnow()
        short = uuid.uuid4().hex[:6]
        return f"TKT-{now.strftime('%Y%m%d')}-{short}"

    @staticmethod
    async def create(ticket_data: Dict[str, Any]) -> str:
        db = mongodb_manager.get_database()
        if db is None:
            raise Exception("MongoDB not connected")

        now = datetime.utcnow()
        if "ticket_id" not in ticket_data:
            ticket_data["ticket_id"] = TicketRepository._generate_ticket_id()
        ticket_data.setdefault("status", "new")
        ticket_data.setdefault("priority", "medium")
        ticket_data.setdefault("severity", "SEV3")
        ticket_data.setdefault("category", None)
        ticket_data.setdefault("channel", "web")
        ticket_data.setdefault("customer", {})
        ticket_data.setdefault("environment", None)
        ticket_data.setdefault("product", None)
        ticket_data.setdefault("version", None)
        ticket_data.setdefault("tags", [])
        ticket_data.setdefault("assignee", None)
        ticket_data.setdefault("ai_analysis", {})
        ticket_data["created_at"] = now
        ticket_data["updated_at"] = now
        ticket_data.setdefault("resolved_at", None)
        ticket_data.setdefault("first_response_at", None)

        result = await db.tickets.insert_one(ticket_data)
        return ticket_data["ticket_id"]

    @staticmethod
    async def bulk_insert(tickets: List[Dict[str, Any]]) -> int:
        db = mongodb_manager.get_database()
        if db is None:
            raise Exception("MongoDB not connected")

        now = datetime.utcnow()
        for t in tickets:
            if "ticket_id" not in t:
                t["ticket_id"] = TicketRepository._generate_ticket_id()
            t.setdefault("created_at", now)
            t.setdefault("updated_at", now)

        result = await db.tickets.insert_many(tickets)
        return len(result.inserted_ids)

    @staticmethod
    async def find_by_id(ticket_id: str) -> Optional[Dict[str, Any]]:
        db = mongodb_manager.get_database()
        if db is None:
            return None
        ticket = await db.tickets.find_one({"ticket_id": ticket_id})
        if ticket:
            ticket["_id"] = str(ticket["_id"])
        return ticket

    @staticmethod
    async def find_all(
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        team: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        db = mongodb_manager.get_database()
        if db is None:
            return []

        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        if category:
            if category.upper() == "UNPROCESSED":
                query["$or"] = [
                    {"category": None},
                    {"category": {"$exists": False}},
                    {"category": "UNPROCESSED"},
                ]
            else:
                query["category"] = category
        if priority:
            query["priority"] = priority
        if team:
            query["$or"] = [
                {"assigned_team": team},
                {"assigned_team": None},
                {"assigned_team": {"$exists": False}},
            ]

        cursor = db.tickets.find(query).sort("created_at", -1).skip(skip).limit(limit)
        tickets = await cursor.to_list(length=limit)
        for t in tickets:
            t["_id"] = str(t["_id"])
        return tickets

    @staticmethod
    async def update_status(ticket_id: str, status: str) -> bool:
        db = mongodb_manager.get_database()
        if db is None:
            return False

        update: Dict[str, Any] = {
            "$set": {
                "status": status,
                "updated_at": datetime.utcnow(),
            }
        }
        if status in ("resolved", "closed"):
            update["$set"]["resolved_at"] = datetime.utcnow()

        result = await db.tickets.update_one({"ticket_id": ticket_id}, update)
        return result.modified_count > 0

    @staticmethod
    async def update_assignment(ticket_id: str, assigned_team: str) -> bool:
        db = mongodb_manager.get_database()
        if db is None:
            return False
        result = await db.tickets.update_one(
            {"ticket_id": ticket_id},
            {"$set": {"assigned_team": assigned_team, "updated_at": datetime.utcnow()}},
        )
        return result.modified_count > 0

    @staticmethod
    async def update_routing(
        ticket_id: str,
        category: str,
        confidence: float,
        reason: str = "",
        severity: str = "SEV3",
    ) -> bool:
        db = mongodb_manager.get_database()
        if db is None:
            return False

        result = await db.tickets.update_one(
            {"ticket_id": ticket_id},
            {
                "$set": {
                    "category": category,
                    "severity": severity,
                    "ai_analysis.routing": {
                        "category": category,
                        "confidence": confidence,
                        "reason": reason,
                        "severity": severity,
                        "routed_at": datetime.utcnow(),
                    },
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return result.modified_count > 0

    @staticmethod
    async def update_ai_analysis(
        ticket_id: str,
        sentiment: str,
        sentiment_score: float,
        summary: str,
    ) -> bool:
        """Persist lightweight AI fields only. Heavy solution data goes to TicketSolutionsRepository."""
        db = mongodb_manager.get_database()
        if db is None:
            return False

        result = await db.tickets.update_one(
            {"ticket_id": ticket_id},
            {
                "$set": {
                    "ai_analysis.sentiment": sentiment,
                    "ai_analysis.sentiment_score": sentiment_score,
                    "ai_analysis.summary": summary,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return result.modified_count > 0

    @staticmethod
    async def get_triage_stats(team: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return per-category ticket counts with status breakdowns."""
        db = mongodb_manager.get_database()
        if db is None:
            return []

        pipeline = []
        if team:
            pipeline.append({"$match": {"$or": [
                {"assigned_team": team},
                {"assigned_team": None},
                {"assigned_team": {"$exists": False}},
            ]}})
        pipeline += [
            {
                "$group": {
                    "_id": "$category",
                    "count": {"$sum": 1},
                    "new": {
                        "$sum": {"$cond": [{"$eq": ["$status", "new"]}, 1, 0]}
                    },
                    "in_progress": {
                        "$sum": {"$cond": [{"$eq": ["$status", "in_progress"]}, 1, 0]}
                    },
                    "resolved": {
                        "$sum": {"$cond": [{"$eq": ["$status", "resolved"]}, 1, 0]}
                    },
                    "escalated": {
                        "$sum": {"$cond": [{"$eq": ["$status", "escalated"]}, 1, 0]}
                    },
                    "waiting_on_customer": {
                        "$sum": {"$cond": [{"$eq": ["$status", "waiting_on_customer"]}, 1, 0]}
                    },
                    "forwarded": {
                        "$sum": {"$cond": [{"$eq": ["$status", "forwarded"]}, 1, 0]}
                    },
                    "negative_sentiment": {
                        "$sum": {
                            "$cond": [
                                {"$in": [
                                    "$ai_analysis.sentiment",
                                    ["negative", "very_negative"],
                                ]},
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "category": {"$ifNull": ["$_id", "UNPROCESSED"]},
                    "count": 1,
                    "new": 1,
                    "in_progress": 1,
                    "resolved": 1,
                    "escalated": 1,
                    "waiting_on_customer": 1,
                    "forwarded": 1,
                    "negative_sentiment": 1,
                    "_id": 0,
                }
            },
            {"$sort": {"count": -1}},
        ]

        cursor = db.tickets.aggregate(pipeline)
        return await cursor.to_list(length=None)

    @staticmethod
    async def get_priority_queue(limit: int = 20, team: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return tickets sorted by urgency heuristic."""
        db = mongodb_manager.get_database()
        if db is None:
            return []

        # Fetch unresolved tickets
        query: Dict[str, Any] = {"status": {"$nin": ["resolved", "closed"]}}
        if team:
            query["$or"] = [
                {"assigned_team": team},
                {"assigned_team": None},
                {"assigned_team": {"$exists": False}},
            ]
        cursor = db.tickets.find(query).sort("created_at", -1).limit(200)
        tickets = await cursor.to_list(length=200)

        scored = []
        for t in tickets:
            t["_id"] = str(t["_id"])
            score = 0
            reasons = []
            if t.get("status") == "escalated":
                score += 100
                reasons.append("Escalated")
            if t.get("severity") == "SEV1":
                score += 90
                reasons.append("SEV1 Critical")
            elif t.get("severity") == "SEV2":
                score += 60
                reasons.append("SEV2 Major")
            if t.get("priority") in ("high", "critical"):
                score += 40
                reasons.append("High priority")
            sentiment = (t.get("ai_analysis") or {}).get("sentiment", "")
            if sentiment in ("negative", "very_negative"):
                score += 50
                reasons.append("Negative sentiment")
            routing_conf = (t.get("ai_analysis", {}).get("routing") or {}).get("confidence", 1.0)
            if routing_conf < 0.5:
                score += 30
                reasons.append("Low confidence")
            if t.get("status") == "new":
                score += 20
                reasons.append("Unassigned")

            if score > 0:
                t["priority_score"] = score
                t["priority_reasons"] = reasons
                scored.append(t)

        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored[:limit]

    @staticmethod
    async def count(query: Optional[Dict[str, Any]] = None) -> int:
        db = mongodb_manager.get_database()
        if db is None:
            return 0
        return await db.tickets.count_documents(query or {})

    @staticmethod
    async def delete(ticket_id: str) -> bool:
        db = mongodb_manager.get_database()
        if db is None:
            return False
        result = await db.tickets.delete_one({"ticket_id": ticket_id})
        return result.deleted_count > 0


# ---------------------------------------------------------------------------
# Ticket Solutions Repository — heavy AI output stored separately
# ---------------------------------------------------------------------------
class TicketSolutionsRepository:

    @staticmethod
    async def upsert(
        ticket_id: str,
        suggested_solution: Dict[str, Any],
        decision: Dict[str, Any],
        matched_kb_articles: List[str],
        similar_tickets: List[str],
    ) -> bool:
        """Insert or replace the solution document for a ticket."""
        db = mongodb_manager.get_database()
        if db is None:
            return False

        now = datetime.utcnow()
        result = await db.ticket_solutions.update_one(
            {"ticket_id": ticket_id},
            {
                "$set": {
                    "ticket_id": ticket_id,
                    "suggested_solution": suggested_solution,
                    "decision": decision,
                    "matched_kb_articles": matched_kb_articles,
                    "similar_tickets": similar_tickets,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return result.acknowledged

    @staticmethod
    async def find_by_ticket_id(ticket_id: str) -> Optional[Dict[str, Any]]:
        db = mongodb_manager.get_database()
        if db is None:
            return None
        doc = await db.ticket_solutions.find_one({"ticket_id": ticket_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc


# ---------------------------------------------------------------------------
# Knowledge Base Repository — new flat metadata schema
# ---------------------------------------------------------------------------
class KnowledgeBaseRepository:

    @staticmethod
    def _generate_article_id() -> str:
        return f"KB-{uuid.uuid4().hex[:8]}"

    @staticmethod
    async def create(article_data: Dict[str, Any]) -> str:
        db = mongodb_manager.get_database()
        if db is None:
            raise Exception("MongoDB not connected")

        now = datetime.utcnow()
        if "article_id" not in article_data:
            article_data["article_id"] = KnowledgeBaseRepository._generate_article_id()
        article_data.setdefault("category", "GENERAL_INQUIRY")
        article_data.setdefault("tags", [])
        article_data.setdefault("product", None)
        article_data.setdefault("version", None)
        article_data.setdefault("severity", None)
        article_data.setdefault("author", "system")
        article_data.setdefault("is_active", True)
        article_data.setdefault("usage_stats", {
            "retrieval_count": 0,
            "helpful_count": 0,
            "not_helpful_count": 0,
            "last_used": None,
        })
        article_data["created_at"] = now
        article_data["updated_at"] = now

        await db.knowledge_base.insert_one(article_data)
        return article_data["article_id"]

    @staticmethod
    async def bulk_insert(articles: List[Dict[str, Any]]) -> int:
        db = mongodb_manager.get_database()
        if db is None:
            raise Exception("MongoDB not connected")

        now = datetime.utcnow()
        for a in articles:
            if "article_id" not in a:
                a["article_id"] = KnowledgeBaseRepository._generate_article_id()
            a.setdefault("is_active", True)
            a.setdefault("created_at", now)
            a.setdefault("updated_at", now)

        result = await db.knowledge_base.insert_many(articles, ordered=False)
        return len(result.inserted_ids)

    @staticmethod
    async def find_by_id(article_id: str) -> Optional[Dict[str, Any]]:
        db = mongodb_manager.get_database()
        if db is None:
            return None
        article = await db.knowledge_base.find_one({"article_id": article_id})
        if article:
            article["_id"] = str(article["_id"])
        return article

    @staticmethod
    async def find_active(
        category: Optional[str] = None,
        product: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        db = mongodb_manager.get_database()
        if db is None:
            return []

        query: Dict[str, Any] = {"is_active": True}
        if category:
            query["category"] = category
        if product:
            query["product"] = product

        cursor = db.knowledge_base.find(query).sort("created_at", -1).limit(limit)
        articles = await cursor.to_list(length=limit)
        for a in articles:
            a["_id"] = str(a["_id"])
        return articles

    @staticmethod
    async def find_all(
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        db = mongodb_manager.get_database()
        if db is None:
            return []

        query: Dict[str, Any] = {}
        if category:
            query["category"] = category

        cursor = (
            db.knowledge_base.find(query)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        articles = await cursor.to_list(length=limit)
        for a in articles:
            a["_id"] = str(a["_id"])
        return articles

    @staticmethod
    async def count(query: Optional[Dict[str, Any]] = None) -> int:
        db = mongodb_manager.get_database()
        if db is None:
            return 0
        return await db.knowledge_base.count_documents(query or {})

    @staticmethod
    async def update_usage_stats(article_id: str, helpful: bool) -> bool:
        db = mongodb_manager.get_database()
        if db is None:
            return False

        update_field = "usage_stats.helpful_count" if helpful else "usage_stats.not_helpful_count"
        result = await db.knowledge_base.update_one(
            {"article_id": article_id},
            {
                "$inc": {
                    "usage_stats.retrieval_count": 1,
                    update_field: 1,
                },
                "$set": {"usage_stats.last_used": datetime.utcnow()},
            },
        )
        return result.modified_count > 0

    @staticmethod
    async def clear_all() -> int:
        db = mongodb_manager.get_database()
        if db is None:
            return 0
        result = await db.knowledge_base.delete_many({})
        return result.deleted_count

    @staticmethod
    async def get_stats() -> Dict[str, Any]:
        db = mongodb_manager.get_database()
        if db is None:
            return {"total": 0, "categories": {}}

        total = await db.knowledge_base.count_documents({})
        pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        cursor = db.knowledge_base.aggregate(pipeline)
        cat_results = await cursor.to_list(length=None)
        categories = {r["_id"] or "UNKNOWN": r["count"] for r in cat_results}

        return {"total": total, "categories": categories}


# ---------------------------------------------------------------------------
# Retrieval Log Repository
# ---------------------------------------------------------------------------
class RetrievalLogRepository:
    @staticmethod
    async def create(log_data: Dict[str, Any]) -> str:
        db = mongodb_manager.get_database()
        if db is None:
            raise Exception("MongoDB not connected")
        log_data["created_at"] = datetime.utcnow()
        result = await db.retrieval_logs.insert_one(log_data)
        return str(result.inserted_id)

    @staticmethod
    async def get_stats(days: int = 7) -> Dict[str, Any]:
        db = mongodb_manager.get_database()
        if db is None:
            return {}
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff}}},
            {
                "$group": {
                    "_id": None,
                    "total_retrievals": {"$sum": 1},
                    "avg_docs_retrieved": {"$avg": {"$size": "$retrieved_chunks"}},
                    "helpful": {"$sum": {"$cond": [{"$eq": ["$feedback", "helpful"]}, 1, 0]}},
                }
            },
        ]
        cursor = db.retrieval_logs.aggregate(pipeline)
        results = await cursor.to_list(length=1)
        return results[0] if results else {}


# ---------------------------------------------------------------------------
# Solution Feedback Repository
# ---------------------------------------------------------------------------
class SolutionFeedbackRepository:
    @staticmethod
    async def create(feedback_data: Dict[str, Any]) -> str:
        db = mongodb_manager.get_database()
        if db is None:
            raise Exception("MongoDB not connected")
        feedback_data["created_at"] = datetime.utcnow()
        result = await db.solution_feedback.insert_one(feedback_data)
        return str(result.inserted_id)

    @staticmethod
    async def get_stats(days: int = 7) -> Dict[str, Any]:
        db = mongodb_manager.get_database()
        if db is None:
            return {}
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff}}},
            {"$group": {"_id": "$feedback_type", "count": {"$sum": 1}}},
        ]
        cursor = db.solution_feedback.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        stats = {"thumbs_up": 0, "thumbs_down": 0}
        for r in results:
            if r["_id"] == "thumbs_up":
                stats["thumbs_up"] = r["count"]
            elif r["_id"] == "thumbs_down":
                stats["thumbs_down"] = r["count"]
        total = stats["thumbs_up"] + stats["thumbs_down"]
        stats["acceptance_rate"] = (stats["thumbs_up"] / total * 100) if total > 0 else 0
        return stats


# ---------------------------------------------------------------------------
# Routing Log Repository
# ---------------------------------------------------------------------------
class RoutingLogRepository:
    @staticmethod
    async def create(log_data: Dict[str, Any]) -> str:
        db = mongodb_manager.get_database()
        if db is None:
            raise Exception("MongoDB not connected")
        log_data["created_at"] = datetime.utcnow()
        result = await db.routing_logs.insert_one(log_data)
        return str(result.inserted_id)

    @staticmethod
    async def get_accuracy(days: int = 7) -> Dict[str, Any]:
        db = mongodb_manager.get_database()
        if db is None:
            return {}
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff}}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "correct": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$predicted_category", "$actual_category"]},
                                1, 0,
                            ]
                        }
                    },
                }
            },
        ]
        cursor = db.routing_logs.aggregate(pipeline)
        results = await cursor.to_list(length=1)
        if results:
            r = results[0]
            accuracy = (r["correct"] / r["total"] * 100) if r["total"] > 0 else 0
            return {"total": r["total"], "correct": r["correct"], "accuracy": accuracy}
        return {"total": 0, "correct": 0, "accuracy": 0}


# ---------------------------------------------------------------------------
# Conversation Repository — per-ticket message history
# ---------------------------------------------------------------------------
class ConversationRepository:

    @staticmethod
    def _generate_message_id() -> str:
        return f"MSG-{uuid.uuid4().hex[:10]}"

    @staticmethod
    async def add_message(
        ticket_id: str,
        sender: str,
        body: str,
        msg_type: str = "reply",
        email_status: str = "simulated",
    ) -> Dict[str, Any]:
        """Add a message to a ticket's conversation history."""
        db = mongodb_manager.get_database()
        if db is None:
            raise Exception("MongoDB not connected")

        now = datetime.utcnow()
        message = {
            "message_id": ConversationRepository._generate_message_id(),
            "ticket_id": ticket_id,
            "sender": sender,
            "body": body,
            "msg_type": msg_type,
            "email_status": email_status,
            "created_at": now,
        }
        await db.conversations.insert_one(message)
        # Convert for JSON serialization (WS broadcast + API response)
        message["_id"] = str(message["_id"])
        message["created_at"] = now.isoformat()
        return message

    @staticmethod
    async def get_history(ticket_id: str) -> List[Dict[str, Any]]:
        """Return all messages for a ticket sorted oldest-first."""
        db = mongodb_manager.get_database()
        if db is None:
            return []

        cursor = db.conversations.find({"ticket_id": ticket_id}).sort("created_at", 1)
        messages = await cursor.to_list(length=500)
        for m in messages:
            m["_id"] = str(m["_id"])
            if isinstance(m.get("created_at"), datetime):
                m["created_at"] = m["created_at"].isoformat()
        return messages


# ---------------------------------------------------------------------------
# AI Chat Repository — agent-AI contextual chat per ticket
# ---------------------------------------------------------------------------
class AIChatRepository:

    @staticmethod
    async def add_message(ticket_id: str, role: str, content: str) -> bool:
        """Insert a chat message (role = 'user' | 'assistant')."""
        db = mongodb_manager.get_database()
        if db is None:
            return False

        doc = {
            "ticket_id": ticket_id,
            "role": role,
            "content": content,
            "created_at": datetime.utcnow(),
        }
        result = await db.ai_chat.insert_one(doc)
        return result.inserted_id is not None

    @staticmethod
    async def get_history(ticket_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Return chat messages for a ticket, sorted oldest-first."""
        db = mongodb_manager.get_database()
        if db is None:
            return []

        cursor = db.ai_chat.find({"ticket_id": ticket_id}).sort("created_at", 1).limit(limit)
        messages = await cursor.to_list(length=limit)
        for m in messages:
            m["_id"] = str(m["_id"])
            if isinstance(m.get("created_at"), datetime):
                m["created_at"] = m["created_at"].isoformat()
        return messages
