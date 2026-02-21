from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import logging
# Load environment variables from .env file in project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from backend.config import Settings
from backend.services.llm import LLMProvider
from backend.services.embeddings import EmbeddingsService
from backend.services.store import SimpleVectorStore
from backend.services.summarizer import SummarizerService
from backend.services.rag import RAGRouterService
from backend.services.sentiment import SentimentService
from backend.db import init_db, get_all_tickets, create_ticket, update_ticket_status, update_ticket_routing, get_ticket_counts_by_category, get_all_faq_items, bulk_create_faq_items, soft_delete_ticket

app = FastAPI()

# Initialize DB on startup
@app.on_event("startup")
def on_startup():
    init_db()
    # Seed a few demo tickets if DB is empty
    tickets = get_all_tickets()
    if not tickets:
        create_ticket("Refund not processed", "new", "negative")
        create_ticket("How do I reset my password?", "new", "neutral")
        create_ticket("Great service, thanks!", "new", "positive")

# Allow frontend to talk to backend
settings = Settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
llm = LLMProvider(settings)
try:
    embeddings = EmbeddingsService(settings)
    store = SimpleVectorStore(embeddings)
except Exception:
    store = None
summarizer = SummarizerService(llm, settings)
rag = RAGRouterService(llm, store, summarizer)
sentiment = SentimentService()

# Health check
@app.get("/")
def root():
    return {"message": "Backend running!"}

# Tickets endpoints
@app.get("/tickets")
def get_tickets():
    return get_all_tickets()

class UpdateTicketStatusRequest(BaseModel):
    ticket_id: int
    status: str  # new, assigned, in_progress, resolved, escalated

@app.post("/tickets/status")
def update_ticket_status_endpoint(req: UpdateTicketStatusRequest):
    logging.info(f"Updating ticket {req.ticket_id} to status {req.status}")
    ok = update_ticket_status(req.ticket_id, req.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ok": True}

class CreateTicketRequest(BaseModel):
    subject: str
    status: str = "new"
    sentiment: str = "neutral"
    auto_process: bool = False

@app.post("/tickets")
def create_new_ticket(req: CreateTicketRequest):
    ticket_id = create_ticket(req.subject, req.status, req.sentiment)
    created = {"id": ticket_id, "subject": req.subject, "status": req.status, "sentiment": req.sentiment}
    if not req.auto_process:
        return created

    try:
        insight = rag.insights(req.subject, top_k=5)
        route_data = insight.get("route") or {}
        update_ticket_routing(
            ticket_id,
            route_data.get("category", "UNKNOWN"),
            route_data.get("confidence", 0.0),
        )
        return {**created, "insights": insight}
    except Exception as e:
        return {**created, "insights_error": str(e)}

class IngestTicketRequest(BaseModel):
    subject: str
    status: str = "new"
    sentiment: str = "neutral"
    top_k: int = 5

@app.post("/tickets/ingest")
def ingest_ticket(req: IngestTicketRequest):
    ticket_id = create_ticket(req.subject, req.status, req.sentiment)
    created = {"id": ticket_id, "subject": req.subject, "status": req.status, "sentiment": req.sentiment}
    try:
        insight = rag.insights(req.subject, top_k=req.top_k)
        route_data = insight.get("route") or {}
        update_ticket_routing(
            ticket_id,
            route_data.get("category", "UNKNOWN"),
            route_data.get("confidence", 0.0),
        )
        return {**created, "insights": insight}
    except Exception as e:
        return {**created, "insights_error": str(e)}

# FAQ endpoints
@app.get("/faq")
def get_faq():
    return get_all_faq_items()

class BulkFaqRequest(BaseModel):
    items: List[Dict[str, Any]]

@app.post("/faq/bulk")
def bulk_faq(req: BulkFaqRequest):
    inserted = bulk_create_faq_items(req.items)
    # Also index them into the vector store if available
    if store:
        try:
            rag.index(req.items)
        except Exception as e:
            # Non-fatal: log but don't fail the request
            print(f"Failed to index FAQ items: {e}")
    return {"inserted": inserted}

@app.post("/faq/upload")
async def upload_faq(file: UploadFile = File(...)):
    if not file.filename.endswith(".jsonl"):
        raise HTTPException(status_code=400, detail="Only .jsonl files are supported")
    content = await file.read()
    lines = content.decode().strip().splitlines()
    items = []
    for line in lines:
        if line.strip():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not items:
        raise HTTPException(status_code=400, detail="No valid JSON objects found in file")
    inserted = bulk_create_faq_items(items)
    if store:
        try:
            rag.index(items)
        except Exception as e:
            print(f"Failed to index FAQ items: {e}")
    return {"inserted": inserted}

# Triage monitoring endpoint
@app.get("/triage")
def get_triage_stats():
    return get_ticket_counts_by_category()

@app.delete("/tickets/{ticket_id}")
def remove_ticket(ticket_id: int):
    ok = soft_delete_ticket(ticket_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ok": True}
class TicketRequest(BaseModel):
    message: str

# Route endpoint
@app.post("/route")
async def route_ticket(req: TicketRequest):
    try:
        result = rag.route(req.message, top_k=5)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5

@app.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    try:
        results = rag.retrieve(req.query, top_k=req.top_k)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class IndexItem(BaseModel):
    id: Optional[str] = None
    text: str
    metadata: Optional[Dict[str, Any]] = None

class IndexRequest(BaseModel):
    items: List[IndexItem]

@app.post("/index")
async def index(req: IndexRequest):
    try:
        count = rag.index([i.model_dump() for i in req.items])
        return {"indexed": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SummarizeRequest(BaseModel):
    text: str

@app.post("/summarize")
async def summarize(req: SummarizeRequest):
    try:
        return {"summary": summarizer.summarize(req.text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class InsightsRequest(BaseModel):
    text: str
    top_k: int = 5
    ticket_id: Optional[int] = None

@app.post("/insights")
async def insights(req: InsightsRequest):
    try:
        # LangChain orchestration: route + summary in one pipeline call.
        insight = rag.insights(req.text, top_k=req.top_k)
        route_result = insight.get("route") or {}
        # Sentiment (light heuristic)
        sent = sentiment.as_dict(req.text)

        # If a ticket_id is provided, update routing info in DB
        if hasattr(req, 'ticket_id') and req.ticket_id is not None:
            update_ticket_routing(req.ticket_id, route_result.get("category", "UNKNOWN"), route_result.get("confidence", 0.0))

        return {
            "route": {
                "category": route_result.get("category"),
                "confidence": route_result.get("confidence"),
                "reason": route_result.get("reason", ""),
            },
            "summary": insight.get("summary", ""),
            "sentiment": sent,
            "top_matches": insight.get("top_matches") or [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
