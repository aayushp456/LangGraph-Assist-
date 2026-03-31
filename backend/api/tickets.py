"""
Ticket API endpoints — MongoDB-only, new 7-category routing, Pinecone ticket namespace
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import time

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class IngestTicketRequest(BaseModel):
    subject: str = Field(..., description="Ticket subject/title")
    description: str = Field("", description="Detailed ticket description")
    customer_email: Optional[str] = Field(None, description="Customer email")
    customer_name: Optional[str] = Field(None, description="Customer name")
    company: Optional[str] = Field(None, description="Customer company")
    priority: Optional[str] = Field("medium", description="Priority: low, medium, high, critical")
    channel: Optional[str] = Field("web", description="Channel: web, email, phone, chat, api")
    environment: Optional[str] = Field(None, description="Environment: production, staging, development")
    product: Optional[str] = Field(None, description="Product or service name")
    version: Optional[str] = Field(None, description="Product version")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for the ticket")
    auto_analyze: bool = Field(True, description="Automatically run AI analysis")


class IngestTicketResponse(BaseModel):
    ticket_id: str
    subject: str
    status: str
    category: Optional[str] = None
    severity: Optional[str] = None
    sentiment: Optional[str] = None
    confidence: Optional[float] = None
    suggested_solution: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[float] = None


class BulkIngestRequest(BaseModel):
    tickets: List[IngestTicketRequest]


class UpdateStatusRequest(BaseModel):
    ticket_id: str
    status: str


class AssignTeamRequest(BaseModel):
    ticket_id: str
    assigned_team: str


class ForwardTicketRequest(BaseModel):
    team: str
    note: str = ""


class ReplyRequest(BaseModel):
    body: str = Field(..., description="Reply message body")


# ---------------------------------------------------------------------------
# Background AI analysis (runs after HTTP response is returned)
# ---------------------------------------------------------------------------
async def _run_ai_analysis(ticket_id: str, subject: str, description: str, priority: str, product: Optional[str]):
    """Run all AI analysis in background so the server stays responsive."""
    from backend.db.repositories import TicketRepository, TicketSolutionsRepository
    from backend.websocket_manager import manager

    try:
        from backend.main import rag_service, decision_engine, store, sentiment as sentiment_svc, solution_service, summarizer as summarizer_svc

        if not rag_service:
            print(f"[BG] Skipping AI analysis for {ticket_id}: RAG service not initialized")
            return

        text = f"{subject}\n\n{description}"
        start = time.time()

        # --- Batch 1: Route + Sentiment + Summarize run concurrently ---
        async def _safe_sentiment():
            if sentiment_svc:
                # Sentiment is pure Python (no I/O) — safe to call directly
                return sentiment_svc.analyze(text)
            return {"label": "neutral", "score": 0.5}

        async def _safe_summary():
            if summarizer_svc:
                return await summarizer_svc.summarize_async(text)
            return ""

        route_result, sentiment_result, summary = await asyncio.gather(
            rag_service.route_async(text, 5),
            _safe_sentiment(),
            _safe_summary(),
        )

        sentiment_label = sentiment_result.label if hasattr(sentiment_result, "label") else sentiment_result.get("label", "neutral")
        sentiment_score = float(sentiment_result.score if hasattr(sentiment_result, "score") else sentiment_result.get("score", 0.5))

        # --- Batch 2: Retrieve KB + Generate solution (need category from route) ---
        category = route_result.get("category", "GENERAL_INQUIRY")
        severity = route_result.get("severity", "SEV3")

        top_matches = await rag_service.retrieve_async(text, 5) if rag_service.store else []
        solution = await solution_service.generate_solution_async(text, top_matches, category) if solution_service else None

        # --- Decision engine (needs all above) ---
        solution_dict = solution.__dict__ if solution else {}
        decision = await asyncio.to_thread(
            decision_engine.decide,
            {"ticket": {"description": text, "priority": priority, "severity": severity}},
            route_result,
            solution_dict,
            top_matches,
            sentiment_label,
        ) if decision_engine else None

        # 7. Assign team based on decision or category
        assigned_team = decision.assigned_team if decision and decision.assigned_team else {
            "BUG": "engineering", "PERFORMANCE": "engineering",
            "API_ISSUE": "api-platform", "SECURITY": "security",
            "INFRASTRUCTURE": "devops", "FEATURE_REQUEST": "product",
        }.get(category, "general")
        await TicketRepository.update_assignment(ticket_id, assigned_team)

        # 8. Update ticket in MongoDB
        await TicketRepository.update_routing(
            ticket_id, category, route_result.get("confidence", 0.0),
            reason=route_result.get("reason", ""), severity=severity,
        )
        await TicketRepository.update_ai_analysis(
            ticket_id,
            sentiment=sentiment_label,
            sentiment_score=sentiment_score,
            summary=summary,
        )
        await TicketSolutionsRepository.upsert(
            ticket_id,
            suggested_solution=solution_dict,
            decision=decision.__dict__ if decision else {},
            matched_kb_articles=[m.get("id", "") for m in top_matches[:5]],
            similar_tickets=[],
        )

        # 8. Embed ticket in Pinecone 'tickets' namespace
        if store:
            try:
                store.index_texts(
                    texts=[text],
                    metadatas=[{
                        "ticket_id": ticket_id,
                        "category": category,
                        "priority": priority,
                        "severity": severity,
                        "product": product or "",
                        "status": "new",
                    }],
                    namespace="tickets",
                )
            except Exception as emb_err:
                print(f"[BG] Ticket embedding failed (non-fatal): {emb_err}")

        # 9. WebSocket events
        await manager.emit_ticket_created({
            "ticket_id": ticket_id,
            "subject": subject,
            "category": category,
            "severity": severity,
            "sentiment": sentiment_label,
        })
        await manager.emit_insight_generated(ticket_id, {
            "route": route_result,
            "sentiment": {"label": sentiment_label, "score": sentiment_score},
            "summary": summary,
        })
        if solution:
            await manager.emit_solution_suggested(ticket_id, solution_dict)
        await manager.emit_ticket_assigned(ticket_id, assigned_team)

        # 11. Emit triage stats update so dashboard refreshes via WS
        try:
            fresh_stats = await TicketRepository.get_triage_stats()
            await manager.emit_triage_stats_updated(fresh_stats)
        except Exception:
            pass

        elapsed = (time.time() - start) * 1000
        print(f"✓ AI analysis complete for {ticket_id} ({elapsed:.0f}ms)")

    except Exception as e:
        print(f"✗ Background AI analysis failed for {ticket_id}: {e}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/ingest", response_model=IngestTicketResponse)
async def ingest_ticket(request: IngestTicketRequest, background_tasks: BackgroundTasks):
    """
    Ingest a new ticket. Returns immediately after creating the ticket in MongoDB.
    AI analysis (routing, sentiment, solution, etc.) runs in the background.
    """
    from backend.db.repositories import TicketRepository

    # Build ticket document
    ticket_data: Dict[str, Any] = {
        "subject": request.subject,
        "description": request.description,
        "priority": request.priority or "medium",
        "channel": request.channel or "web",
        "environment": request.environment,
        "product": request.product,
        "version": request.version,
        "tags": request.tags or [],
        "customer": {
            "email": request.customer_email,
            "name": request.customer_name,
            "company": request.company,
        },
    }

    ticket_id = await TicketRepository.create(ticket_data)

    # Schedule AI analysis in background (non-blocking)
    if request.auto_analyze:
        background_tasks.add_task(
            _run_ai_analysis,
            ticket_id=ticket_id,
            subject=request.subject,
            description=request.description,
            priority=request.priority or "medium",
            product=request.product,
        )

    return IngestTicketResponse(
        ticket_id=ticket_id,
        subject=request.subject,
        status="new",
    )


@router.post("/ingest/bulk")
async def bulk_ingest_tickets(request: BulkIngestRequest, background_tasks: BackgroundTasks):
    results = []
    errors = []
    for idx, ticket_req in enumerate(request.tickets):
        try:
            result = await ingest_ticket(ticket_req, background_tasks)
            results.append(result)
        except Exception as e:
            errors.append({"index": idx, "subject": ticket_req.subject, "error": str(e)})
    return {
        "total": len(request.tickets),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


@router.get("/priority-queue")
async def get_priority_queue(team: Optional[str] = None):
    from backend.db.repositories import TicketRepository
    tickets = await TicketRepository.get_priority_queue(limit=20, team=team)
    return {"total": len(tickets), "tickets": tickets}


@router.get("/by-category/{category}")
async def get_tickets_by_category(category: str, status: Optional[str] = None, team: Optional[str] = None):
    from backend.db.repositories import TicketRepository
    tickets = await TicketRepository.find_all(
        category=category.upper(), status=status, team=team, limit=200,
    )
    return {"category": category, "status": status, "count": len(tickets), "tickets": tickets}


@router.get("/stats/triage")
async def get_triage_stats(team: Optional[str] = None):
    from backend.db.repositories import TicketRepository
    return await TicketRepository.get_triage_stats(team=team)


@router.patch("/status")
async def update_ticket_status(request: UpdateStatusRequest):
    from backend.db.repositories import TicketRepository
    updated = await TicketRepository.update_status(request.ticket_id, request.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ok": True, "ticket_id": request.ticket_id, "status": request.status}


@router.patch("/assign")
async def assign_ticket_team(request: AssignTeamRequest):
    from backend.db.repositories import TicketRepository
    from backend.websocket_manager import manager
    updated = await TicketRepository.update_assignment(request.ticket_id, request.assigned_team)
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await manager.emit_ticket_assigned(request.ticket_id, request.assigned_team)
    return {"ok": True, "ticket_id": request.ticket_id, "assigned_team": request.assigned_team}


@router.post("/{ticket_id}/forward")
async def forward_ticket(ticket_id: str, request: ForwardTicketRequest):
    """Forward a ticket to a specialist team with an optional internal note."""
    from backend.db.repositories import TicketRepository, ConversationRepository
    from backend.websocket_manager import manager

    ticket = await TicketRepository.find_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # 1. Assign team + set status to forwarded
    await TicketRepository.update_assignment(ticket_id, request.team)
    await TicketRepository.update_status(ticket_id, "forwarded")

    # 2. Log internal note if provided
    if request.note.strip():
        await ConversationRepository.add_message(
            ticket_id=ticket_id,
            sender="system",
            body=f"Forwarded to {request.team} team: {request.note}",
            msg_type="note",
        )
    else:
        await ConversationRepository.add_message(
            ticket_id=ticket_id,
            sender="system",
            body=f"Ticket forwarded to {request.team} team",
            msg_type="status_change",
        )

    # 3. WebSocket events
    await manager.emit_ticket_assigned(ticket_id, request.team)
    try:
        fresh_stats = await TicketRepository.get_triage_stats()
        await manager.emit_triage_stats_updated(fresh_stats)
    except Exception:
        pass

    return {"ok": True, "ticket_id": ticket_id, "team": request.team, "status": "forwarded"}


@router.post("/{ticket_id}/reply")
async def reply_to_ticket(ticket_id: str, request: ReplyRequest):
    """Send a reply to a ticket. Logs in conversation history, sets status to waiting_on_customer."""
    from backend.db.repositories import TicketRepository, ConversationRepository
    from backend.websocket_manager import manager

    ticket = await TicketRepository.find_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # 1. Log reply in conversation history
    message = await ConversationRepository.add_message(
        ticket_id=ticket_id,
        sender="agent",
        body=request.body,
        msg_type="reply",
        email_status="simulated",
    )

    # 2. Update ticket status
    await TicketRepository.update_status(ticket_id, "waiting_on_customer")

    # 3. Set first_response_at if not already set
    db = (await TicketRepository.find_by_id(ticket_id)) or {}
    if not db.get("first_response_at"):
        from backend.db.mongodb import mongodb_manager
        mdb = mongodb_manager.get_database()
        if mdb is not None:
            await mdb.tickets.update_one(
                {"ticket_id": ticket_id},
                {"$set": {"first_response_at": datetime.utcnow()}},
            )

    # 4. Emit WS events
    await manager.emit_reply_sent(ticket_id, message)
    await manager.emit_agent_message(ticket_id, message)  # For customer portal
    await manager.emit_ticket_updated(ticket_id, {"status": "waiting_on_customer"})

    # 5. Refresh triage stats
    try:
        fresh_stats = await TicketRepository.get_triage_stats()
        await manager.emit_triage_stats_updated(fresh_stats)
    except Exception:
        pass

    return {
        "ok": True,
        "message": message,
        "ticket_status": "waiting_on_customer",
    }


@router.post("/{ticket_id}/close")
async def close_ticket(ticket_id: str):
    """Close/resolve a ticket. Calculates resolution time."""
    from backend.db.repositories import TicketRepository, ConversationRepository
    from backend.websocket_manager import manager

    ticket = await TicketRepository.find_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # 1. Update status to resolved
    await TicketRepository.update_status(ticket_id, "resolved")

    # 2. Calculate resolution time
    resolved_at = datetime.utcnow()
    created_at = ticket.get("created_at", resolved_at)
    resolution_time_ms = (resolved_at - created_at).total_seconds() * 1000

    # 3. Log system message
    await ConversationRepository.add_message(
        ticket_id=ticket_id,
        sender="system",
        body="Ticket closed by agent",
        msg_type="status_change",
        email_status="none",
    )

    # 4. Emit WS events
    await manager.emit_ticket_resolved(ticket_id, {
        "resolved_at": resolved_at.isoformat(),
        "resolution_time_ms": resolution_time_ms,
    })
    await manager.emit_ticket_updated(ticket_id, {"status": "resolved"})

    try:
        fresh_stats = await TicketRepository.get_triage_stats()
        await manager.emit_triage_stats_updated(fresh_stats)
    except Exception:
        pass

    return {
        "ok": True,
        "ticket_id": ticket_id,
        "status": "resolved",
        "resolved_at": resolved_at.isoformat(),
        "resolution_time_ms": round(resolution_time_ms),
    }


@router.get("/{ticket_id}/conversations")
async def get_conversations(ticket_id: str):
    """Get full conversation history for a ticket."""
    from backend.db.repositories import ConversationRepository
    messages = await ConversationRepository.get_history(ticket_id)
    return {"ticket_id": ticket_id, "messages": messages}


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str):
    from backend.db.repositories import TicketRepository
    ticket = await TicketRepository.find_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.delete("/{ticket_id}")
async def delete_ticket(ticket_id: str):
    from backend.db.repositories import TicketRepository
    deleted = await TicketRepository.delete(ticket_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ok": True}
