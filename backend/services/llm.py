from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from backend.config import Settings


class LLMProvider:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        if not self.settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required")

        self._headers = {
            "HTTP-Referer": self.settings.openrouter_site_url,
            "X-Title": self.settings.openrouter_app_name,
        }
        self._model = ChatOpenAI(
            model=self.settings.openrouter_chat_model,
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
            default_headers=self._headers,
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )

    @property
    def model(self) -> ChatOpenAI:
        return self._model

    def chat_json(
        self,
        system_prompt: str,
        user_content: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("user", "{user_content}")]
        )
        model = self._model.bind(**(extra or {}))
        raw = (prompt | model | StrOutputParser()).invoke({"user_content": user_content})
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("Model returned JSON that is not an object.")
        except json.JSONDecodeError:
            parser = JsonOutputParser()
            parsed = parser.parse(raw)
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("Model response could not be parsed as a JSON object.")

    def chat_text(
        self,
        system_prompt: str,
        user_content: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("user", "{user_content}")]
        )
        model = self._model.bind(**(extra or {}))
        return (prompt | model | StrOutputParser()).invoke({"user_content": user_content})

    def structured_model(self, schema: Type[BaseModel]) -> Any:
        return self._model.with_structured_output(schema)

    def stream_chat(self, system_prompt: str, user_content: str, **kwargs: Any):
        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("user", "{user_content}")]
        )
        model = self._model.bind(**kwargs)
        return (prompt | model | StrOutputParser()).stream({"user_content": user_content})
