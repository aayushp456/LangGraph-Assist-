from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from backend.services.llm import LLMProvider


class QueryVariations(BaseModel):
    variations: List[str] = Field(
        description="List of 2-3 alternative phrasings of the original query"
    )


class QueryExpander:
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self._prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a query expansion assistant. Given a support ticket query, "
                "generate 2-3 alternative phrasings that capture the same intent but use different words. "
                "Focus on synonyms, related terms, and different ways customers might describe the same issue."
            ),
            (
                "user",
                "Original query: {query}\n\nGenerate alternative phrasings:"
            )
        ])
        self._chain = self._prompt | self.llm.structured_model(QueryVariations)

    def expand(self, query: str, include_original: bool = True) -> List[str]:
        try:
            result = self._chain.invoke({"query": query})
            variations = result.variations if hasattr(result, 'variations') else result.get('variations', [])
            
            if include_original:
                return [query] + variations
            return variations
        except Exception as e:
            print(f"Query expansion (LLM) failed, using heuristic fallback: {e}")
            return self.expand_simple(query)

    def expand_simple(self, query: str) -> List[str]:
        """Fallback heuristic-based expansion without LLM"""
        variations = [query]
        
        # Simple synonym replacements
        replacements = {
            "password": ["login", "credentials", "authentication"],
            "reset": ["recover", "restore", "change"],
            "error": ["issue", "problem", "bug"],
            "payment": ["billing", "charge", "transaction"],
            "refund": ["reimbursement", "money back", "return"],
            "account": ["profile", "user"],
            "delete": ["remove", "cancel"],
        }
        
        query_lower = query.lower()
        for original, synonyms in replacements.items():
            if original in query_lower:
                for synonym in synonyms[:1]:  # Use only first synonym
                    variations.append(query_lower.replace(original, synonym))
        
        return variations[:3]
