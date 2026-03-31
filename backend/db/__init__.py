# Database package
from backend.db.mongodb import mongodb_manager
from backend.db.repositories import (
    TicketRepository,
    KnowledgeBaseRepository,
    RetrievalLogRepository,
    SolutionFeedbackRepository,
    RoutingLogRepository
)

__all__ = [
    'mongodb_manager',
    'TicketRepository',
    'KnowledgeBaseRepository',
    'RetrievalLogRepository',
    'SolutionFeedbackRepository',
    'RoutingLogRepository'
]
