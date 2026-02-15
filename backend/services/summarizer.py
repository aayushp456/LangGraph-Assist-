from typing import Optional

from backend.config import Settings
from backend.services.llm import LLMProvider


class SummarizerService:
    def __init__(self, llm: LLMProvider, settings: Optional[Settings] = None):
        self.llm = llm
        self.settings = settings or Settings()

    def summarize(self, text: str) -> str:
        system_prompt = (
            "You are a support assistant. Summarize the ticket in 3-5 bullet points focusing on issue, context, and requested action."
        )
        return self.llm.chat_text(system_prompt, text)
