#!/usr/bin/env python3
"""
Check actual ticket counts in database
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.sqlite_db import get_all_tickets, get_ticket_counts_by_category

def check_ticket_counts():
    """Check actual ticket counts"""
    print("🔍 Checking Ticket Counts...\n")
    
    # Get all tickets
    tickets = get_all_tickets()
    print(f"Total tickets in database: {len(tickets)}")
    
    # Count by status/category
    counts = get_ticket_counts_by_category()
    print("\nTickets by category:")
    for category, count in counts.items():
        print(f"  {category}: {count}")
    
    # Check for UNPROCESSED specifically
    unprocessed = [t for t in tickets if t.get('category') == 'UNPROCESSED']
    print(f"\nUNPROCESSED tickets: {len(unprocessed)}")
    
    # Show sample of unprocessed
    if unprocessed:
        print("\nSample unprocessed tickets:")
        for i, ticket in enumerate(unprocessed[:3], 1):
            print(f"{i}. ID: {ticket.get('id')} - \"{ticket.get('text', '')[:50]}...\"")
    
    # Check for duplicates or data issues
    if len(tickets) > 10000:
        print(f"\n⚠️  Warning: Very high ticket count ({len(tickets)})")
        print("Possible causes:")
        print("- CSV import ran multiple times")
        print("- Test data accumulation")
        print("- Database not cleared between tests")
        
        response = input("\nClear all tickets? (yes/no): ")
        if response.lower() == 'yes':
            from backend.sqlite_db import get_conn
            conn = get_conn()
            conn.execute("DELETE FROM tickets")
            conn.commit()
            conn.close()
            print("✓ All tickets cleared")
        else:
            print("No action taken")

if __name__ == "__main__":
    check_ticket_counts()
