import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "backend" / "data" / "tickets.db"

def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            sentiment TEXT NOT NULL DEFAULT 'neutral',
            route_category TEXT,
            route_confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faq_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Ticket CRUD
def create_ticket(subject: str, status: str = "new", sentiment: str = "neutral") -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tickets (subject, status, sentiment) VALUES (?, ?, ?)",
        (subject, status, sentiment)
    )
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ticket_id

def get_all_tickets() -> List[Dict[str, Any]]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
    rows = cursor.fetchall()
    tickets = [dict(row) for row in rows]
    conn.close()
    return tickets

def update_ticket_status(ticket_id: int, status: str) -> bool:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, ticket_id)
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def update_ticket_routing(ticket_id: int, category: str, confidence: float) -> bool:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tickets SET route_category = ?, route_confidence = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (category, confidence, ticket_id)
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_ticket_counts_by_category() -> List[Dict[str, Any]]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COALESCE(route_category, 'UNPROCESSED') as category,
            COUNT(*) as count,
            COUNT(CASE WHEN status = 'assigned' OR status = 'in_progress' THEN 1 END) as active,
            COUNT(CASE WHEN route_category = 'ESCALATE' AND (status != 'resolved' AND status != 'escalated') THEN 1 END) as urgent
        FROM tickets
        GROUP BY route_category
        ORDER BY count DESC
    """)
    rows = cursor.fetchall()
    counts = [dict(row) for row in rows]
    conn.close()
    return counts

def delete_ticket(ticket_id: int) -> bool:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def soft_delete_ticket(ticket_id: int) -> bool:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

# FAQ items CRUD
def create_faq_item(text: str, metadata: Optional[Dict[str, Any]] = None) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    metadata_json = str(metadata) if metadata else None
    cursor.execute(
        "INSERT INTO faq_items (text, metadata) VALUES (?, ?)",
        (text, metadata_json)
    )
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id

def get_all_faq_items() -> List[Dict[str, Any]]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM faq_items ORDER BY created_at DESC")
    rows = cursor.fetchall()
    items = []
    for row in rows:
        item = dict(row)
        # Try to parse metadata back to dict if possible
        if item["metadata"]:
            try:
                import ast
                item["metadata"] = ast.literal_eval(item["metadata"])
            except Exception:
                pass
        items.append(item)
    conn.close()
    return items

def bulk_create_faq_items(items: List[Dict[str, Any]]) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    inserted = 0
    for item in items:
        text = item.get("text", "")
        metadata = item.get("metadata")
        metadata_json = str(metadata) if metadata else None
        cursor.execute(
            "INSERT INTO faq_items (text, metadata) VALUES (?, ?)",
            (text, metadata_json)
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted
