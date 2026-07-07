"""Offline Ollama client for Praxis. Adapted from interviewer/llm_client.py,
wellness-specific methods removed. All calls hit local Ollama only."""
import json
import os
import httpx

DEFAULT_MODEL = os.environ.get("PRAXIS_MODEL", "qwen3.5:9b")


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = DEFAULT_MODEL):
        self.model = model
        self._http = httpx.AsyncClient(base_url=base_url, timeout=180.0)

    async def close(self):
        await self._http.aclose()

    async def complete(self, system, messages, max_tokens=512, temperature=0.7) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
            "think": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        r = await self._http.post("/api/chat", json=payload)
        r.raise_for_status()
        return r.json()["message"]["content"]

    async def complete_json(self, system, user, max_tokens=768, temperature=0.2) -> dict:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        r = await self._http.post("/api/chat", json=payload)
        r.raise_for_status()
        return self.parse_json(r.json()["message"]["content"])

    @staticmethod
    def parse_json(text: str) -> dict:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        cleaned = text.strip()
        for fence in ("```json", "```"):
            if cleaned.startswith(fence):
                cleaned = cleaned[len(fence):]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass
        if "{" in cleaned and "}" in cleaned:
            try:
                return json.loads(cleaned[cleaned.index("{"): cleaned.rindex("}") + 1])
            except (json.JSONDecodeError, TypeError):
                pass
        return {}
