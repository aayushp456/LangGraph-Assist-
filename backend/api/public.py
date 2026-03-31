"""
Public API endpoints for customer portal - no authentication required
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
import re

router = APIRouter(prefix="/api/public", tags=["public"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class PublicTicketRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Customer name")
    email: EmailStr = Field(..., description="Customer email")
    subject: str = Field(..., min_length=1, max_length=200, description="Ticket subject")
    description: str = Field(..., min_length=1, max_length=5000, description="Ticket description")
    priority: Optional[str] = Field("medium", description="Priority: low, medium, high, critical")


class PublicTicketResponse(BaseModel):
    ticket_id: str
    subject: str
    status: str
    created_at: str
    message: str


class PublicMessageRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000, description="Message content")
    sender_name: Optional[str] = Field(None, description="Customer name")


class PublicTicketDetail(BaseModel):
    ticket_id: str
    subject: str
    description: str
    status: str
    priority: str
    customer_name: str
    customer_email: str
    created_at: str
    updated_at: str
    conversation: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def sanitize_input(text: str) -> str:
    """Basic sanitization to prevent XSS"""
    # Remove any HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove script tags content
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def format_ticket_for_public(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Format ticket data for public consumption (hide sensitive AI data)"""
    return {
        "ticket_id": ticket.get("ticket_id"),
        "subject": ticket.get("subject"),
        "description": ticket.get("description"),
        "status": ticket.get("status"),
        "priority": ticket.get("priority"),
        "customer_name": ticket.get("customer", {}).get("name", ""),
        "customer_email": ticket.get("customer", {}).get("email", ""),
        "created_at": ticket.get("created_at").isoformat() if isinstance(ticket.get("created_at"), datetime) else ticket.get("created_at"),
        "updated_at": ticket.get("updated_at").isoformat() if isinstance(ticket.get("updated_at"), datetime) else ticket.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/tickets", response_model=PublicTicketResponse)
async def submit_ticket(request: PublicTicketRequest, http_request: Request):
    """
    Submit a new support ticket (no authentication required).
    Triggers AI analysis in the background.
    """
    from backend.db.repositories import TicketRepository
    from backend.api.tickets import _run_ai_analysis
    import asyncio
    
    # Sanitize inputs
    name = sanitize_input(request.name)
    subject = sanitize_input(request.subject)
    description = sanitize_input(request.description)
    
    # Validate priority
    valid_priorities = ["low", "medium", "high", "critical"]
    priority = request.priority.lower() if request.priority else "medium"
    if priority not in valid_priorities:
        priority = "medium"
    
    # Create ticket
    ticket_data = {
        "subject": subject,
        "description": description,
        "priority": priority,
        "status": "new",
        "channel": "portal",
        "customer": {
            "name": name,
            "email": request.email,
        },
    }
    
    ticket_id = await TicketRepository.create(ticket_data)
    
    # Trigger AI analysis in background
    asyncio.create_task(_run_ai_analysis(
        ticket_id=ticket_id,
        subject=subject,
        description=description,
        priority=priority,
        product=None
    ))
    
    return PublicTicketResponse(
        ticket_id=ticket_id,
        subject=subject,
        status="new",
        created_at=datetime.utcnow().isoformat(),
        message=f"Ticket created successfully! Your ticket ID is {ticket_id}. Save this ID to track your ticket."
    )


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    """
    Get ticket details by ticket ID (public view - no sensitive data).
    """
    from backend.db.repositories import TicketRepository, ConversationRepository
    
    ticket = await TicketRepository.find_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Get conversation history
    conversation = await ConversationRepository.get_history(ticket_id)
    
    # Format messages for public view
    public_conversation = []
    for msg in conversation:
        public_conversation.append({
            "message_id": msg.get("message_id"),
            "sender": "You" if msg.get("sender") == "customer" else "Support Team",
            "body": msg.get("body"),
            "created_at": msg.get("created_at"),
        })
    
    # Format ticket for public
    public_ticket = format_ticket_for_public(ticket)
    public_ticket["conversation"] = public_conversation
    
    return public_ticket


@router.get("/tickets/by-email/{email}")
async def get_tickets_by_email(email: str):
    """
    Get all tickets submitted by a specific email address.
    Limited to last 50 tickets.
    """
    from backend.db.repositories import TicketRepository
    from backend.db.mongodb import mongodb_manager
    
    db = mongodb_manager.get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    # Find tickets by customer email
    cursor = db.tickets.find(
        {"customer.email": email}
    ).sort("created_at", -1).limit(50)
    
    tickets = await cursor.to_list(length=50)
    
    # Format for public view
    public_tickets = []
    for ticket in tickets:
        ticket["_id"] = str(ticket["_id"])
        public_tickets.append(format_ticket_for_public(ticket))
    
    return {
        "email": email,
        "total": len(public_tickets),
        "tickets": public_tickets
    }


@router.post("/tickets/{ticket_id}/messages")
async def add_customer_message(ticket_id: str, request: PublicMessageRequest):
    """
    Add a message to a ticket (customer reply).
    Emits WebSocket event to notify agents.
    """
    from backend.db.repositories import TicketRepository, ConversationRepository
    from backend.websocket_manager import manager
    
    # Verify ticket exists
    ticket = await TicketRepository.find_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Sanitize message
    body = sanitize_input(request.body)
    
    if not body:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Add message to conversation
    message = await ConversationRepository.add_message(
        ticket_id=ticket_id,
        sender="customer",
        body=body,
        msg_type="reply",
        email_status="portal",
    )
    
    # Update ticket status if it was resolved
    if ticket.get("status") in ["resolved", "closed"]:
        await TicketRepository.update_status(ticket_id, "open")
    
    # Emit WebSocket event to agents
    await manager.emit_customer_message(ticket_id, message)
    
    return {
        "ok": True,
        "message_id": message["message_id"],
        "created_at": message["created_at"]
    }
