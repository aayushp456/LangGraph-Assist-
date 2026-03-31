import asyncio
from typing import Type, Optional, Dict, Any
from pydantic import BaseModel
import json
import re
from google import genai
from google.genai import types


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", temperature: float = 0.2, max_tokens: int = 4096):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        """Generate text completion using Google Gemini."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                ),
            )
            return response.text
        except Exception as e:
            raise Exception(f"Gemini generation failed: {e}")

    def _extract_json(self, text: str) -> str:
        """Extract JSON from model response, stripping markdown/thinking tokens."""
        text = text.strip()
        # Remove markdown code fences
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        # If still not valid, try to find the first { ... } or [ ... ]
        if text and text[0] not in ('{', '['):
            match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
            if match:
                text = match.group(1)
        return text

    def structured_generate(self, prompt: str, schema: Type[BaseModel]) -> BaseModel:
        """Generate structured output matching a Pydantic schema."""
        schema_json = schema.model_json_schema()
        enhanced_prompt = (
            f"{prompt}\n\n"
            f"You must respond with valid JSON matching this schema:\n"
            f"{json.dumps(schema_json, indent=2)}\n\n"
            f"Respond only with the JSON object, no additional text."
        )

        last_error = None
        for attempt, token_budget in enumerate([self.max_tokens, self.max_tokens * 2]):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=enhanced_prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=token_budget,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )

                response_text = self._extract_json(response.text)
                data = json.loads(response_text)
                return schema(**data)

            except (json.JSONDecodeError, Exception) as e:
                last_error = e
                if attempt == 0:
                    print(f"Gemini structured generation attempt 1 failed, retrying with {self.max_tokens * 2} tokens: {e}")
                    continue
                break

        raise Exception(f"Gemini structured generation failed: {last_error}")

    def chat(self, messages: list) -> str:
        """Chat completion using message history."""
        try:
            contents = []
            for msg in messages:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                ),
            )
            return response.text
        except Exception as e:
            raise Exception(f"Gemini chat failed: {e}")

    # ------------------------------------------------------------------
    # Async variants — use client.aio to avoid thread-pool deadlocks
    # ------------------------------------------------------------------

    async def generate_async(self, prompt: str, timeout_s: float = 60.0) -> str:
        """Async text completion using Google Gemini."""
        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_tokens,
                    ),
                ),
                timeout=timeout_s,
            )
            return response.text
        except asyncio.TimeoutError:
            raise Exception(f"Gemini async generation timed out after {timeout_s}s")
        except Exception as e:
            raise Exception(f"Gemini async generation failed: {e}")

    async def structured_generate_async(
        self,
        prompt: str,
        schema: Type[BaseModel],
        timeout_s: float = 60.0,
    ) -> BaseModel:
        """Async structured output matching a Pydantic schema."""
        schema_json = schema.model_json_schema()
        enhanced_prompt = (
            f"{prompt}\n\n"
            f"You must respond with valid JSON matching this schema:\n"
            f"{json.dumps(schema_json, indent=2)}\n\n"
            f"Respond only with the JSON object, no additional text."
        )

        last_error = None
        for attempt, token_budget in enumerate([self.max_tokens, self.max_tokens * 2]):
            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=self.model,
                        contents=enhanced_prompt,
                        config=types.GenerateContentConfig(
                            temperature=self.temperature,
                            max_output_tokens=token_budget,
                            response_mime_type="application/json",
                            thinking_config=types.ThinkingConfig(thinking_budget=0),
                        ),
                    ),
                    timeout=timeout_s,
                )

                response_text = self._extract_json(response.text)
                data = json.loads(response_text)
                return schema(**data)

            except asyncio.TimeoutError as e:
                # Don't retry on timeout — it would double the wait time
                raise Exception(f"Gemini async structured generation timed out after {timeout_s}s")
            except json.JSONDecodeError as e:
                last_error = e
                if attempt == 0:
                    print(f"Gemini async structured attempt 1 failed (JSON parse), retrying with {self.max_tokens * 2} tokens: {e}")
                    continue
                break
            except Exception as e:
                last_error = e
                if attempt == 0:
                    print(f"Gemini async structured attempt 1 failed, retrying: {e}")
                    continue
                break

        raise Exception(f"Gemini async structured generation failed: {last_error}")
