"""
The Soul -- LLM Client (Ollama)

Wraps the Ollama async HTTP API at localhost:11434/api/chat.
Routes calls to the right model tier:

- Interviewer (user-facing generation)
- Cartographer (structured analysis)
- Mirror (soul persona builder)

All tiers default to the VIB_MODEL env var or qwen3.5:9b.
"""

import json
import os
from typing import Dict, List, Optional

import httpx


# ---------------------------------------------
# MODEL ROUTING
# ---------------------------------------------

class ModelTier:
    """Model assignments per system. Override via VIB_MODEL env var."""
    INTERVIEWER = os.environ.get("VIB_MODEL", "qwen3.5:9b")
    CARTOGRAPHER = os.environ.get("VIB_MODEL", "qwen3.5:9b")
    MIRROR = os.environ.get("VIB_MODEL", "qwen3.5:9b")
    VISION = os.environ.get("VIB_MODEL_VISION", "qwen2.5-vl:7b")


# ---------------------------------------------
# CLIENT
# ---------------------------------------------

class OllamaLLMClient:
    """
    Async LLM client that talks to a local Ollama instance.
    Handles model routing, JSON parsing, and response extraction.
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self._http = httpx.AsyncClient(base_url=base_url, timeout=180.0)

    async def close(self):
        """Close the underlying httpx client."""
        await self._http.aclose()

    # -- Core completion method --

    async def complete(
        self,
        system: str,
        messages: List[Dict[str, str]],
        model: str = ModelTier.INTERVIEWER,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        format_json: bool = False,
    ) -> str:
        """
        Send a chat completion request to Ollama's /api/chat endpoint.
        Returns the text content of the assistant's response.
        """
        payload: Dict = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if format_json:
            payload["format"] = "json"

        response = await self._http.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    # -- System-specific methods --

    async def interviewer_generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Generate the interviewer's response to the user.
        Moderate temperature for natural conversational feel.
        """
        return await self.complete(
            system=system,
            messages=messages,
            model=ModelTier.INTERVIEWER,
            max_tokens=256,
            temperature=0.75,
        )

    async def cartographer_analyze(
        self,
        system: str,
        analysis_input: Dict,
    ) -> Dict:
        """
        Run cartographer analysis on a user message.
        Returns parsed JSON with trait signals, emotional read, etc.
        Low temperature for consistent structured output.
        """
        messages = [{
            "role": "user",
            "content": json.dumps(analysis_input, indent=2),
        }]

        response_text = await self.complete(
            system=system,
            messages=messages,
            model=ModelTier.CARTOGRAPHER,
            max_tokens=512,
            temperature=0.3,
            format_json=True,
        )

        return self._parse_json_response(response_text)

    async def mirror_generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Generate the soul mirror / persona output.
        Higher temperature for warmth and creative nuance.
        """
        return await self.complete(
            system=system,
            messages=messages,
            model=ModelTier.MIRROR,
            max_tokens=256,
            temperature=0.8,
        )

    async def vision(
        self,
        prompt: str,
        image_b64: str,
        caption: Optional[str] = None,
    ) -> Dict:
        """
        Send an image to the vision model and get structured JSON back.
        Uses Ollama's image support in the chat API.
        """
        user_content = prompt
        if caption:
            user_content += f"\n\nUser's description: {caption}"

        messages = [{
            "role": "user",
            "content": user_content,
            "images": [image_b64],
        }]

        payload = {
            "model": ModelTier.VISION,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 512,
            },
            "format": "json",
        }

        response = await self._http.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return self._parse_json_response(data["message"]["content"])

    # -- JSON fallback chain --

    def _parse_json_response(self, text: str) -> Dict:
        """
        Parse JSON from LLM output with a multi-step fallback chain:
        1. Parse directly
        2. Strip markdown code blocks and parse
        3. Find first '{' and last '}' and parse that substring
        4. Return safe default dict
        """
        # Attempt 1: direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Attempt 2: strip markdown code fences
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass

        # Attempt 3: find first { and last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace : last_brace + 1])
            except (json.JSONDecodeError, TypeError):
                pass

        # Attempt 4: safe default
        return {
            "trait_signals": [],
            "emotional_read": {
                "temperature": "cool",
                "trend": "stable",
                "energy": 0.5,
            },
            "thread_updates": [],
            "contradiction_check": None,
            "unclassified": [],
        }


# Backward-compatible alias
SoulLLMClient = OllamaLLMClient
