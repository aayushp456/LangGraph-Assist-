import asyncio
import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.db.mongodb import mongodb_manager
from backend.db.repositories import TicketRepository

async def parse_csv_row(row: pd.Series) -> Dict[str, Any]:
    """Parse a CSV row into MongoDB ticket schema."""
    
    # Parse dates
    purchase_date = None
    if pd.notna(row.get("Date of Purchase")):
        try:
            purchase_date = pd.to_datetime(row["Date of Purchase"])
        except:
            pass
    
    # Parse numeric fields
    age = None
    if pd.notna(row.get("Customer Age")):
        try:
            age = int(row["Customer Age"])
        except:
            pass
    
    first_response_time = None
    if pd.notna(row.get("First Response Time")):
        try:
            first_response_time = float(row["First Response Time"])
        except:
            pass
    
    time_to_resolution = None
    if pd.notna(row.get("Time to Resolution")):
        try:
            time_to_resolution = float(row["Time to Resolution"])
        except:
            pass
    
    satisfaction_rating = None
    if pd.notna(row.get("Customer Satisfaction Rating")):
        try:
            satisfaction_rating = float(row["Customer Satisfaction Rating"])
        except:
            pass
    
    ticket = {
        "ticket_id": str(row.get("Ticket ID", "")),
        "customer": {
            "email": str(row.get("Customer Email", "")),
            "gmail": str(row.get("Customer Gmail", "")),
            "age": age,
            "gender": str(row.get("Customer Gender", "")) if pd.notna(row.get("Customer Gender")) else None
        },
        "product": {
            "name": str(row.get("Product Purchased", "")) if pd.notna(row.get("Product Purchased")) else None,
            "purchase_date": purchase_date
        },
        "ticket": {
            "type": str(row.get("Ticket Type", "")) if pd.notna(row.get("Ticket Type")) else None,
            "subject": str(row.get("Ticket Subject", "")),
            "description": str(row.get("Ticket Description", "")),
            "status": str(row.get("Ticket Status", "new")).lower(),
            "priority": str(row.get("Ticket Priority", "medium")).lower() if pd.notna(row.get("Ticket Priority")) else "medium",
            "channel": str(row.get("Ticket Channel", "")) if pd.notna(row.get("Ticket Channel")) else None
        },
        "resolution": {
            "text": str(row.get("Resolution", "")) if pd.notna(row.get("Resolution")) else None,
            "resolved_at": None,
            "resolution_time_minutes": time_to_resolution
        },
        "metrics": {
            "first_response_time": first_response_time,
            "time_to_resolution": time_to_resolution,
            "satisfaction_rating": satisfaction_rating
        },
        "routing": {
            "category": None,
            "confidence": None,
            "reason": None,
            "routed_at": None
        },
        "ai_analysis": {
            "sentiment": None,
            "summary": None,
            "suggested_solution": None,
            "retrieved_docs": [],
            "confidence_score": None
        },
        "created_at": purchase_date or datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    return ticket

async def import_csv(csv_path: str, batch_size: int = 100, analyze: bool = False):
    """Import historical tickets from CSV file."""
    
    print(f"Reading CSV file: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"Found {len(df)} rows in CSV")
    
    # Connect to MongoDB
    await mongodb_manager.connect()
    
    if not mongodb_manager.is_connected():
        print("Error: MongoDB not connected. Check your MONGODB_URI and USE_MONGODB settings.")
        return
    
    print("Connected to MongoDB")
    
    # Process in batches
    total_imported = 0
    errors = 0
    
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        tickets = []
        
        for _, row in batch.iterrows():
            try:
                ticket = await parse_csv_row(row)
                tickets.append(ticket)
            except Exception as e:
                print(f"Error parsing row: {e}")
                errors += 1
        
        if tickets:
            try:
                count = await TicketRepository.bulk_insert(tickets)
                total_imported += count
                print(f"Imported batch {i//batch_size + 1}: {count} tickets (Total: {total_imported})")
            except Exception as e:
                print(f"Error importing batch: {e}")
                errors += len(tickets)
    
    print(f"\nImport complete!")
    print(f"Total imported: {total_imported}")
    print(f"Errors: {errors}")
    
    if analyze:
        print("\nNote: AI analysis for historical tickets will be implemented in Phase 3")
    
    await mongodb_manager.close()

def main():
    parser = argparse.ArgumentParser(description="Import historical tickets from CSV")
    parser.add_argument("--file", required=True, help="Path to CSV file")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for import")
    parser.add_argument("--analyze", action="store_true", help="Run AI analysis on imported tickets")
    
    args = parser.parse_args()
    
    if not Path(args.file).exists():
        print(f"Error: File not found: {args.file}")
        return
    
    asyncio.run(import_csv(args.file, args.batch_size, args.analyze))

if __name__ == "__main__":
    main()
