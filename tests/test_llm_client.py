"""Tests for the Ollama-based LLM client.

Covers:
- ModelTier defaults and attributes
- OllamaLLMClient.complete() payload construction and response parsing
- cartographer_analyze() JSON parsing with fallback chain
- interviewer_generate() and mirror_generate() delegation
- SoulLLMClient backward-compatible alias
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# ModelTier
# ---------------------------------------------------------------------------

class TestModelTier:
    def test_defaults_contain_model_name(self):
        from interviewer.llm_client import ModelTier
        assert "qwen3.5" in ModelTier.INTERVIEWER
        assert "qwen3.5" in ModelTier.CARTOGRAPHER
        assert "qwen3.5" in ModelTier.MIRROR

    def test_all_tiers_defined(self):
        from interviewer.llm_client import ModelTier
        assert hasattr(ModelTier, "INTERVIEWER")
        assert hasattr(ModelTier, "CARTOGRAPHER")
        assert hasattr(ModelTier, "MIRROR")

    def test_env_override(self):
        """VIB_MODEL env var should override the default."""
        with patch.dict("os.environ", {"VIB_MODEL": "llama3:8b"}):
            import importlib
            import interviewer.llm_client as mod
            importlib.reload(mod)
            assert mod.ModelTier.INTERVIEWER == "llama3:8b"
            assert mod.ModelTier.CARTOGRAPHER == "llama3:8b"
            assert mod.ModelTier.MIRROR == "llama3:8b"
            importlib.reload(mod)


# ---------------------------------------------------------------------------
# Helpers for mocking httpx responses
# ---------------------------------------------------------------------------

def _make_httpx_response(content_text: str, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "model": "qwen3.5:9b",
        "message": {"role": "assistant", "content": content_text},
        "done": True,
    }
    return resp


# ---------------------------------------------------------------------------
# OllamaLLMClient.complete
# ---------------------------------------------------------------------------

class TestComplete:
    @pytest.mark.asyncio
    async def test_returns_text_content(self):
        from interviewer.llm_client import OllamaLLMClient
        mock_response = _make_httpx_response("Hello, world!")

        client = OllamaLLMClient()
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        result = await client.complete(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
            model="qwen3.5:9b",
        )
        assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self):
        from interviewer.llm_client import OllamaLLMClient
        mock_response = _make_httpx_response("ok")

        client = OllamaLLMClient()
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        await client.complete(
            system="Be concise.",
            messages=[{"role": "user", "content": "test"}],
            model="test-model",
            max_tokens=256,
            temperature=0.5,
        )

        client._http.post.assert_called_once()
        call_args = client._http.post.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
        assert "/api/chat" in str(url)

        payload = call_args.kwargs.get("json") or call_args.args[1]
        assert payload["model"] == "test-model"
        assert payload["stream"] is False
        assert payload["options"]["temperature"] == 0.5
        assert payload["options"]["num_predict"] == 256
        assert payload["messages"][0]["role"] == "system"


# ---------------------------------------------------------------------------
# cartographer_analyze -- JSON fallback chain
# ---------------------------------------------------------------------------

class TestCartographerAnalyze:
    @pytest.mark.asyncio
    async def test_parses_valid_json(self):
        from interviewer.llm_client import OllamaLLMClient
        valid_json = json.dumps({
            "trait_signals": [{"dimension": "openness", "signal": "high"}],
            "emotional_read": {"temperature": "warm"},
            "thread_updates": [],
            "contradiction_check": None,
            "unclassified": [],
        })
        mock_response = _make_httpx_response(valid_json)

        client = OllamaLLMClient()
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        result = await client.cartographer_analyze(
            system="Analyze.",
            analysis_input={"user_message": "I love hiking"},
        )
        assert isinstance(result, dict)
        assert result["trait_signals"][0]["dimension"] == "openness"

    @pytest.mark.asyncio
    async def test_returns_safe_default_on_garbage(self):
        from interviewer.llm_client import OllamaLLMClient
        mock_response = _make_httpx_response("This is not JSON at all!")

        client = OllamaLLMClient()
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        result = await client.cartographer_analyze(
            system="Analyze.",
            analysis_input={"user_message": "garbage"},
        )
        assert isinstance(result, dict)
        assert result["trait_signals"] == []


# ---------------------------------------------------------------------------
# interviewer_generate and mirror_generate delegation
# ---------------------------------------------------------------------------

class TestInterviewerGenerate:
    @pytest.mark.asyncio
    async def test_calls_complete(self):
        from interviewer.llm_client import OllamaLLMClient, ModelTier
        client = OllamaLLMClient()
        client.complete = AsyncMock(return_value="That's honest.")

        result = await client.interviewer_generate(
            system="You are the interviewer.",
            messages=[{"role": "user", "content": "I moved recently."}],
        )
        assert result == "That's honest."
        client.complete.assert_called_once_with(
            system="You are the interviewer.",
            messages=[{"role": "user", "content": "I moved recently."}],
            model=ModelTier.INTERVIEWER,
            max_tokens=256,
            temperature=0.75,
        )


class TestMirrorGenerate:
    @pytest.mark.asyncio
    async def test_calls_complete(self):
        from interviewer.llm_client import OllamaLLMClient, ModelTier
        client = OllamaLLMClient()
        client.complete = AsyncMock(return_value="Yeah, that sounds like me.")

        result = await client.mirror_generate(
            system="You are their soul.",
            messages=[{"role": "user", "content": "What do you think?"}],
        )
        assert result == "Yeah, that sounds like me."
        client.complete.assert_called_once_with(
            system="You are their soul.",
            messages=[{"role": "user", "content": "What do you think?"}],
            model=ModelTier.MIRROR,
            max_tokens=256,
            temperature=0.8,
        )


# ---------------------------------------------------------------------------
# _parse_json_response unit tests
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    def test_direct_parse(self):
        from interviewer.llm_client import OllamaLLMClient
        client = OllamaLLMClient.__new__(OllamaLLMClient)
        data = {"key": "value"}
        assert client._parse_json_response(json.dumps(data)) == data

    def test_garbage_returns_safe_default(self):
        from interviewer.llm_client import OllamaLLMClient
        client = OllamaLLMClient.__new__(OllamaLLMClient)
        result = client._parse_json_response("no json here")
        assert isinstance(result, dict)
        assert result["trait_signals"] == []


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

class TestBackwardAlias:
    def test_soul_llm_client_is_ollama_client(self):
        from interviewer.llm_client import SoulLLMClient, OllamaLLMClient
        assert SoulLLMClient is OllamaLLMClient


# ---------------------------------------------------------------------------
# close() method
# ---------------------------------------------------------------------------

class TestClose:
    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from interviewer.llm_client import OllamaLLMClient
        client = OllamaLLMClient()
        client._http = AsyncMock()
        client._http.aclose = AsyncMock()

        await client.close()
        client._http.aclose.assert_called_once()
