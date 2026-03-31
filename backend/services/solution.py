from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from backend.services.llm import LLMProvider


class SolutionResponse(BaseModel):
    draft_reply: str = Field(
        description="Customer-facing response draft that the agent can edit and send"
    )
    resolution_steps: List[str] = Field(
        description="Internal troubleshooting steps for the agent to follow"
    )
    relevant_articles: List[str] = Field(
        description="KB article IDs or URLs that are relevant to this issue"
    )
    escalation_criteria: Optional[str] = Field(
        default=None,
        description="Conditions under which this ticket should be escalated"
    )
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0 in the solution quality"
    )


class SolutionService:
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self._setup_prompts()

    def _setup_prompts(self):
        self._technical_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a technical support solution assistant for a software platform.\n"
                "The ticket is classified as: {category}\n\n"
                "Guidelines for draft_reply:\n"
                "- Professional, empathetic, concise tone\n"
                "- Acknowledge the customer's issue specifically\n"
                "- Provide clear solution steps based on retrieved KB context\n"
                "- Keep under 200 words\n"
                "- Include relevant error codes or references if available\n\n"
                "Guidelines for resolution_steps:\n"
                "- Numbered checklist format (3-7 steps)\n"
                "- Include diagnostics, fixes, and verification\n"
                "- Reference specific settings, endpoints, or config\n\n"
                "Use the retrieved context to inform your response."
            ),
            (
                "user",
                "Ticket: {ticket_text}\n\n"
                "Retrieved Context:\n{context}\n\n"
                "Generate a solution with draft reply and resolution steps."
            )
        ])

        self._escalation_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a technical support solution assistant. This {category} ticket requires escalation.\n\n"
                "Guidelines for draft_reply:\n"
                "- Acknowledge urgency and impact\n"
                "- Explain that a specialist team will handle this\n"
                "- Provide any immediate workarounds from KB context\n"
                "- Set expectations for response time\n\n"
                "Guidelines for resolution_steps:\n"
                "- Document all relevant information for the specialist\n"
                "- Note any immediate mitigations\n"
                "- Specify escalation path and team\n\n"
                "Guidelines for escalation_criteria:\n"
                "- Explain why this needs escalation (severity, impact, security risk, etc.)"
            ),
            (
                "user",
                "Ticket: {ticket_text}\n\n"
                "Retrieved Context:\n{context}\n\n"
                "Generate an escalation-focused solution."
            )
        ])

        self._inquiry_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a technical support solution assistant. This is a general inquiry or feature request.\n\n"
                "Guidelines for draft_reply:\n"
                "- Acknowledge the request\n"
                "- Provide relevant information from KB context\n"
                "- If feature request, explain how to submit formally\n"
                "- If unclear, ask clarifying questions\n\n"
                "Guidelines for resolution_steps:\n"
                "- Point to relevant documentation\n"
                "- List information needed if unclear\n"
                "- Note potential solutions to investigate"
            ),
            (
                "user",
                "Ticket: {ticket_text}\n\n"
                "Retrieved Context:\n{context}\n\n"
                "Generate a helpful response."
            )
        ])

    # Categories that use escalation prompt
    ESCALATION_CATEGORIES = {"SECURITY", "INFRASTRUCTURE"}
    # Categories that use inquiry prompt
    INQUIRY_CATEGORIES = {"GENERAL_INQUIRY", "FEATURE_REQUEST"}

    def generate_solution(
        self,
        ticket_text: str,
        top_docs: List[Dict[str, Any]],
        route_category: str = "GENERAL_INQUIRY",
    ) -> SolutionResponse:
        context = self._format_context(top_docs)
        
        # Select prompt based on category
        if route_category in self.ESCALATION_CATEGORIES:
            prompt = self._escalation_prompt
        elif route_category in self.INQUIRY_CATEGORIES:
            prompt = self._inquiry_prompt
        else:
            prompt = self._technical_prompt

        try:
            chain = prompt | self.llm.structured_model(SolutionResponse)
            result = chain.invoke({
                "ticket_text": ticket_text,
                "context": context,
                "category": route_category,
            })
            
            # Extract relevant article IDs from top docs
            if hasattr(result, 'relevant_articles') and not result.relevant_articles:
                result.relevant_articles = [
                    doc.get("id", f"doc_{i}")
                    for i, doc in enumerate(top_docs[:3])
                    if doc.get("score", 0) > 0.5
                ]
            
            return result
        except Exception as e:
            print(f"Solution generation failed: {e}")
            return self._fallback_solution(ticket_text, route_category)

    async def generate_solution_async(
        self,
        ticket_text: str,
        top_docs: List[Dict[str, Any]],
        route_category: str = "GENERAL_INQUIRY",
    ) -> SolutionResponse:
        """Async solution generation — calls Gemini via client.aio."""
        context = self._format_context(top_docs)

        if route_category in self.ESCALATION_CATEGORIES:
            prompt = self._escalation_prompt
        elif route_category in self.INQUIRY_CATEGORIES:
            prompt = self._inquiry_prompt
        else:
            prompt = self._technical_prompt

        try:
            prompt_text = prompt.format(
                ticket_text=ticket_text,
                context=context,
                category=route_category,
            )
            result = await self.llm.structured_generate_async(prompt_text, SolutionResponse)

            if hasattr(result, 'relevant_articles') and not result.relevant_articles:
                result.relevant_articles = [
                    doc.get("id", f"doc_{i}")
                    for i, doc in enumerate(top_docs[:3])
                    if doc.get("score", 0) > 0.5
                ]

            return result
        except Exception as e:
            print(f"Async solution generation failed: {e}")
            return self._fallback_solution(ticket_text, route_category)

    def _format_context(self, docs: List[Dict[str, Any]]) -> str:
        if not docs:
            return "No relevant context found."
        
        lines = []
        for i, doc in enumerate(docs[:5], 1):
            text = doc.get("text", "")[:300]
            score = doc.get("score", 0)
            lines.append(f"{i}. [score={score:.3f}] {text}")
        
        return "\n".join(lines)

    def _fallback_solution(
        self,
        ticket_text: str,
        route_category: str
    ) -> SolutionResponse:
        if route_category in self.ESCALATION_CATEGORIES:
            return SolutionResponse(
                draft_reply=(
                    "Thank you for bringing this to our attention. This matter requires immediate attention "
                    "from our specialist team. I've escalated your case and a senior engineer will contact you "
                    "within 24 hours to resolve this issue."
                ),
                resolution_steps=[
                    "Document all ticket details and environment info",
                    "Flag as high priority",
                    f"Assign to {route_category.lower()} specialist queue",
                    "Set follow-up reminder for 24 hours",
                    "Monitor for specialist response"
                ],
                relevant_articles=[],
                escalation_criteria=f"Requires {route_category.lower()} specialist attention",
                confidence=0.4
            )
        elif route_category in self.INQUIRY_CATEGORIES:
            return SolutionResponse(
                draft_reply=(
                    "Thank you for contacting us. To better assist you, could you please provide "
                    "more details? Specifically, what you're trying to achieve, any steps you've "
                    "already tried, and which product/service this relates to would be very helpful."
                ),
                resolution_steps=[
                    "Review the request details",
                    "Check knowledge base for relevant documentation",
                    "Provide links to relevant guides or docs",
                    "If feature request, log in product backlog",
                    "Follow up with the customer"
                ],
                relevant_articles=[],
                confidence=0.35
            )
        else:
            return SolutionResponse(
                draft_reply=(
                    "Thank you for reporting this issue. Our team is investigating and will provide "
                    "an update shortly. In the meantime, please share any error messages, logs, "
                    "or steps to reproduce the issue to help us resolve this faster."
                ),
                resolution_steps=[
                    "Review the ticket details and environment",
                    "Search the knowledge base for similar issues",
                    "Identify the root cause",
                    "Apply the standard resolution procedure",
                    "Verify the fix in customer's environment",
                    "Follow up with the customer"
                ],
                relevant_articles=[],
                confidence=0.3
            )
