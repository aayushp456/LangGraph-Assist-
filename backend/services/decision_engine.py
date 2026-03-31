from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class ActionType(str, Enum):
    AUTO_RESOLVE = "auto_resolve"
    AGENT_REVIEW = "agent_review"
    ESCALATE = "escalate"
    REQUEST_INFO = "request_info"

class Decision(BaseModel):
    action: ActionType = Field(description="Recommended action to take")
    confidence: float = Field(description="Confidence in the decision (0.0-1.0)")
    reason: str = Field(description="Explanation for the decision")
    solution: Optional[Dict[str, Any]] = Field(default=None, description="Suggested solution if applicable")
    assigned_team: Optional[str] = Field(default=None, description="Team assigned to handle this ticket")
    requires_review: bool = Field(default=True, description="Whether agent review is required")
    next_steps: List[str] = Field(default_factory=list, description="Recommended next steps")

class DecisionEngine:
    def __init__(self):
        self.auto_resolve_threshold = 0.85
        self.escalate_threshold = 0.5
        self.high_priority_categories = ["SECURITY", "INFRASTRUCTURE"]
        self.auto_resolvable_categories = ["GENERAL_INQUIRY", "FEATURE_REQUEST"]
        self.category_team_map = {
            "BUG": "engineering",
            "PERFORMANCE": "engineering",
            "API_ISSUE": "api-platform",
            "SECURITY": "security",
            "INFRASTRUCTURE": "devops",
            "FEATURE_REQUEST": "product",
            "GENERAL_INQUIRY": "general",
        }
    
    def decide(
        self,
        ticket: Dict[str, Any],
        routing: Dict[str, Any],
        solution: Optional[Dict[str, Any]] = None,
        retrieved_docs: List[Dict[str, Any]] = None,
        sentiment: Optional[str] = None
    ) -> Decision:
        """
        Make an actionable decision based on ticket analysis.
        
        Args:
            ticket: Ticket data
            routing: Routing decision with category and confidence
            solution: Generated solution (if any)
            retrieved_docs: Retrieved knowledge base documents
            sentiment: Detected sentiment
        
        Returns:
            Decision object with recommended action
        """
        category = routing.get("category", "UNKNOWN")
        confidence = routing.get("confidence", 0.0)
        priority = ticket.get("ticket", {}).get("priority", "medium")
        
        # Check for escalation triggers
        if self._should_escalate(category, confidence, priority, sentiment, ticket):
            return self._create_escalation_decision(category, ticket, solution)
        
        # Check for auto-resolve eligibility
        if self._can_auto_resolve(category, confidence, solution, retrieved_docs):
            return self._create_auto_resolve_decision(solution, confidence, category)
        
        # Check if more information is needed
        if self._needs_more_info(ticket, retrieved_docs, confidence):
            return self._create_request_info_decision(ticket)
        
        # Default to agent review
        return self._create_agent_review_decision(solution, confidence, category)
    
    def _should_escalate(
        self,
        category: str,
        confidence: float,
        priority: str,
        sentiment: Optional[str],
        ticket: Dict[str, Any]
    ) -> bool:
        """Determine if ticket should be escalated."""
        severity = ticket.get("ticket", {}).get("severity", "SEV3")
        
        # Always escalate SEV1 (critical outage)
        if severity == "SEV1":
            return True
        
        # Always escalate SECURITY category
        if category == "SECURITY":
            return True
        
        # Escalate critical priority with low confidence
        if priority in ["high", "critical"] and confidence < self.escalate_threshold:
            return True
        
        # Escalate SEV2 INFRASTRUCTURE issues
        if category == "INFRASTRUCTURE" and severity in ["SEV1", "SEV2"]:
            return True
        
        # Escalate very negative sentiment
        if sentiment in ["very_negative", "angry", "frustrated"]:
            return True
        
        # Check for escalation keywords in ticket
        description = ticket.get("ticket", {}).get("description", "").lower()
        escalation_keywords = ["data loss", "outage", "breach", "unauthorized", "compromised", "down for all"]
        if any(keyword in description for keyword in escalation_keywords):
            return True
        
        return False
    
    def _can_auto_resolve(
        self,
        category: str,
        confidence: float,
        solution: Optional[Dict[str, Any]],
        retrieved_docs: Optional[List[Dict[str, Any]]]
    ) -> bool:
        """Determine if ticket can be auto-resolved."""
        # Only low-risk categories can be auto-resolved
        if category not in self.auto_resolvable_categories:
            return False
        
        # Need high confidence
        if confidence < self.auto_resolve_threshold:
            return False
        
        # Need a solution
        if not solution:
            return False
        
        # Solution must have high confidence
        solution_confidence = solution.get("confidence", 0.0)
        if solution_confidence < self.auto_resolve_threshold:
            return False
        
        # Need strong evidence from retrieved docs
        if not retrieved_docs or len(retrieved_docs) < 2:
            return False
        
        # Check if top docs have high scores
        top_scores = [doc.get("score", 0.0) for doc in retrieved_docs[:3]]
        if not top_scores or max(top_scores) < 0.7:
            return False
        
        return True
    
    def _needs_more_info(
        self,
        ticket: Dict[str, Any],
        retrieved_docs: Optional[List[Dict[str, Any]]],
        confidence: float
    ) -> bool:
        """Determine if more information is needed from customer."""
        description = ticket.get("ticket", {}).get("description", "")
        
        # Very short description might need more info
        if len(description.split()) < 10:
            return True
        
        # Low confidence with poor retrieval
        if confidence < 0.3 and (not retrieved_docs or len(retrieved_docs) < 2):
            return True
        
        return False
    
    def _create_escalation_decision(
        self,
        category: str,
        ticket: Dict[str, Any],
        solution: Optional[Dict[str, Any]]
    ) -> Decision:
        """Create an escalation decision."""
        # Determine escalation team
        escalation_team = "general"
        description = ticket.get("ticket", {}).get("description", "").lower()
        
        escalation_team = self.category_team_map.get(category, "general")
        
        if any(word in description for word in ["legal", "lawsuit", "fraud", "compliance"]):
            escalation_team = "legal"
        
        escalation_criteria = solution.get("escalation_criteria", "") if solution else ""
        
        return Decision(
            action=ActionType.ESCALATE,
            confidence=0.9,
            reason=f"Ticket requires escalation to {escalation_team} team. {escalation_criteria}",
            solution=solution,
            assigned_team=escalation_team,
            requires_review=True,
            next_steps=[
                f"Route to {escalation_team} team",
                "Notify customer of escalation",
                "Set priority to high",
                "Add escalation notes"
            ]
        )
    
    def _create_auto_resolve_decision(
        self,
        solution: Dict[str, Any],
        confidence: float,
        category: str = "GENERAL_INQUIRY",
    ) -> Decision:
        """Create an auto-resolve decision."""
        return Decision(
            action=ActionType.AUTO_RESOLVE,
            confidence=confidence,
            reason="High confidence match with strong KB evidence. Can be auto-resolved.",
            solution=solution,
            assigned_team=self.category_team_map.get(category, "general"),
            requires_review=False,
            next_steps=[
                "Send solution to customer",
                "Mark ticket as resolved",
                "Request feedback",
                "Close ticket"
            ]
        )
    
    def _create_agent_review_decision(
        self,
        solution: Optional[Dict[str, Any]],
        confidence: float,
        category: str
    ) -> Decision:
        """Create an agent review decision."""
        return Decision(
            action=ActionType.AGENT_REVIEW,
            confidence=confidence,
            reason=f"Medium confidence {category} ticket. Agent review recommended.",
            solution=solution,
            assigned_team=self.category_team_map.get(category, "general"),
            requires_review=True,
            next_steps=[
                "Review suggested solution",
                "Verify accuracy",
                "Edit if needed",
                "Send to customer"
            ]
        )
    
    def _create_request_info_decision(
        self,
        ticket: Dict[str, Any]
    ) -> Decision:
        """Create a request more info decision."""
        return Decision(
            action=ActionType.REQUEST_INFO,
            confidence=0.6,
            reason="Insufficient information to provide accurate solution.",
            assigned_team="general",
            requires_review=True,
            next_steps=[
                "Request additional details from customer",
                "Ask clarifying questions",
                "Wait for customer response",
                "Re-analyze with new information"
            ]
        )
