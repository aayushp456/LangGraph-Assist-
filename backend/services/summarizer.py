from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.config import Settings
from backend.services.llm import LLMProvider


class SummarizerService:
    def __init__(self, llm: LLMProvider, settings: Optional[Settings] = None):
        self.llm = llm
        self.settings = settings or Settings()
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a support assistant. Summarize the ticket in 3-5 concise bullet points "
                    "focused on issue, context, customer impact, and requested action.",
                ),
                ("user", "{text}"),
            ]
        )
        self._chain = self._prompt | self.llm.model | StrOutputParser()

    def summarize(self, text: str) -> str:
        try:
            return self._chain.invoke({"text": text})
        except Exception:
            return self._fallback_summary(text)

    @staticmethod
    def _fallback_summary(text: str) -> str:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            return "- No ticket text provided."
        snippet = cleaned[:400]
        return (
            "- Issue reported by customer.\n"
            f"- Details: {snippet}\n"
            "- Recommended action: agent review and respond."
        )
