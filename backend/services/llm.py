from typing import List, Optional, Dict, Any
import json
from openai import OpenAI

from backend.config import Settings


class LLMProvider:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        if not self.settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required")
            
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.settings.openrouter_api_key,
            # Attach OpenRouter-friendly headers once at client creation
            default_headers={
                "HTTP-Referer": "https://github.com/aayushp456/LangGraph-Assist-",
                "X-Title": "Support Copilot",
            },
        )
        self._model = self.settings.openrouter_chat_model

    def _get_headers(self) -> Dict[str, str]:
        """Get headers including OpenRouter specific headers"""
        return {
            "HTTP-Referer": "https://github.com/aayushp456/LangGraph-Assist-",  # Optional for tracking
            "X-Title": "Support Copilot"  # Optional, shown in OpenRouter logs
        }

    def chat_json(self, system_prompt: str, user_content: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a chat message and parse the response as JSON"""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            
            # Prepare the request with conservative defaults to reduce token usage
            request_kwargs: Dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_tokens": 256,
                "temperature": 0.2,
            }
            if extra:
                request_kwargs.update(extra)
            
            # Make the API call
            response = self._client.chat.completions.create(**request_kwargs)
            
            # Parse and return the JSON response
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from model")
                
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}")
        except Exception as e:
            raise RuntimeError(f"Chat completion failed: {str(e)}")

    def chat_text(self, system_prompt: str, user_content: str, extra: Optional[Dict[str, Any]] = None) -> str:
        """Send a chat message and return the raw text response"""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            
            # Prepare the request with conservative defaults to reduce token usage
            request_kwargs: Dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "max_tokens": 256,
                "temperature": 0.2,
            }
            if extra:
                request_kwargs.update(extra)
            
            # Make the API call
            response = self._client.chat.completions.create(**request_kwargs)
            
            # Return the text response
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from model")
                
            return content
            
        except Exception as e:
            raise RuntimeError(f"Chat completion failed: {str(e)}")
            
    # Helper method for streaming responses if needed
    def stream_chat(self, system_prompt: str, user_content: str, **kwargs):
        """Stream chat completion response"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        
        return self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
            **kwargs
        )
