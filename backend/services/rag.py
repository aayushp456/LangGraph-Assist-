from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from pydantic import BaseModel, Field

from backend.services.llm import LLMProvider
from backend.services.store import SimpleVectorStore
from backend.services.summarizer import SummarizerService

SUPPORTED_CATEGORIES = {"FAQ", "ESCALATE", "SUMMARIZE"}


class RouteDecision(BaseModel):
    category: str = Field(
        description="Routing category. Must be one of FAQ, ESCALATE, or SUMMARIZE."
    )
    confidence: float = Field(
        description="Model confidence in range 0.0 to 1.0."
    )
    reason: str = Field(
        default="",
        description="Brief rationale for the routing decision.",
    )


class RAGRouterService:
    def __init__(
        self,
        llm: LLMProvider,
        store: Optional[SimpleVectorStore] = None,
        summarizer: Optional[SummarizerService] = None,
    ):
        self.llm = llm
        self.store = store
        self.summarizer = summarizer

        self._route_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert support triage router.\n"
                    "Classify tickets into one category:\n"
                    "- FAQ: likely answerable with known docs/common policy.\n"
                    "- ESCALATE: urgent, account/security/billing risk, legal risk, or high business impact.\n"
                    "- SUMMARIZE: ambiguous/novel issues where agent context summary is more useful.\n"
                    "Use retrieved context when available, but do not overfit to it.\n"
                    "Always return a category and confidence from 0.0 to 1.0.",
                ),
                (
                    "user",
                    "Ticket:\n{message}\n\nRetrieved context:\n{context_text}",
                ),
            ]
        )
        self._route_chain = self._route_prompt | self.llm.structured_model(RouteDecision)
        self._insights_chain = RunnableParallel(
            route=RunnableLambda(
                lambda x: self.route(
                    x["message"],
                    top_k=int(x.get("top_k", 5)),
                )
            ),
            summary=RunnableLambda(
                lambda x: self.summarizer.summarize(x["message"])
                if self.summarizer is not None
                else ""
            ),
        )

    @staticmethod
    def _normalize_category(category: Optional[str]) -> str:
        normalized = (category or "").strip().upper()
        if normalized in SUPPORTED_CATEGORIES:
            return normalized
        return "SUMMARIZE"

    @staticmethod
    def _normalize_confidence(confidence: Any) -> float:
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, value))

    @staticmethod
    def _format_context_text(contexts: List[Dict[str, Any]]) -> str:
        if not contexts:
            return "N/A"
        rows: List[str] = []
        for ctx in contexts:
            score = float(ctx.get("score") or 0.0)
            text = (ctx.get("text") or "").strip().replace("\n", " ")
            rows.append(f"[score={score:.3f}] {text[:400]}")
        return "\n".join(rows)

    @staticmethod
    def _top_matches(contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "id": c.get("id"),
                "score": c.get("score"),
                "metadata": c.get("metadata") or {},
                "text": (c.get("text") or "")[:300],
            }
            for c in contexts
        ]

    @staticmethod
    def _fallback_route(message: str) -> RouteDecision:
        text = (message or "").lower()
        escalate_terms = [
            "fraud",
            "chargeback",
            "hacked",
            "breach",
            "unauthorized",
            "payment failed",
            "locked out",
        ]
        faq_terms = [
            "how do i",
            "how to",
            "where can i",
            "reset password",
            "cancel subscription",
            "update billing",
            "change email",
        ]

        if any(term in text for term in escalate_terms):
            return RouteDecision(
                category="ESCALATE",
                confidence=0.35,
                reason="Fallback heuristic triggered by security/billing risk keywords.",
            )
        if any(term in text for term in faq_terms):
            return RouteDecision(
                category="FAQ",
                confidence=0.35,
                reason="Fallback heuristic triggered by common support FAQ patterns.",
            )
        return RouteDecision(
            category="SUMMARIZE",
            confidence=0.30,
            reason="Fallback heuristic used because model output was unavailable.",
        )

    def _retrieve_contexts(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if self.store is None or top_k <= 0:
            return []
        try:
            return self.store.search(query, top_k=top_k)
        except Exception:
            return []

    def route(self, message: str, top_k: int = 5) -> Dict[str, Any]:
        contexts = self._retrieve_contexts(message, top_k)
        try:
            decision = self._route_chain.invoke(
                {"message": message, "context_text": self._format_context_text(contexts)}
            )
        except Exception:
            decision = self._fallback_route(message)
        if isinstance(decision, dict):
            category = decision.get("category")
            confidence = decision.get("confidence")
            reason = decision.get("reason", "")
        else:
            category = decision.category
            confidence = decision.confidence
            reason = decision.reason
        result = {
            "category": self._normalize_category(category),
            "confidence": self._normalize_confidence(confidence),
            "reason": reason,
            "top_matches": self._top_matches(contexts),
        }
        return result

    def insights(self, message: str, top_k: int = 5) -> Dict[str, Any]:
        result = self._insights_chain.invoke({"message": message, "top_k": top_k})
        route_result = result.get("route") or {}
        return {
            "route": {
                "category": route_result.get("category"),
                "confidence": route_result.get("confidence"),
                "reason": route_result.get("reason", ""),
            },
            "summary": result.get("summary", ""),
            "top_matches": route_result.get("top_matches") or [],
        }

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.store is None:
            raise RuntimeError("Vector store not configured (embeddings missing).")
        return self.store.search(query, top_k=top_k)

    def index(self, items: List[Dict[str, Any]]) -> int:
        if self.store is None:
            raise RuntimeError("Vector store not configured (embeddings missing).")
        texts = [i.get("text", "") for i in items]
        metas = [i.get("metadata") or {} for i in items]
        ids = [i.get("id") for i in items]
        return self.store.index_texts(texts, metas, ids)
