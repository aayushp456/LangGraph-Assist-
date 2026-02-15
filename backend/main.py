import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Load environment variables from .env file in project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from backend.config import Settings
from backend.services.llm import LLMProvider
from backend.services.embeddings import EmbeddingsService
from backend.services.store import SimpleVectorStore
from backend.services.summarizer import SummarizerService
from backend.services.rag import RAGRouterService

app = FastAPI()

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

# Health check
@app.get("/")
def root():
    return {"message": "Backend running!"}

# Mock tickets endpoint
@app.get("/tickets")
def get_tickets():
    return [
        {"id": 1, "subject": "Refund not processed", "status": "open", "sentiment": "negative"},
        {"id": 2, "subject": "How do I reset my password?", "status": "open", "sentiment": "neutral"},
        {"id": 3, "subject": "Great service, thanks!", "status": "closed", "sentiment": "positive"},
    ]

# TicketRequest Pydantic model
class TicketRequest(BaseModel):
    message: str

# Route endpoint using OpenAI
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
