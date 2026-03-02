"""
The Soul — LLM Client

Wraps the Anthropic API. Routes calls to the right model based on
which system is calling:

- Interviewer (user-facing generation) → Opus 4.6
- Cartographer (structured analysis)   → Opus 4.6
- Negotiation (agent-to-agent)         → Opus 4.6
- Messenger (reveal delivery)          → Opus 4.6

Using Opus across the board for maximum quality during development.
In production, Cartographer could drop to Haiku for cost optimization.
"""

import json
import os
from typing import Dict, List, Optional

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    Anthropic = None


# ─────────────────────────────────────────────
# MODEL ROUTING
# ─────────────────────────────────────────────

class ModelTier:
    # All Opus for now — best quality during prototyping
    INTERVIEWER = "claude-opus-4-6"
    CARTOGRAPHER = "claude-opus-4-6"
    NEGOTIATION = "claude-opus-4-6"
    MESSENGER = "claude-opus-4-6"

    # Future production config:
    # CARTOGRAPHER = "claude-haiku-4-5-20251001"  # Fast + cheap for JSON extraction
    # INTERVIEWER  = "claude-sonnet-4-5-20250929" # Balance of quality and cost
    # NEGOTIATION  = "claude-sonnet-4-5-20250929"
    # MESSENGER    = "claude-sonnet-4-5-20250929"


# ─────────────────────────────────────────────
# CLIENT
# ─────────────────────────────────────────────

class SoulLLMClient:
    """
    Unified LLM client for all Soul systems.
    Handles model routing, retries, and response parsing.
    """

    def __init__(self, api_key: Optional[str] = None):
        if not HAS_ANTHROPIC:
            raise ImportError(
                "The 'anthropic' package is required. Install with: pip install anthropic"
            )
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set in environment or passed directly."
            )
        self.client = Anthropic(api_key=self.api_key)

    # ── Core completion method ──

    def complete(
        self,
        system: str,
        messages: List[Dict[str, str]],
        model: str = ModelTier.INTERVIEWER,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a completion request to the Anthropic API.
        Returns the text content of the response.
        """
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        )

        # Extract text from response content blocks
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        return "\n".join(text_parts)

    # ── System-specific methods ──

    def interviewer_generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Generate the interviewer's response to the user.
        Uses highest quality model, moderate temperature for natural feel.
        """
        return self.complete(
            system=system,
            messages=messages,
            model=ModelTier.INTERVIEWER,
            max_tokens=512,       # Responses should be short — 1-4 sentences
            temperature=0.75,     # Slightly creative for natural conversation
        )

    def cartographer_analyze(
        self,
        system: str,
        analysis_input: Dict,
    ) -> Dict:
        """
        Run cartographer analysis on a user message.
        Returns parsed JSON with trait signals, emotional read, etc.
        
        Uses lower temperature for more consistent structured output.
        """
        response_text = self.complete(
            system=system,
            messages=[{
                "role": "user",
                "content": json.dumps(analysis_input, indent=2),
            }],
            model=ModelTier.CARTOGRAPHER,
            max_tokens=1024,
            temperature=0.3,      # Low temp for consistent JSON extraction
        )

        # Parse JSON from response — handle potential markdown wrapping
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # If parsing fails, return a safe default
            # In production, this should log and retry
            print(f"[CARTOGRAPHER WARNING] Failed to parse JSON response:")
            print(f"  Raw: {response_text[:200]}...")
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

    def negotiation_evaluate(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Agent-to-agent negotiation call.
        Reasoning-heavy — needs precision over creativity.
        """
        return self.complete(
            system=system,
            messages=messages,
            model=ModelTier.NEGOTIATION,
            max_tokens=2048,
            temperature=0.4,
        )

    def messenger_generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Generate the match reveal conversation.
        Warm and emotionally intelligent — needs creative nuance.
        """
        return self.complete(
            system=system,
            messages=messages,
            model=ModelTier.MESSENGER,
            max_tokens=1024,
            temperature=0.8,      # Higher temp for warmth and personality
        )
