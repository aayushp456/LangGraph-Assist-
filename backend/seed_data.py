"""
Seed historical data for the Support Agent application.
Creates sample tickets with various categories, statuses, and sentiments.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.sqlite_db import init_db, create_ticket, update_ticket_routing, update_ticket_status
import random

SAMPLE_TICKETS = [
    # FAQ tickets
    {"subject": "How do I reset my password?", "category": "FAQ", "status": "resolved", "sentiment": "neutral"},
    {"subject": "Where can I find my invoice from last month?", "category": "FAQ", "status": "resolved", "sentiment": "neutral"},
    {"subject": "Can I change my email address on my account?", "category": "FAQ", "status": "in_progress", "sentiment": "neutral"},
    {"subject": "How to cancel my subscription?", "category": "FAQ", "status": "new", "sentiment": "neutral"},
    {"subject": "What are your business hours?", "category": "FAQ", "status": "resolved", "sentiment": "positive"},
    
    # BILLING tickets
    {"subject": "I was charged twice for my subscription this month", "category": "ESCALATE", "status": "in_progress", "sentiment": "negative"},
    {"subject": "Payment failed but I was still charged", "category": "ESCALATE", "status": "assigned", "sentiment": "negative"},
    {"subject": "Need a refund for duplicate charge", "category": "ESCALATE", "status": "new", "sentiment": "negative"},
    {"subject": "My credit card was declined but the order went through", "category": "ESCALATE", "status": "escalated", "sentiment": "negative"},
    
    # TECHNICAL tickets
    {"subject": "The app crashes every time I try to upload a file", "category": "SUMMARIZE", "status": "in_progress", "sentiment": "negative"},
    {"subject": "Getting 500 error when saving my profile", "category": "SUMMARIZE", "status": "assigned", "sentiment": "negative"},
    {"subject": "Website is very slow today", "category": "SUMMARIZE", "status": "resolved", "sentiment": "neutral"},
    {"subject": "Cannot log in after password reset", "category": "FAQ", "status": "new", "sentiment": "negative"},
    
    # ESCALATE tickets
    {"subject": "I think my account has been hacked - unauthorized purchases", "category": "ESCALATE", "status": "escalated", "sentiment": "very_negative"},
    {"subject": "Legal notice: GDPR data deletion request", "category": "ESCALATE", "status": "assigned", "sentiment": "neutral"},
    {"subject": "Unauthorized access to my account", "category": "ESCALATE", "status": "new", "sentiment": "very_negative"},
    
    # SUMMARIZE tickets
    {"subject": "Something is wrong with my account and billing", "category": "SUMMARIZE", "status": "new", "sentiment": "neutral"},
    {"subject": "Having multiple issues with the service", "category": "SUMMARIZE", "status": "assigned", "sentiment": "negative"},
    
    # More unprocessed tickets (no category)
    {"subject": "Need help with my recent order", "category": None, "status": "new", "sentiment": "neutral"},
    {"subject": "Question about premium features", "category": None, "status": "new", "sentiment": "neutral"},
    {"subject": "App not working on my phone", "category": None, "status": "new", "sentiment": "negative"},
]

def seed_tickets():
    """Create sample tickets in the database."""
    print("Initializing database...")
    init_db()
    
    print(f"Creating {len(SAMPLE_TICKETS)} sample tickets...")
    for ticket_data in SAMPLE_TICKETS:
        ticket_id = create_ticket(
            subject=ticket_data["subject"],
            status=ticket_data["status"],
            sentiment=ticket_data["sentiment"]
        )
        
        # Update routing if category is provided
        if ticket_data["category"]:
            confidence = random.uniform(0.7, 0.95)
            update_ticket_routing(ticket_id, ticket_data["category"], confidence)
        
        print(f"  ✓ Created ticket #{ticket_id}: {ticket_data['subject'][:50]}...")
    
    print(f"\n✅ Successfully seeded {len(SAMPLE_TICKETS)} tickets!")
    print("\nTicket breakdown:")
    print(f"  - FAQ: {sum(1 for t in SAMPLE_TICKETS if t['category'] == 'FAQ')}")
    print(f"  - ESCALATE: {sum(1 for t in SAMPLE_TICKETS if t['category'] == 'ESCALATE')}")
    print(f"  - SUMMARIZE: {sum(1 for t in SAMPLE_TICKETS if t['category'] == 'SUMMARIZE')}")
    print(f"  - UNPROCESSED: {sum(1 for t in SAMPLE_TICKETS if t['category'] is None)}")

if __name__ == "__main__":
    seed_tickets()
