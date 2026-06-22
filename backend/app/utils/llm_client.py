"""
LLM Client Wrapper
Unified OpenAI format API calls
Supports Ollama num_ctx parameter to prevent prompt truncation
Includes retry logic with exponential backoff for rate limits and transient errors
"""

import json
import os
import re
import time
import logging
from typing import Optional, Dict, Any, List

from openai import OpenAI

from ..config import Config

logger = logging.getLogger('mirofish.llm')


class LLMClient:
    """LLM Client with retry logic"""

    # Default retry configuration
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 2.0  # seconds

    # Retryable HTTP status codes
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 300.0,
        max_retries: Optional[int] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        self.max_retries = max_retries if max_retries is not None else int(
            os.environ.get('LLM_MAX_RETRIES', str(self.DEFAULT_MAX_RETRIES))
        )

        if not self.api_key:
            raise ValueError("LLM_API_KEY not configured")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )

        # Ollama context window size
        self._num_ctx = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))

    def _is_ollama(self) -> bool:
        """Check if we're talking to an Ollama server."""
        return '11434' in (self.base_url or '')

    def _should_retry(self, exc: Exception) -> bool:
        """Determine if an exception is retryable."""
        from openai import (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            InternalServerError,
            APIStatusError,
        )

        if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError)):
            return True
        if isinstance(exc, InternalServerError):
            return True
        if isinstance(exc, APIStatusError):
            return exc.status_code in self.RETRYABLE_STATUS_CODES
        # Fallback: check status_code attribute
        status_code = getattr(exc, 'status_code', None)
        if status_code and status_code in self.RETRYABLE_STATUS_CODES:
            return True
        return False

    def _get_retry_delay(self, attempt: int, exc: Exception = None) -> float:
        """
        Calculate retry delay with exponential backoff.
        Respects Retry-After header on 429 responses.
        """
        # Check for Retry-After header
        retry_after = None
        if exc and hasattr(exc, 'response') and exc.response is not None:
            retry_after = exc.response.headers.get('Retry-After')
            if retry_after:
                try:
                    return float(retry_after)
                except (ValueError, TypeError):
                    pass

        # Exponential backoff with jitter: 2, 4, 8, 16...
        delay = self.DEFAULT_BASE_DELAY * (2 ** attempt)
        # Cap at 60 seconds
        return min(delay, 60.0)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send chat request with retry logic.

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Max token count
            response_format: Response format (e.g., JSON mode)

        Returns:
            Model response text
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # For Ollama: pass num_ctx via extra_body to prevent prompt truncation
        if self._is_ollama() and self._num_ctx:
            kwargs["extra_body"] = {
                "options": {"num_ctx": self._num_ctx}
            }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                # Some models include thinking content in response, remove it
                content = re.sub(r'<think[\s\S]*?</think\s*>', '', content).strip()
                return content

            except Exception as e:
                last_error = e

                if not self._should_retry(e):
                    logger.error(f"[LLM] Non-retryable error: {type(e).__name__}: {e}")
                    raise

                if attempt < self.max_retries:
                    delay = self._get_retry_delay(attempt, e)
                    logger.warning(
                        f"[LLM] Retryable error (attempt {attempt + 1}/{self.max_retries + 1}): "
                        f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[LLM] All {self.max_retries + 1} attempts failed. "
                        f"Last error: {type(e).__name__}: {e}"
                    )

        raise last_error

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send chat request and return JSON with retry logic.

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Max token count

        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # Clean markdown code block markers
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format from LLM: {cleaned_response}")
