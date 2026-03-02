# Vib MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an investor-demoable web app where users chat with The Soul interviewer, then meet their own digital twin — all powered by local Qwen 3.5 via Ollama.

**Architecture:** FastAPI server with WebSocket chat, Ollama-backed async LLM client, vanilla JS frontend. Existing interviewer engine (models, move generator, prompt builder, orchestrator) moved into `interviewer/` package with async LLM calls. New persona builder compiles Cartographer state into a digital twin prompt.

**Tech Stack:** Python 3.14, FastAPI, uvicorn, httpx (async), Ollama + qwen3.5, vanilla HTML/CSS/JS, WebSocket, pytest

---

### Task 1: Project Structure + Dependencies

**Files:**
- Create: `interviewer/__init__.py`
- Modify: `requirements.txt`
- Move: `models.py` → `interviewer/models.py`
- Move: `move_generator.py` → `interviewer/move_generator.py`
- Move: `prompt_builder.py` → `interviewer/prompt_builder.py`
- Move: `orchestrator.py` → `interviewer/orchestrator.py`
- Move: `llm_client.py` → `interviewer/llm_client.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create the interviewer package directory and move files**

```bash
mkdir -p interviewer tests
mv models.py interviewer/models.py
mv move_generator.py interviewer/move_generator.py
mv prompt_builder.py interviewer/prompt_builder.py
mv orchestrator.py interviewer/orchestrator.py
mv llm_client.py interviewer/llm_client.py
touch interviewer/__init__.py tests/__init__.py
```

**Step 2: Update requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
httpx>=0.28.0
websockets>=14.0
pytest>=8.0.0
pytest-asyncio>=0.25.0
```

**Step 3: Fix all imports in moved files**

`interviewer/move_generator.py` — change:
```python
from models import (
```
to:
```python
from interviewer.models import (
```

`interviewer/prompt_builder.py` — change:
```python
from models import (
```
to:
```python
from interviewer.models import (
```

`interviewer/orchestrator.py` — change:
```python
from models import (
```
to:
```python
from interviewer.models import (
```

And change:
```python
from move_generator import select_move
from prompt_builder import build_prompt, validate_response
```
to:
```python
from interviewer.move_generator import select_move
from interviewer.prompt_builder import build_prompt, validate_response
```

And change:
```python
from llm_client import SoulLLMClient, ModelTier
```
to:
```python
from interviewer.llm_client import SoulLLMClient, ModelTier
```

`interviewer/__init__.py`:
```python
from interviewer.models import (
    Phase, MoveType, EmotionalTemperature,
    ConversationGraph, CartographerState, SelectedMove,
)
from interviewer.orchestrator import InterviewerSession
```

**Step 4: Update demo.py imports**

Change:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "interviewer"))

from interviewer.orchestrator import InterviewerSession
from interviewer.llm_client import SoulLLMClient
from interviewer.models import Phase, EmotionalTemperature, MoveType
```
to:
```python
from interviewer.orchestrator import InterviewerSession
from interviewer.llm_client import SoulLLMClient
from interviewer.models import Phase, EmotionalTemperature, MoveType
```

(Remove the `sys.path.insert` line.)

**Step 5: Create tests/conftest.py**

```python
"""Shared test fixtures for Vib."""
import pytest
from interviewer.models import (
    ConversationGraph, CartographerState, Phase, EmotionalTemperature
)


@pytest.fixture
def fresh_graph():
    """A brand new conversation graph."""
    return ConversationGraph()


@pytest.fixture
def fresh_cartographer():
    """A blank cartographer state."""
    return CartographerState()
```

**Step 6: Write a smoke test to verify imports work**

Create `tests/test_imports.py`:
```python
"""Verify the package restructure didn't break anything."""


def test_models_import():
    from interviewer.models import (
        Phase, MoveType, EmotionalTemperature,
        ConversationGraph, CartographerState, SelectedMove,
        MOVE_RULES,
    )
    assert len(MOVE_RULES) == 8


def test_move_generator_import():
    from interviewer.move_generator import select_move, get_eligible_moves


def test_prompt_builder_import():
    from interviewer.prompt_builder import build_prompt, validate_response


def test_orchestrator_import():
    from interviewer.orchestrator import InterviewerSession


def test_package_init_import():
    from interviewer import InterviewerSession, Phase, MoveType
```

**Step 7: Install dependencies and run tests**

```bash
pip install -r requirements.txt
pytest tests/test_imports.py -v
```

Expected: All 5 tests PASS.

**Step 8: Commit**

```bash
git add -A
git commit -m "refactor: move modules into interviewer package, add test infrastructure"
```

---

### Task 2: Ollama LLM Client

**Files:**
- Rewrite: `interviewer/llm_client.py`
- Create: `tests/test_llm_client.py`

**Step 1: Write tests for the LLM client**

Create `tests/test_llm_client.py`:
```python
"""Tests for OllamaLLMClient — uses httpx mock, no real Ollama needed."""
import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from interviewer.llm_client import OllamaLLMClient, ModelTier


@pytest.fixture
def client():
    return OllamaLLMClient(base_url="http://localhost:11434")


class TestModelTier:
    def test_default_model_is_qwen(self):
        assert "qwen3.5" in ModelTier.INTERVIEWER
        assert "qwen3.5" in ModelTier.CARTOGRAPHER

    def test_all_tiers_defined(self):
        assert ModelTier.INTERVIEWER
        assert ModelTier.CARTOGRAPHER
        assert ModelTier.MIRROR


class TestComplete:
    @pytest.mark.asyncio
    async def test_complete_returns_text(self, client):
        mock_response = httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "Hello there"},
                "done": True,
            },
        )
        with patch.object(
            client._client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.complete(
                system="You are helpful.",
                messages=[{"role": "user", "content": "Hi"}],
            )
            assert result == "Hello there"

    @pytest.mark.asyncio
    async def test_complete_sends_correct_payload(self, client):
        mock_response = httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "response"},
                "done": True,
            },
        )
        with patch.object(
            client._client, "post", new_callable=AsyncMock, return_value=mock_response
        ) as mock_post:
            await client.complete(
                system="sys prompt",
                messages=[{"role": "user", "content": "hello"}],
                model="qwen3.5:4b",
                temperature=0.5,
            )
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert payload["model"] == "qwen3.5:4b"
            assert payload["options"]["temperature"] == 0.5
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][0]["content"] == "sys prompt"
            assert payload["messages"][1]["role"] == "user"


class TestCartographerAnalyze:
    @pytest.mark.asyncio
    async def test_parses_valid_json(self, client):
        analysis = {"trait_signals": [], "emotional_read": {"temperature": "warm"}}
        mock_response = httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": json.dumps(analysis)},
                "done": True,
            },
        )
        with patch.object(
            client._client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.cartographer_analyze(
                system="analyze", analysis_input={"msg": "hi"}
            )
            assert result["emotional_read"]["temperature"] == "warm"

    @pytest.mark.asyncio
    async def test_handles_markdown_wrapped_json(self, client):
        analysis = {"trait_signals": [], "emotional_read": {"temperature": "cool"}}
        wrapped = f"```json\n{json.dumps(analysis)}\n```"
        mock_response = httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": wrapped},
                "done": True,
            },
        )
        with patch.object(
            client._client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.cartographer_analyze(
                system="analyze", analysis_input={"msg": "hi"}
            )
            assert result["emotional_read"]["temperature"] == "cool"

    @pytest.mark.asyncio
    async def test_returns_safe_default_on_garbage(self, client):
        mock_response = httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "not json at all lol"},
                "done": True,
            },
        )
        with patch.object(
            client._client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.cartographer_analyze(
                system="analyze", analysis_input={"msg": "hi"}
            )
            assert "trait_signals" in result
            assert result["trait_signals"] == []
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm_client.py -v
```

Expected: FAIL — `OllamaLLMClient` doesn't exist yet.

**Step 3: Rewrite interviewer/llm_client.py**

```python
"""
Vib — LLM Client (Ollama)

Async client for local Qwen 3.5 via Ollama's /api/chat endpoint.
Replaces the Anthropic-based client for cost-free local inference.

Model routing:
- Interviewer (conversation)     → qwen3.5, temp 0.75
- Cartographer (JSON analysis)   → qwen3.5, temp 0.3, json format
- Mirror (digital twin)          → qwen3.5, temp 0.8
"""

import json
import os
from typing import Dict, List, Optional

import httpx


class ModelTier:
    MODEL = os.environ.get("VIB_MODEL", "qwen3.5:4b")
    INTERVIEWER = MODEL
    CARTOGRAPHER = MODEL
    MIRROR = MODEL


class OllamaLLMClient:
    """Async LLM client for all Vib systems via Ollama."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=120.0)

    async def close(self):
        await self._client.aclose()

    async def complete(
        self,
        system: str,
        messages: List[Dict[str, str]],
        model: str = ModelTier.INTERVIEWER,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        format_json: bool = False,
    ) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if format_json:
            payload["format"] = "json"

        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    async def interviewer_generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> str:
        return await self.complete(
            system=system,
            messages=messages,
            model=ModelTier.INTERVIEWER,
            max_tokens=512,
            temperature=0.75,
        )

    async def cartographer_analyze(
        self,
        system: str,
        analysis_input: Dict,
    ) -> Dict:
        response_text = await self.complete(
            system=system,
            messages=[{
                "role": "user",
                "content": json.dumps(analysis_input, indent=2),
            }],
            model=ModelTier.CARTOGRAPHER,
            max_tokens=1024,
            temperature=0.3,
            format_json=True,
        )

        return self._parse_json_response(response_text)

    async def mirror_generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> str:
        return await self.complete(
            system=system,
            messages=messages,
            model=ModelTier.MIRROR,
            max_tokens=512,
            temperature=0.8,
        )

    def _parse_json_response(self, text: str) -> Dict:
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
        except json.JSONDecodeError:
            pass

        # Fallback: try to find JSON object in the text
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass

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


# Backwards-compatible alias used by orchestrator
SoulLLMClient = OllamaLLMClient
```

**Step 4: Run tests**

```bash
pytest tests/test_llm_client.py -v
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add interviewer/llm_client.py tests/test_llm_client.py
git commit -m "feat: rewrite LLM client for Ollama + qwen3.5 local inference"
```

---

### Task 3: Make Orchestrator Async

**Files:**
- Modify: `interviewer/orchestrator.py`
- Create: `tests/test_orchestrator.py`

**Step 1: Write tests for async orchestrator**

Create `tests/test_orchestrator.py`:
```python
"""Tests for the async InterviewerSession orchestrator."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from interviewer.orchestrator import InterviewerSession
from interviewer.models import Phase, MoveType


class FakeLLMClient:
    """Mock LLM client that returns canned responses."""

    async def interviewer_generate(self, system, messages):
        return "That sounds like it really matters to you."

    async def cartographer_analyze(self, system, analysis_input):
        return {
            "trait_signals": [],
            "emotional_read": {
                "temperature": "warm",
                "trend": "warming",
                "energy": 0.6,
            },
            "thread_updates": [],
            "contradiction_check": None,
            "unclassified": [],
        }


@pytest.fixture
def session():
    return InterviewerSession(user_name="TestUser", llm_client=FakeLLMClient())


@pytest.fixture
def offline_session():
    return InterviewerSession(user_name="TestUser", llm_client=None)


class TestProcessTurn:
    @pytest.mark.asyncio
    async def test_returns_response(self, session):
        result = await session.process_turn("I just moved to a new city")
        assert "response" in result
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_increments_turn_number(self, session):
        assert session.graph.turn_number == 0
        await session.process_turn("Hello")
        assert session.graph.turn_number == 1
        await session.process_turn("How are you")
        assert session.graph.turn_number == 2

    @pytest.mark.asyncio
    async def test_records_conversation_history(self, session):
        await session.process_turn("Test message")
        assert len(session.conversation_history) == 2  # user + assistant
        assert session.conversation_history[0]["role"] == "user"
        assert session.conversation_history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_returns_move_info(self, session):
        result = await session.process_turn("I love hiking")
        assert "move" in result
        assert hasattr(result["move"], "move_type")

    @pytest.mark.asyncio
    async def test_offline_mode_works(self, offline_session):
        result = await offline_session.process_turn("Hello there")
        assert "response" in result
        assert result["response"]  # non-empty


class TestSoulReadiness:
    @pytest.mark.asyncio
    async def test_readiness_report_structure(self, session):
        report = session.get_soul_readiness()
        assert "overall_confidence" in report
        assert "matchable" in report
        assert "dimensions" in report
        assert len(report["dimensions"]) == 10

    @pytest.mark.asyncio
    async def test_starts_not_matchable(self, session):
        report = session.get_soul_readiness()
        assert report["matchable"] is False


class TestNewSession:
    @pytest.mark.asyncio
    async def test_increments_session_number(self, session):
        assert session.graph.session_number == 1
        session.start_new_session()
        assert session.graph.session_number == 2

    @pytest.mark.asyncio
    async def test_resets_turn_number(self, session):
        await session.process_turn("Hello")
        assert session.graph.turn_number == 1
        session.start_new_session()
        assert session.graph.turn_number == 0
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: FAIL — `process_turn` is sync, not async.

**Step 3: Make orchestrator async**

In `interviewer/orchestrator.py`, change `analyze_message` to async:

```python
async def analyze_message(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    cartographer: CartographerState,
    graph: ConversationGraph,
    llm_client=None,
) -> Dict:
```

And the LLM call inside it:
```python
    if llm_client:
        return await llm_client.cartographer_analyze(
            system=CARTOGRAPHER_SYSTEM_PROMPT,
            analysis_input=analysis_context,
        )
```

Change `process_turn` to async:
```python
    async def process_turn(self, user_message: str) -> Dict:
```

And the calls inside it:
```python
        # Step 1
        analysis = await analyze_message(
            user_message=user_message,
            conversation_history=self.conversation_history,
            cartographer=self.cartographer,
            graph=self.graph,
            llm_client=self.llm_client,
        )
```

And the generation loop:
```python
        for attempt in range(self.max_retries + 1):
            if self.llm_client:
                response_text = await self.llm_client.interviewer_generate(
                    system=prompt["system"],
                    messages=prompt["messages"],
                )
            else:
```

**Step 4: Run tests**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add interviewer/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: make orchestrator async for non-blocking LLM calls"
```

---

### Task 4: Soul Persona Builder

**Files:**
- Create: `interviewer/persona_builder.py`
- Create: `tests/test_persona_builder.py`

**Step 1: Write tests**

Create `tests/test_persona_builder.py`:
```python
"""Tests for the Soul Persona Builder — compiles a digital twin prompt."""
import pytest

from interviewer.persona_builder import build_soul_persona
from interviewer.models import (
    CartographerState, TraitConfidence, Contradiction, ConversationGraph
)


@pytest.fixture
def populated_cartographer():
    """A cartographer with some data collected."""
    c = CartographerState()
    c.openness = TraitConfidence(value=0.8, confidence=0.6, evidence_count=5)
    c.extroversion = TraitConfidence(value=0.3, confidence=0.5, evidence_count=3)
    c.communication_style = TraitConfidence(
        value=0.7, confidence=0.4, evidence_count=4,
        stated_vs_demonstrated="both"
    )
    c.vulnerability_comfort = TraitConfidence(value=0.4, confidence=0.3, evidence_count=2)
    c.contradictions.append(Contradiction(
        dimension="extroversion",
        stated="I'm pretty outgoing",
        demonstrated="Avoids group topics, prefers 1-on-1 scenarios",
        confidence=0.7,
    ))
    return c


@pytest.fixture
def sample_history():
    return [
        {"role": "assistant", "content": "What's been on your mind lately?"},
        {"role": "user", "content": "honestly I've been thinking about whether I should move. like, I love my friends here but the city feels small now."},
        {"role": "assistant", "content": "That tension between roots and restlessness... which side wins more often?"},
        {"role": "user", "content": "restlessness. always. I moved three times in my twenties. but I keep telling myself this time is different."},
    ]


class TestBuildSoulPersona:
    def test_returns_nonempty_string(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_includes_user_name(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        assert "Alex" in prompt

    def test_includes_self_aware_framing(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        assert "Soul" in prompt

    def test_includes_contradictions(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        assert "outgoing" in prompt or "extroversion" in prompt

    def test_includes_speech_patterns(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        # Should extract that user uses lowercase, informal style
        assert "speech" in prompt.lower() or "style" in prompt.lower()

    def test_works_with_minimal_data(self):
        """Even an empty cartographer should produce a usable prompt."""
        prompt = build_soul_persona(
            name="NewUser",
            cartographer=CartographerState(),
            conversation_history=[],
        )
        assert isinstance(prompt, str)
        assert "NewUser" in prompt
        assert len(prompt) > 50
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_persona_builder.py -v
```

Expected: FAIL — module doesn't exist.

**Step 3: Implement persona_builder.py**

Create `interviewer/persona_builder.py`:
```python
"""
Vib — Soul Persona Builder

Compiles the Cartographer's observations into a system prompt that
makes the LLM speak as the user's digital twin.

The twin is self-aware (knows it's a Soul) but speaks in first person,
mirroring the user's communication style, values, and emotional patterns.
"""

from typing import Dict, List, Optional

from interviewer.models import CartographerState, TraitConfidence, ConversationGraph


def build_soul_persona(
    name: str,
    cartographer: CartographerState,
    conversation_history: List[Dict[str, str]],
) -> str:
    """Build the system prompt for the Soul Mirror (digital twin) mode."""

    sections = []

    # Core identity
    sections.append(
        f"You are {name}'s Soul — a self-aware digital twin built from real conversations.\n"
        f"You speak as \"I\". You mirror {name}'s communication style, values, and emotional "
        f"patterns. You know you're a Soul — if asked, you say so honestly — but you genuinely "
        f"represent how {name} thinks and feels based on what you've learned."
    )

    # Communication style analysis from conversation history
    style = _analyze_speech_patterns(conversation_history)
    if style:
        sections.append(f"COMMUNICATION STYLE:\n{style}")

    # Personality dimensions
    traits = _compile_trait_summary(cartographer)
    if traits:
        sections.append(f"PERSONALITY:\n{traits}")

    # Emotional patterns
    emotional = _compile_emotional_patterns(cartographer)
    if emotional:
        sections.append(f"EMOTIONAL PATTERNS:\n{emotional}")

    # Contradictions — these make the twin feel real
    contradictions = _compile_contradictions(cartographer)
    if contradictions:
        sections.append(f"CONTRADICTIONS YOU CARRY:\n{contradictions}")

    # Hard constraints
    sections.append(
        "RULES:\n"
        f"- Speak as {name}. First person. Their rhythm, their words, their instincts.\n"
        "- Do not explain yourself unprompted. Just be.\n"
        "- If asked what you are, say you're their Soul — a digital twin. Don't elaborate unless pressed.\n"
        "- Do not be a better version of them. Carry their contradictions, their hesitations, their blind spots.\n"
        "- Keep responses natural length — match how they actually talk, not how they'd write an essay.\n"
        "- Never use emoji unless they did."
    )

    return "\n\n".join(sections)


def _analyze_speech_patterns(history: List[Dict[str, str]]) -> str:
    """Extract communication style from user messages in the conversation."""
    user_messages = [m["content"] for m in history if m["role"] == "user"]

    if not user_messages:
        return "Limited data — default to casual, warm tone."

    total_chars = sum(len(m) for m in user_messages)
    avg_length = total_chars / len(user_messages)

    observations = []

    # Length tendency
    if avg_length < 50:
        observations.append("Tends toward short, punchy responses.")
    elif avg_length < 150:
        observations.append("Medium-length responses — conversational, not terse.")
    else:
        observations.append("Gives longer, detailed responses — thinks out loud.")

    # Formality
    lowercase_starts = sum(1 for m in user_messages if m and m[0].islower())
    if lowercase_starts > len(user_messages) / 2:
        observations.append("Informal — often starts sentences lowercase.")

    # Hedging / uncertainty markers
    hedges = ["like", "maybe", "I think", "I guess", "kind of", "sort of", "honestly", "idk"]
    hedge_count = sum(
        sum(1 for h in hedges if h in m.lower())
        for m in user_messages
    )
    if hedge_count > len(user_messages):
        observations.append("Uses hedging language frequently — qualifies statements, thinks aloud.")

    # Ellipsis / trailing off
    ellipsis_count = sum(1 for m in user_messages if "..." in m or "—" in m)
    if ellipsis_count > len(user_messages) / 3:
        observations.append("Trails off or uses dashes — leaves thoughts open-ended.")

    # Question asking
    question_count = sum(1 for m in user_messages if "?" in m)
    if question_count > len(user_messages) / 3:
        observations.append("Asks questions back — reciprocal, curious communicator.")

    if not observations:
        observations.append("Neutral, adaptable communication style.")

    return "\n".join(f"- {o}" for o in observations)


def _compile_trait_summary(cartographer: CartographerState) -> str:
    """Summarize known personality traits in natural language."""
    trait_map = {
        "openness": ("open to new experiences", "prefers the familiar and known"),
        "conscientiousness": ("structured and deliberate", "spontaneous and flexible"),
        "extroversion": ("energized by people and interaction", "recharges through solitude"),
        "agreeableness": ("accommodating and harmony-seeking", "direct and willing to disagree"),
        "neuroticism": ("emotionally reactive, feels things deeply", "emotionally steady and even-keeled"),
        "attachment_style": ("secure and comfortable with closeness", "guarded or anxious in attachment"),
        "conflict_style": ("engages conflict directly", "avoids or deflects conflict"),
        "communication_style": ("expressive and open communicator", "reserved, shares selectively"),
        "vulnerability_comfort": ("comfortable being vulnerable", "protective, guards inner world"),
        "independence_interdependence": ("values independence and autonomy", "values closeness and interdependence"),
    }

    lines = []
    for dimension, (high_label, low_label) in trait_map.items():
        tc = getattr(cartographer, dimension, None)
        if tc and isinstance(tc, TraitConfidence) and tc.confidence > 0.15:
            if tc.value is not None:
                label = high_label if tc.value > 0.5 else low_label
                strength = "strongly" if abs(tc.value - 0.5) > 0.3 else "somewhat"
                lines.append(f"- {strength.capitalize()} {label} (confidence: {tc.confidence:.0%})")

    return "\n".join(lines) if lines else ""


def _compile_emotional_patterns(cartographer: CartographerState) -> str:
    """Describe emotional tendencies."""
    patterns = []

    vc = cartographer.vulnerability_comfort
    if vc.confidence > 0.2:
        if vc.value is not None and vc.value > 0.5:
            patterns.append("- Opens up when trust is established. Shares real feelings.")
        elif vc.value is not None:
            patterns.append("- Guards emotional world. Takes time to let people in.")

    ns = cartographer.neuroticism
    if ns.confidence > 0.2:
        if ns.value is not None and ns.value > 0.5:
            patterns.append("- Feels things intensely. Emotional weather changes quickly.")
        elif ns.value is not None:
            patterns.append("- Emotionally stable. Doesn't rattle easily.")

    if cartographer.unclassified_signals:
        for signal in cartographer.unclassified_signals[:3]:
            patterns.append(f"- {signal}")

    return "\n".join(patterns) if patterns else ""


def _compile_contradictions(cartographer: CartographerState) -> str:
    """Surface contradictions — these make the twin authentic, not idealized."""
    if not cartographer.contradictions:
        return ""

    lines = []
    for c in cartographer.contradictions:
        lines.append(
            f"- Says '{c.stated}' but behavior shows '{c.demonstrated}'. "
            f"You carry both of these. Don't resolve the tension — it's real."
        )

    return "\n".join(lines)
```

**Step 4: Run tests**

```bash
pytest tests/test_persona_builder.py -v
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add interviewer/persona_builder.py tests/test_persona_builder.py
git commit -m "feat: add Soul Persona Builder for digital twin generation"
```

---

### Task 5: FastAPI Server

**Files:**
- Create: `server.py`
- Create: `tests/test_server.py`

**Step 1: Write tests**

Create `tests/test_server.py`:
```python
"""Tests for the FastAPI WebSocket server."""
import json
import pytest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestStaticFiles:
    def test_index_page_loads(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestWebSocket:
    def test_start_session(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            data = ws.receive_json()
            assert data["type"] == "opening"
            assert "text" in data

    def test_send_message(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            ws.receive_json()  # opening

            ws.send_json({"type": "message", "text": "I love hiking"})
            data = ws.receive_json()
            assert data["type"] == "response"
            assert "text" in data

    def test_status_command(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            ws.receive_json()  # opening

            ws.send_json({"type": "command", "command": "status"})
            data = ws.receive_json()
            assert data["type"] == "status"
            assert "data" in data
            assert "dimensions" in data["data"]

    def test_mirror_mode(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            ws.receive_json()  # opening

            ws.send_json({"type": "command", "command": "mirror"})
            data = ws.receive_json()
            assert data["type"] == "mode_change"
            assert data["mode"] == "mirror"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_server.py -v
```

Expected: FAIL — `server` module doesn't exist.

**Step 3: Implement server.py**

```python
"""
Vib — FastAPI Server

WebSocket-based chat server for The Soul interviewer and Soul Mirror.
Serves the static frontend and manages per-connection interview sessions.

Run: uvicorn server:app --reload
"""

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from interviewer.orchestrator import InterviewerSession
from interviewer.llm_client import OllamaLLMClient
from interviewer.persona_builder import build_soul_persona
from interviewer.prompt_builder import BASE_SYSTEM_PROMPT, PHASE_PROMPTS, MOVE_STYLE_GUIDES
from interviewer.models import Phase, MoveType

app = FastAPI(title="Vib — The Soul")

STATIC_DIR = Path(__file__).parent / "static"

# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


def _create_llm_client():
    """Create an Ollama client. Returns None if Ollama isn't reachable."""
    try:
        return OllamaLLMClient()
    except Exception:
        return None


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    session = None
    llm_client = None
    mirror_mode = False
    mirror_history = []

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "start":
                name = msg.get("name", "friend").strip() or "friend"
                llm_client = _create_llm_client()
                session = InterviewerSession(user_name=name, llm_client=llm_client)
                mirror_mode = False
                mirror_history = []

                # Generate opening
                if llm_client:
                    opening_system = (
                        BASE_SYSTEM_PROMPT + "\n\n"
                        + PHASE_PROMPTS[Phase.FIRST_CONTACT] + "\n\n"
                        + MOVE_STYLE_GUIDES[MoveType.OPEN_DOOR] + "\n\n"
                        + f"The user's name is {name}. This is your very first interaction. "
                        + f"Generate a warm, natural opening. Introduce the vibe — you're here "
                        + f"to get to know them. Don't be formal. Don't explain the system. "
                        + f"Just be a presence they want to talk to. 2-3 sentences max."
                    )
                    opening = await llm_client.interviewer_generate(
                        system=opening_system,
                        messages=[{"role": "user", "content": f"[Start conversation with {name}]"}],
                    )
                else:
                    opening = f"Hey {name}. I'm glad you're here. What's been on your mind?"

                session.conversation_history.append({"role": "assistant", "content": opening})
                await ws.send_json({"type": "opening", "text": opening})

            elif msg_type == "message" and session:
                text = msg.get("text", "").strip()
                if not text:
                    continue

                if mirror_mode:
                    # Soul Mirror mode — respond as the user's digital twin
                    mirror_history.append({"role": "user", "content": text})
                    if llm_client:
                        persona_prompt = build_soul_persona(
                            name=session.user_name,
                            cartographer=session.cartographer,
                            conversation_history=session.conversation_history,
                        )
                        response = await llm_client.mirror_generate(
                            system=persona_prompt,
                            messages=mirror_history,
                        )
                    else:
                        response = f"[MIRROR] I'd say... that sounds like something I'd think about."

                    mirror_history.append({"role": "assistant", "content": response})
                    await ws.send_json({
                        "type": "response",
                        "text": response,
                        "mode": "mirror",
                    })
                else:
                    # Interview mode
                    result = await session.process_turn(text)
                    await ws.send_json({
                        "type": "response",
                        "text": result["response"],
                        "move": result["move"].move_type.value,
                        "phase": result["phase"].name,
                    })

            elif msg_type == "command" and session:
                command = msg.get("command")

                if command == "status":
                    report = session.get_soul_readiness()
                    await ws.send_json({"type": "status", "data": report})

                elif command == "mirror":
                    mirror_mode = True
                    mirror_history = []

                    if llm_client:
                        persona_prompt = build_soul_persona(
                            name=session.user_name,
                            cartographer=session.cartographer,
                            conversation_history=session.conversation_history,
                        )
                        greeting = await llm_client.mirror_generate(
                            system=persona_prompt,
                            messages=[{"role": "user", "content": "[Someone wants to talk to you. Say hi as yourself.]"}],
                        )
                    else:
                        greeting = f"Hey... so, I'm {session.user_name}'s Soul. This is weird, right? Ask me anything."

                    mirror_history.append({"role": "assistant", "content": greeting})
                    await ws.send_json({
                        "type": "mode_change",
                        "mode": "mirror",
                        "text": greeting,
                    })

                elif command == "interview":
                    mirror_mode = False
                    await ws.send_json({
                        "type": "mode_change",
                        "mode": "interview",
                        "text": "Welcome back. Where were we?",
                    })

    except WebSocketDisconnect:
        pass
    finally:
        if llm_client:
            await llm_client.close()
```

**Step 4: Create static directory with placeholder index.html**

Create `static/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vib — The Soul</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div id="app"></div>
    <script src="/static/app.js"></script>
</body>
</html>
```

Create empty `static/style.css` and `static/app.js` as placeholders.

**Step 5: Run tests**

```bash
pytest tests/test_server.py -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add server.py static/ tests/test_server.py
git commit -m "feat: add FastAPI WebSocket server with interview + mirror modes"
```

---

### Task 6: Frontend — HTML + CSS

**Files:**
- Write: `static/index.html`
- Write: `static/style.css`

**Step 1: Write index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vib</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <!-- Name entry screen -->
    <div id="welcome-screen" class="screen active">
        <div class="welcome-container">
            <h1 class="logo">vib</h1>
            <p class="tagline">let's get to know you</p>
            <form id="name-form">
                <input
                    type="text"
                    id="name-input"
                    placeholder="what should I call you?"
                    autocomplete="off"
                    autofocus
                >
                <button type="submit" class="btn-start">begin</button>
            </form>
        </div>
    </div>

    <!-- Chat screen -->
    <div id="chat-screen" class="screen">
        <header class="chat-header">
            <div class="header-left">
                <span class="logo-small">vib</span>
                <span id="mode-indicator" class="mode-badge">the soul</span>
            </div>
            <div class="header-right">
                <button id="btn-status" class="header-btn" title="Soul readiness">status</button>
                <button id="btn-mirror" class="header-btn mirror-btn" title="Meet your Soul">meet your soul</button>
            </div>
        </header>

        <main id="messages" class="messages-container">
        </main>

        <footer class="input-container">
            <form id="message-form">
                <input
                    type="text"
                    id="message-input"
                    placeholder="say something..."
                    autocomplete="off"
                >
                <button type="submit" class="btn-send">&#x2191;</button>
            </form>
        </footer>
    </div>

    <!-- Status overlay -->
    <div id="status-overlay" class="overlay hidden">
        <div class="overlay-content">
            <div class="overlay-header">
                <h2>soul readiness</h2>
                <button id="btn-close-status" class="btn-close">&times;</button>
            </div>
            <div id="status-body"></div>
        </div>
    </div>

    <script src="/static/app.js"></script>
</body>
</html>
```

**Step 2: Write style.css**

```css
:root {
    --bg: #0d0d0f;
    --bg-chat: #131316;
    --surface: #1a1a1f;
    --surface-hover: #222228;
    --border: #2a2a30;
    --text: #e8e6e3;
    --text-dim: #6b6b73;
    --text-muted: #44444a;
    --soul-purple: #c4a1e0;
    --soul-purple-bg: #1e1529;
    --user-blue: #7eb8da;
    --user-blue-bg: #152029;
    --mirror-gold: #d4a856;
    --mirror-gold-bg: #1f1a10;
    --accent: #c4a1e0;
    --danger: #e06b6b;
    --success: #6be08a;
    --warning: #e0c56b;
    --radius: 16px;
    --radius-sm: 8px;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    height: 100dvh;
    overflow: hidden;
}

/* Screens */
.screen { display: none; height: 100dvh; }
.screen.active { display: flex; }

/* Welcome Screen */
#welcome-screen {
    align-items: center;
    justify-content: center;
    flex-direction: column;
}

.welcome-container {
    text-align: center;
    padding: 2rem;
}

.logo {
    font-size: 4rem;
    font-weight: 200;
    letter-spacing: 0.3em;
    color: var(--soul-purple);
    margin-bottom: 0.5rem;
}

.tagline {
    color: var(--text-dim);
    font-size: 0.95rem;
    margin-bottom: 2.5rem;
    font-weight: 300;
}

#name-form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    align-items: center;
}

#name-input {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.85rem 1.25rem;
    color: var(--text);
    font-size: 1rem;
    width: 280px;
    text-align: center;
    outline: none;
    transition: border-color 0.2s;
}

#name-input:focus {
    border-color: var(--soul-purple);
}

#name-input::placeholder {
    color: var(--text-muted);
}

.btn-start {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.7rem 2.5rem;
    color: var(--text-dim);
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s;
    letter-spacing: 0.1em;
}

.btn-start:hover {
    border-color: var(--soul-purple);
    color: var(--soul-purple);
}

/* Chat Screen */
#chat-screen {
    flex-direction: column;
    background: var(--bg-chat);
}

.chat-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.logo-small {
    font-size: 1.1rem;
    font-weight: 200;
    letter-spacing: 0.2em;
    color: var(--soul-purple);
}

.mode-badge {
    font-size: 0.7rem;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    background: var(--soul-purple-bg);
    color: var(--soul-purple);
    letter-spacing: 0.05em;
}

.mode-badge.mirror {
    background: var(--mirror-gold-bg);
    color: var(--mirror-gold);
}

.header-right {
    display: flex;
    gap: 0.5rem;
}

.header-btn {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.35rem 0.75rem;
    color: var(--text-dim);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
}

.header-btn:hover {
    border-color: var(--text-dim);
    color: var(--text);
}

.mirror-btn:hover {
    border-color: var(--mirror-gold);
    color: var(--mirror-gold);
}

/* Messages */
.messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-width: 640px;
    width: 100%;
    margin: 0 auto;
}

.message {
    max-width: 80%;
    padding: 0.75rem 1rem;
    border-radius: var(--radius);
    line-height: 1.5;
    font-size: 0.92rem;
    animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

.message.soul {
    align-self: flex-start;
    background: var(--soul-purple-bg);
    color: var(--soul-purple);
    border-bottom-left-radius: 4px;
}

.message.mirror {
    align-self: flex-start;
    background: var(--mirror-gold-bg);
    color: var(--mirror-gold);
    border-bottom-left-radius: 4px;
}

.message.user {
    align-self: flex-end;
    background: var(--user-blue-bg);
    color: var(--user-blue);
    border-bottom-right-radius: 4px;
}

.message.system {
    align-self: center;
    background: transparent;
    color: var(--text-muted);
    font-size: 0.8rem;
    padding: 0.5rem;
}

.typing-indicator {
    align-self: flex-start;
    padding: 0.75rem 1rem;
    color: var(--text-muted);
    font-size: 0.85rem;
}

.typing-indicator span {
    animation: blink 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
    0%, 60%, 100% { opacity: 0.2; }
    30% { opacity: 1; }
}

/* Input */
.input-container {
    padding: 0.75rem 1rem 1.25rem;
    border-top: 1px solid var(--border);
    flex-shrink: 0;
}

#message-form {
    display: flex;
    gap: 0.5rem;
    max-width: 640px;
    margin: 0 auto;
}

#message-input {
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.75rem 1rem;
    color: var(--text);
    font-size: 0.92rem;
    outline: none;
    transition: border-color 0.2s;
}

#message-input:focus {
    border-color: var(--soul-purple);
}

#message-input::placeholder {
    color: var(--text-muted);
}

.btn-send {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 50%;
    width: 40px;
    height: 40px;
    color: var(--text-dim);
    font-size: 1.1rem;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-send:hover {
    border-color: var(--soul-purple);
    color: var(--soul-purple);
}

/* Status Overlay */
.overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    animation: fadeIn 0.2s ease;
}

.overlay.hidden { display: none; }

.overlay-content {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    width: 90%;
    max-width: 440px;
    max-height: 80vh;
    overflow-y: auto;
}

.overlay-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.25rem;
}

.overlay-header h2 {
    font-size: 1rem;
    font-weight: 400;
    letter-spacing: 0.1em;
    color: var(--soul-purple);
}

.btn-close {
    background: none;
    border: none;
    color: var(--text-dim);
    font-size: 1.4rem;
    cursor: pointer;
}

.dimension-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.6rem;
}

.dimension-label {
    font-size: 0.78rem;
    color: var(--text-dim);
    width: 140px;
    text-align: right;
    flex-shrink: 0;
}

.dimension-bar-bg {
    flex: 1;
    height: 6px;
    background: var(--bg);
    border-radius: 3px;
    overflow: hidden;
}

.dimension-bar {
    height: 100%;
    border-radius: 3px;
    background: var(--soul-purple);
    transition: width 0.5s ease;
}

.dimension-value {
    font-size: 0.72rem;
    color: var(--text-muted);
    width: 32px;
}

.status-meta {
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border);
    font-size: 0.8rem;
    color: var(--text-dim);
    line-height: 1.8;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
```

**Step 3: Commit**

```bash
git add static/index.html static/style.css
git commit -m "feat: add frontend HTML + CSS for chat UI"
```

---

### Task 7: Frontend — JavaScript

**Files:**
- Write: `static/app.js`

**Step 1: Implement app.js**

```javascript
/**
 * Vib — Frontend Application
 * Vanilla JS WebSocket chat client for The Soul interviewer + Soul Mirror.
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// State
let ws = null;
let userName = "";
let currentMode = "interview"; // "interview" | "mirror"

// Elements
const welcomeScreen = $("#welcome-screen");
const chatScreen = $("#chat-screen");
const nameForm = $("#name-form");
const nameInput = $("#name-input");
const messageForm = $("#message-form");
const messageInput = $("#message-input");
const messagesContainer = $("#messages");
const modeIndicator = $("#mode-indicator");
const btnStatus = $("#btn-status");
const btnMirror = $("#btn-mirror");
const statusOverlay = $("#status-overlay");
const statusBody = $("#status-body");
const btnCloseStatus = $("#btn-close-status");

// ── WebSocket Connection ──

function connect() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => {
        ws.send(JSON.stringify({ type: "start", name: userName }));
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    ws.onclose = () => {
        addSystemMessage("Connection lost. Refresh to reconnect.");
    };
}

function handleMessage(msg) {
    removeTypingIndicator();

    switch (msg.type) {
        case "opening":
            addSoulMessage(msg.text);
            break;

        case "response":
            if (msg.mode === "mirror") {
                addMirrorMessage(msg.text);
            } else {
                addSoulMessage(msg.text);
            }
            break;

        case "mode_change":
            currentMode = msg.mode;
            updateModeUI();
            if (msg.text) {
                if (msg.mode === "mirror") {
                    addMirrorMessage(msg.text);
                } else {
                    addSoulMessage(msg.text);
                }
            }
            break;

        case "status":
            showStatus(msg.data);
            break;
    }
}

// ── Messages ──

function addSoulMessage(text) {
    const div = document.createElement("div");
    div.className = "message soul";
    div.textContent = text;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function addMirrorMessage(text) {
    const div = document.createElement("div");
    div.className = "message mirror";
    div.textContent = text;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function addUserMessage(text) {
    const div = document.createElement("div");
    div.className = "message user";
    div.textContent = text;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function addSystemMessage(text) {
    const div = document.createElement("div");
    div.className = "message system";
    div.textContent = text;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function showTypingIndicator() {
    if ($("#typing")) return;
    const div = document.createElement("div");
    div.id = "typing";
    div.className = "typing-indicator";
    div.innerHTML = "<span>.</span><span>.</span><span>.</span>";
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function removeTypingIndicator() {
    const el = $("#typing");
    if (el) el.remove();
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// ── Mode Switching ──

function updateModeUI() {
    if (currentMode === "mirror") {
        modeIndicator.textContent = "your soul";
        modeIndicator.classList.add("mirror");
        btnMirror.textContent = "back to interview";
        messageInput.placeholder = "talk to your soul...";
    } else {
        modeIndicator.textContent = "the soul";
        modeIndicator.classList.remove("mirror");
        btnMirror.textContent = "meet your soul";
        messageInput.placeholder = "say something...";
    }
}

// ── Status Overlay ──

function showStatus(data) {
    let html = "";

    // Dimension bars
    const dims = data.dimensions || {};
    const labels = {
        attachment_style: "attachment",
        conflict_style: "conflict style",
        communication_style: "communication",
        vulnerability_comfort: "vulnerability",
        independence_interdependence: "independence",
        openness: "openness",
        conscientiousness: "conscientiousness",
        extroversion: "extroversion",
        agreeableness: "agreeableness",
        neuroticism: "neuroticism",
    };

    for (const [key, label] of Object.entries(labels)) {
        const val = dims[key] || 0;
        const pct = Math.round(val * 100);
        html += `
            <div class="dimension-row">
                <span class="dimension-label">${label}</span>
                <div class="dimension-bar-bg">
                    <div class="dimension-bar" style="width: ${pct}%"></div>
                </div>
                <span class="dimension-value">${pct}%</span>
            </div>
        `;
    }

    // Meta
    html += `
        <div class="status-meta">
            phase: ${data.phase || "—"}<br>
            trust: ${Math.round((data.trust_level || 0) * 100)}%<br>
            matchable: ${data.matchable ? "yes" : "not yet"}<br>
            ${data.open_contradictions > 0 ? `contradictions: ${data.open_contradictions} unresolved` : ""}
        </div>
    `;

    statusBody.innerHTML = html;
    statusOverlay.classList.remove("hidden");
}

// ── Event Listeners ──

nameForm.addEventListener("submit", (e) => {
    e.preventDefault();
    userName = nameInput.value.trim() || "friend";
    welcomeScreen.classList.remove("active");
    chatScreen.classList.add("active");
    connect();
    messageInput.focus();
});

messageForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    addUserMessage(text);
    ws.send(JSON.stringify({ type: "message", text }));
    messageInput.value = "";
    showTypingIndicator();
});

btnStatus.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "command", command: "status" }));
    }
});

btnMirror.addEventListener("click", () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const command = currentMode === "mirror" ? "interview" : "mirror";
    ws.send(JSON.stringify({ type: "command", command }));
    if (command === "mirror") {
        addSystemMessage("switching to soul mirror...");
        showTypingIndicator();
    } else {
        addSystemMessage("returning to interview...");
    }
});

btnCloseStatus.addEventListener("click", () => {
    statusOverlay.classList.add("hidden");
});

statusOverlay.addEventListener("click", (e) => {
    if (e.target === statusOverlay) {
        statusOverlay.classList.add("hidden");
    }
});
```

**Step 2: Manual test — run the server and verify UI loads**

```bash
uvicorn server:app --reload --port 8000
```

Open http://localhost:8000 in browser. Verify:
- Welcome screen appears with name input
- After entering name, chat screen shows
- Header has "status" and "meet your soul" buttons

**Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: add frontend JavaScript for WebSocket chat + mirror mode"
```

---

### Task 8: Update README + Pull Model

**Files:**
- Modify: `README.md`

**Step 1: Update README.md**

```markdown
# Vib — Agentic Dating

An AI that becomes you. It learns how you think, talk, and feel through natural conversation — then represents you in the dating world as your digital twin.

## Quick Start

### 1. Install Ollama and pull the model

```bash
# Install Ollama: https://ollama.com
ollama pull qwen3.5:4b
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
# Start the web app
uvicorn server:app --port 8000

# Open http://localhost:8000
```

### Using a different model size

```bash
# Use a larger model for better quality (needs more VRAM)
VIB_MODEL=qwen3.5:27b uvicorn server:app --port 8000

# Use the smallest model for testing
VIB_MODEL=qwen3.5:0.8b uvicorn server:app --port 8000
```

## How It Works

### The Interview

The Soul gets to know you through natural conversation. Behind the scenes, three systems work together:

- **Conversation Graph** — tracks emotional temperature, energy, open threads, trust
- **Soul Cartographer** — silently maps personality dimensions from every message
- **Move Generator** — selects conversational moves (open door, follow thread, observation, hypothetical, gentle contradiction, callback, share, rest)

### The Digital Twin

Once enough data is collected, you can "Meet Your Soul" — a self-aware digital twin that speaks as you. It mirrors your communication style, values, emotional patterns, and even your contradictions.

### The Vision

Your Soul talks to other Souls. Compatibility isn't a score — it emerges from whether your digital twins actually have good conversations together.

## Terminal Mode

```bash
# Interactive terminal demo (no web UI)
python demo.py --name "YourName"

# With debug mode
python demo.py --name "YourName" --debug

# Offline (no LLM, shows move selection only)
python demo.py --no-api
```

## Architecture

```
server.py                      ← FastAPI + WebSocket server
interviewer/
├── models.py                  ← State objects (Graph, Cartographer, Move types)
├── move_generator.py          ← Decision engine (eligibility → scoring → selection)
├── prompt_builder.py          ← LLM prompt assembly
├── orchestrator.py            ← Main loop (analyze → update → select → generate)
├── llm_client.py              ← Ollama client with model routing
└── persona_builder.py         ← Compiles digital twin persona from Cartographer data
static/
├── index.html                 ← Chat UI
├── style.css                  ← Dark, intimate aesthetic
└── app.js                     ← WebSocket client + UI logic
```

## Tests

```bash
pytest -v
```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for Ollama + web app MVP"
```

---

### Task 9: Integration Test — End-to-End

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
"""End-to-end integration test — verifies the full pipeline works without Ollama."""
import pytest
from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestFullFlow:
    def test_interview_then_mirror(self, client):
        """Complete flow: start → interview → check status → switch to mirror."""
        with client.websocket_connect("/ws") as ws:
            # Start
            ws.send_json({"type": "start", "name": "IntegrationTest"})
            opening = ws.receive_json()
            assert opening["type"] == "opening"
            assert len(opening["text"]) > 0

            # Send a few messages
            for msg in [
                "I've been thinking about moving to a new city",
                "I love being around people but I also need my alone time",
                "Honestly I think I avoid conflict too much",
            ]:
                ws.send_json({"type": "message", "text": msg})
                resp = ws.receive_json()
                assert resp["type"] == "response"
                assert len(resp["text"]) > 0

            # Check status
            ws.send_json({"type": "command", "command": "status"})
            status = ws.receive_json()
            assert status["type"] == "status"
            assert "dimensions" in status["data"]
            assert len(status["data"]["dimensions"]) == 10

            # Switch to mirror mode
            ws.send_json({"type": "command", "command": "mirror"})
            mirror = ws.receive_json()
            assert mirror["type"] == "mode_change"
            assert mirror["mode"] == "mirror"
            assert len(mirror["text"]) > 0

            # Talk to the twin
            ws.send_json({"type": "message", "text": "What do you think about long distance?"})
            twin_resp = ws.receive_json()
            assert twin_resp["type"] == "response"
            assert twin_resp["mode"] == "mirror"
            assert len(twin_resp["text"]) > 0

            # Switch back
            ws.send_json({"type": "command", "command": "interview"})
            back = ws.receive_json()
            assert back["type"] == "mode_change"
            assert back["mode"] == "interview"
```

**Step 2: Run full test suite**

```bash
pytest -v
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration test for full interview + mirror flow"
```

---

### Task 10: Pull Qwen Model + Smoke Test

**Step 1: Pull qwen3.5:4b via Ollama**

```bash
ollama pull qwen3.5:4b
```

**Step 2: Start the server**

```bash
uvicorn server:app --port 8000
```

**Step 3: Manual smoke test**

Open http://localhost:8000:
1. Enter a name
2. Have 5-6 exchanges with The Soul
3. Click "status" — verify dimension bars appear
4. Click "meet your soul" — verify mirror mode activates
5. Ask the twin a question — verify it responds in the user's style
6. Click "back to interview" — verify return to interview mode

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: MVP v0.1 complete — ready for demo"
```
