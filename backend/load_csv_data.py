#!/usr/bin/env python3
"""
Load historical ticket data from CSV file into the database.
This replaces the seed_data.py script with your actual dataset.

Usage:
    python backend/load_csv_data.py <path_to_csv_file>
    
    Or set CSV_IMPORT_PATH in .env file:
    CSV_IMPORT_PATH=/Users/aayushpatel/Downloads/customer_support_tickets.csv

CSV Format Expected:
    - Required: One of these columns for ticket text:
      * 'Ticket Subject' or 'subject' or 'text' or 'Ticket Description'
    - Optional columns:
      * 'Ticket Status' or 'status' (defaults to "new")
      * 'sentiment' (auto-detected if missing)
      * 'category' (auto-routed by AI if missing)
    
Note: Categories (FAQ, ESCALATE, SUMMARIZE) are automatically determined by AI.
"""

import sys
import csv
import random
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.sqlite_db import init_db, create_ticket, update_ticket_routing
from backend.services.sentiment import SentimentService
from backend.services.rag import RAGRouterService
from backend.services.llm import LLMProvider
from backend.services.embeddings import EmbeddingsService
from backend.services.pinecone_store import PineconeVectorStore
from backend.config import Settings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def load_csv_tickets(csv_path: str, auto_route: bool = True):
    """Load tickets from CSV file and insert into database"""
    
    # Initialize database
    init_db()
    
    # Initialize sentiment service for auto-detection
    sentiment_service = SentimentService()
    
    # Initialize routing service if auto-routing is enabled
    rag_service = None
    if auto_route:
        print("Initializing AI routing service...")
        try:
            settings = Settings()
            llm = LLMProvider(settings)
            embeddings = EmbeddingsService(settings)
            vector_store = PineconeVectorStore(
                embeddings_service=embeddings,
                api_key=settings.pinecone_api_key,
                index_name=settings.pinecone_index_name,
                dimension=settings.embedding_dim,
                cloud=settings.pinecone_cloud,
                region=settings.pinecone_region
            )
            rag_service = RAGRouterService(llm, vector_store, embeddings)
            print("✓ AI routing ready")
        except Exception as e:
            print(f"Warning: Could not initialize AI routing: {e}")
            print("Tickets will be loaded without categories (UNPROCESSED)")
            auto_route = False
    
    print(f"Loading tickets from: {csv_path}")
    
    tickets_loaded = 0
    tickets_routed = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Find the subject column (try multiple possible names)
        subject_col = None
        for col in ['Ticket Subject', 'subject', 'text', 'Ticket Description', 'description']:
            if col in reader.fieldnames:
                subject_col = col
                break
        
        if not subject_col:
            print(f"Error: Could not find subject column. Available columns: {reader.fieldnames}")
            sys.exit(1)
        
        print(f"Using '{subject_col}' as ticket subject")
        
        # Find status column
        status_col = None
        for col in ['Ticket Status', 'status', 'Status']:
            if col in reader.fieldnames:
                status_col = col
                break
        
        for row in reader:
            # Get subject/text
            subject = row.get(subject_col, '').strip()
            if not subject:
                continue
            
            # Get or detect sentiment
            sentiment = row.get('sentiment', '').strip()
            if not sentiment:
                sentiment_result = sentiment_service.analyze(subject)
                sentiment = sentiment_result.label
            
            # Get status
            status = 'new'
            if status_col:
                csv_status = row.get(status_col, '').strip().lower()
                # Map common status values
                status_map = {
                    'open': 'new',
                    'pending': 'in_progress',
                    'closed': 'resolved',
                    'resolved': 'resolved',
                    'escalated': 'escalated'
                }
                status = status_map.get(csv_status, 'new')
            
            # Create ticket
            ticket_id = create_ticket(subject, status, sentiment)
            tickets_loaded += 1
            
            # Auto-route using AI if enabled
            if auto_route and rag_service:
                try:
                    route_result = rag_service.route(subject, top_k=3)
                    category = route_result.get('category', 'UNKNOWN')
                    confidence = route_result.get('confidence', 0.0)
                    update_ticket_routing(ticket_id, category, confidence)
                    tickets_routed += 1
                except Exception as e:
                    print(f"Warning: Could not route ticket {ticket_id}: {e}")
            
            if tickets_loaded % 10 == 0:
                status_msg = f"Loaded {tickets_loaded} tickets..."
                if auto_route:
                    status_msg += f" (routed: {tickets_routed})"
                print(status_msg)
    
    print(f"\n✅ Successfully loaded {tickets_loaded} tickets from CSV")
    if auto_route:
        print(f"✅ AI-routed {tickets_routed} tickets into categories")
    print(f"Database: backend/data/tickets.db")
    return tickets_loaded


if __name__ == "__main__":
    # Try to get CSV path from command line argument or environment variable
    csv_path = None
    
    if len(sys.argv) >= 2:
        csv_path = sys.argv[1]
    else:
        csv_path = os.getenv("CSV_IMPORT_PATH")
    
    if not csv_path:
        print("Usage: python backend/load_csv_data.py <path_to_csv_file>")
        print("\nOr set CSV_IMPORT_PATH in .env file:")
        print("  CSV_IMPORT_PATH=/Users/aayushpatel/Downloads/customer_support_tickets.csv")
        print("\nExample:")
        print("  python backend/load_csv_data.py ~/Downloads/support_tickets.csv")
        print("\nCSV Format:")
        print("  Required: text (or subject), category")
        print("  Optional: status, sentiment")
        sys.exit(1)
    
    if not Path(csv_path).exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)
    
    load_csv_tickets(csv_path)
