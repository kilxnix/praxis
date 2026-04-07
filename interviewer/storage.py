"""
The Soul -- Persistent Storage

SQLite-backed persistence for souls. The soul is the evidence, not the summary.
Every trait signal, every message, every contradiction gets stored with context.
The CartographerState is rebuilt from evidence on load -- it's a view, not the source of truth.

Schema:
- souls: one per user
- sessions: one per conversation session
- messages: full conversation transcripts across all sessions
- trait_evidence: every signal observed, with the user's actual words
- contradictions: stated vs demonstrated gaps
- soul_state: cross-session state (trust, phase)
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from interviewer.models import (
    CartographerState, TraitConfidence, Contradiction, CartographerNeeds,
    ConversationGraph, Phase, EmotionalTemperature, phase_from_str,
)


DIMENSIONS = [
    "openness", "conscientiousness", "extroversion", "agreeableness",
    "neuroticism", "attachment_style", "conflict_style",
    "communication_style", "vulnerability_comfort",
    "independence_interdependence",
]


class SoulStorage:
    """SQLite persistence for souls."""

    def __init__(self, db_path: str = "souls.db"):
        self.db_path = db_path
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._init_tables()

    def _init_tables(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS souls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                soul_id INTEGER NOT NULL,
                session_number INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                soul_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                turn INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS trait_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                soul_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                turn INTEGER NOT NULL,
                dimension TEXT NOT NULL,
                signal TEXT NOT NULL,
                direction REAL,
                confidence_delta REAL NOT NULL,
                signal_type TEXT NOT NULL,
                user_quote TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS contradictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                soul_id INTEGER NOT NULL,
                dimension TEXT NOT NULL,
                stated TEXT NOT NULL,
                demonstrated TEXT NOT NULL,
                confidence REAL NOT NULL,
                first_noticed_session INTEGER NOT NULL,
                explored INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id)
            );

            CREATE TABLE IF NOT EXISTS soul_state (
                soul_id INTEGER PRIMARY KEY,
                trust_score REAL NOT NULL DEFAULT 0.1,
                phase TEXT NOT NULL DEFAULT 'FIRST_CONTACT',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id)
            );

            CREATE TABLE IF NOT EXISTS vib_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                soul_a_id INTEGER NOT NULL,
                soul_b_id INTEGER NOT NULL,
                turns_completed INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (soul_a_id) REFERENCES souls(id),
                FOREIGN KEY (soul_b_id) REFERENCES souls(id)
            );

            CREATE TABLE IF NOT EXISTS vib_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vib_id INTEGER NOT NULL,
                turn INTEGER NOT NULL,
                speaker_soul_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                phase TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (vib_id) REFERENCES vib_sessions(id),
                FOREIGN KEY (speaker_soul_id) REFERENCES souls(id)
            );

            CREATE TABLE IF NOT EXISTS vib_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vib_id INTEGER NOT NULL UNIQUE,
                compatibility_score REAL NOT NULL,
                recommendation TEXT NOT NULL,
                dimension_scores TEXT NOT NULL,
                key_moments TEXT NOT NULL,
                summary TEXT NOT NULL,
                soul_a_verdict TEXT,
                soul_b_verdict TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (vib_id) REFERENCES vib_sessions(id)
            );
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    # ── Soul lifecycle ──

    def get_or_create_soul(self, name: str) -> int:
        """Get existing soul by name, or create a new one. Returns soul_id."""
        row = self.db.execute(
            "SELECT id FROM souls WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row[0]

        now = datetime.now().isoformat()
        cursor = self.db.execute(
            "INSERT INTO souls (name, created_at, updated_at) VALUES (?, ?, ?)",
            (name, now, now),
        )
        soul_id = cursor.lastrowid
        self.db.execute(
            "INSERT INTO soul_state (soul_id, trust_score, phase, updated_at) "
            "VALUES (?, 0.1, 'FIRST_CONTACT', ?)",
            (soul_id, now),
        )
        self.db.commit()
        return soul_id

    def soul_exists(self, name: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM souls WHERE name = ?", (name,)
        ).fetchone()
        return row is not None

    # ── Sessions ──

    def start_session(self, soul_id: int) -> Tuple[int, int]:
        """Create a new session. Returns (session_id, session_number)."""
        row = self.db.execute(
            "SELECT COALESCE(MAX(session_number), 0) FROM sessions WHERE soul_id = ?",
            (soul_id,),
        ).fetchone()
        session_number = row[0] + 1

        cursor = self.db.execute(
            "INSERT INTO sessions (soul_id, session_number, started_at) VALUES (?, ?, ?)",
            (soul_id, session_number, datetime.now().isoformat()),
        )
        self.db.commit()
        return cursor.lastrowid, session_number

    def get_session_count(self, soul_id: int) -> int:
        row = self.db.execute(
            "SELECT COUNT(*) FROM sessions WHERE soul_id = ?", (soul_id,)
        ).fetchone()
        return row[0]

    # ── Messages ──

    def save_message(self, soul_id: int, session_id: int, turn: int,
                     role: str, content: str):
        self.db.execute(
            "INSERT INTO messages (soul_id, session_id, turn, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (soul_id, session_id, turn, role, content, datetime.now().isoformat()),
        )
        self.db.commit()

    def load_messages(self, soul_id: int, limit: int = 50) -> List[Dict[str, str]]:
        """Load recent messages across all sessions, oldest first."""
        rows = self.db.execute(
            "SELECT role, content FROM messages WHERE soul_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (soul_id, limit),
        ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def load_session_messages(self, session_id: int) -> List[Dict[str, str]]:
        """Load messages from a specific session."""
        rows = self.db.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows]

    def get_message_count(self, soul_id: int) -> int:
        row = self.db.execute(
            "SELECT COUNT(*) FROM messages WHERE soul_id = ?", (soul_id,)
        ).fetchone()
        return row[0]

    # ── Trait evidence ──

    def save_evidence(self, soul_id: int, session_id: int, turn: int,
                      signals: List[Dict], user_quote: str):
        """Save trait signals from a single analysis, tied to the user's words."""
        now = datetime.now().isoformat()
        for signal in signals:
            dimension = signal.get("dimension", "")
            if dimension not in DIMENSIONS:
                continue
            self.db.execute(
                "INSERT INTO trait_evidence "
                "(soul_id, session_id, turn, dimension, signal, direction, "
                "confidence_delta, signal_type, user_quote, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    soul_id, session_id, turn,
                    dimension,
                    signal.get("signal", ""),
                    signal.get("direction"),
                    signal.get("confidence_delta", 0.0),
                    signal.get("type", "stated"),
                    user_quote,
                    now,
                ),
            )
        self.db.commit()

    def load_evidence(self, soul_id: int) -> List[Dict]:
        """Load all trait evidence for a soul."""
        rows = self.db.execute(
            "SELECT dimension, signal, direction, confidence_delta, signal_type, "
            "user_quote, turn, session_id, created_at "
            "FROM trait_evidence WHERE soul_id = ? ORDER BY id",
            (soul_id,),
        ).fetchall()
        return [
            {
                "dimension": r[0], "signal": r[1], "direction": r[2],
                "confidence_delta": r[3], "signal_type": r[4],
                "user_quote": r[5], "turn": r[6], "session_id": r[7],
                "created_at": r[8],
            }
            for r in rows
        ]

    def load_evidence_by_dimension(self, soul_id: int) -> Dict[str, List[Dict]]:
        """Load evidence grouped by dimension -- useful for persona building."""
        evidence = self.load_evidence(soul_id)
        by_dim: Dict[str, List[Dict]] = {}
        for e in evidence:
            by_dim.setdefault(e["dimension"], []).append(e)
        return by_dim

    # ── Contradictions ──

    def save_contradiction(self, soul_id: int, contradiction: Dict):
        """Save a new contradiction if it doesn't already exist for this dimension."""
        existing = self.db.execute(
            "SELECT 1 FROM contradictions WHERE soul_id = ? AND dimension = ?",
            (soul_id, contradiction["dimension"]),
        ).fetchone()
        if existing:
            return

        self.db.execute(
            "INSERT INTO contradictions "
            "(soul_id, dimension, stated, demonstrated, confidence, "
            "first_noticed_session, explored, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
            (
                soul_id,
                contradiction["dimension"],
                contradiction["stated"],
                contradiction["demonstrated"],
                contradiction.get("confidence", 0.5),
                contradiction.get("first_noticed_session", 1),
                datetime.now().isoformat(),
            ),
        )
        self.db.commit()

    def load_contradictions(self, soul_id: int) -> List[Contradiction]:
        rows = self.db.execute(
            "SELECT dimension, stated, demonstrated, confidence, "
            "first_noticed_session, explored "
            "FROM contradictions WHERE soul_id = ?",
            (soul_id,),
        ).fetchall()
        return [
            Contradiction(
                dimension=r[0], stated=r[1], demonstrated=r[2],
                confidence=r[3], first_noticed_session=r[4], explored=bool(r[5]),
            )
            for r in rows
        ]

    def mark_contradiction_explored(self, soul_id: int, dimension: str):
        self.db.execute(
            "UPDATE contradictions SET explored = 1 "
            "WHERE soul_id = ? AND dimension = ?",
            (soul_id, dimension),
        )
        self.db.commit()

    # ── Soul state (trust, phase) ──

    def save_soul_state(self, soul_id: int, trust_score: float, phase: str):
        self.db.execute(
            "UPDATE soul_state SET trust_score = ?, phase = ?, updated_at = ? "
            "WHERE soul_id = ?",
            (trust_score, phase, datetime.now().isoformat(), soul_id),
        )
        self.db.execute(
            "UPDATE souls SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), soul_id),
        )
        self.db.commit()

    def load_soul_state(self, soul_id: int) -> Dict:
        row = self.db.execute(
            "SELECT trust_score, phase FROM soul_state WHERE soul_id = ?",
            (soul_id,),
        ).fetchone()
        if row:
            return {"trust_score": row[0], "phase": row[1]}
        return {"trust_score": 0.1, "phase": "FIRST_CONTACT"}

    # ── Rebuild CartographerState from evidence ──

    def load_cartographer(self, soul_id: int) -> CartographerState:
        """Rebuild the full CartographerState from stored evidence."""
        cart = CartographerState()

        # Replay all evidence to rebuild trait confidences
        evidence = self.load_evidence(soul_id)
        for e in evidence:
            dimension = e["dimension"]
            tc = getattr(cart, dimension, None)
            if not tc or not isinstance(tc, TraitConfidence):
                continue

            delta = e["confidence_delta"]
            if e["signal_type"] == "demonstrated":
                delta *= 2.0
            if dimension in ("communication_style", "extroversion", "openness"):
                delta = max(delta, 0.03)

            tc.confidence = min(tc.confidence + delta, 1.0)
            tc.evidence_count += 1

            if tc.stated_vs_demonstrated is None:
                tc.stated_vs_demonstrated = e["signal_type"]
            elif tc.stated_vs_demonstrated != e["signal_type"]:
                tc.stated_vs_demonstrated = "both"

        # Load contradictions
        cart.contradictions = self.load_contradictions(soul_id)

        return cart

    # ── Full soul load (for resuming a session) ──

    def load_soul(self, name: str) -> Optional[Dict]:
        """Load everything needed to resume a soul. Returns None if not found."""
        row = self.db.execute(
            "SELECT id FROM souls WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            return None

        soul_id = row[0]
        state = self.load_soul_state(soul_id)
        cartographer = self.load_cartographer(soul_id)
        messages = self.load_messages(soul_id)
        session_count = self.get_session_count(soul_id)
        evidence = self.load_evidence(soul_id)

        return {
            "soul_id": soul_id,
            "cartographer": cartographer,
            "messages": messages,
            "trust_score": state["trust_score"],
            "phase": state["phase"],
            "session_count": session_count,
            "evidence_count": len(evidence),
        }

    # ── Vib sessions ──

    def create_vib_session(self, soul_a_id: int, soul_b_id: int) -> int:
        """Create a new vib session between two souls. Returns vib_id."""
        cursor = self.db.execute(
            "INSERT INTO vib_sessions (soul_a_id, soul_b_id, started_at) "
            "VALUES (?, ?, ?)",
            (soul_a_id, soul_b_id, datetime.now().isoformat()),
        )
        self.db.commit()
        return cursor.lastrowid

    def save_vib_message(self, vib_id: int, turn: int,
                         speaker_soul_id: int, content: str, phase: str):
        """Save a single turn from a vib conversation."""
        self.db.execute(
            "INSERT INTO vib_messages "
            "(vib_id, turn, speaker_soul_id, content, phase, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (vib_id, turn, speaker_soul_id, content, phase,
             datetime.now().isoformat()),
        )
        self.db.commit()

    def complete_vib_session(self, vib_id: int, turns: int):
        """Mark a vib session as completed."""
        self.db.execute(
            "UPDATE vib_sessions SET turns_completed = ?, completed_at = ? "
            "WHERE id = ?",
            (turns, datetime.now().isoformat(), vib_id),
        )
        self.db.commit()

    def save_vib_result(self, vib_id: int, result_data: Dict):
        """Save the compatibility evaluation result for a vib."""
        import json as _json
        self.db.execute(
            "INSERT OR REPLACE INTO vib_results "
            "(vib_id, compatibility_score, recommendation, dimension_scores, "
            "key_moments, summary, soul_a_verdict, soul_b_verdict, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                vib_id,
                result_data["compatibility_score"],
                result_data["recommendation"],
                _json.dumps(result_data.get("dimension_scores", {})),
                _json.dumps(result_data.get("key_moments", [])),
                result_data.get("summary", ""),
                result_data.get("soul_a_verdict", ""),
                result_data.get("soul_b_verdict", ""),
                datetime.now().isoformat(),
            ),
        )
        self.db.commit()

    def load_vib_result(self, vib_id: int) -> Optional[Dict]:
        """Load the result of a vib session."""
        import json as _json
        row = self.db.execute(
            "SELECT compatibility_score, recommendation, dimension_scores, "
            "key_moments, summary, soul_a_verdict, soul_b_verdict "
            "FROM vib_results WHERE vib_id = ?",
            (vib_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "compatibility_score": row[0],
            "recommendation": row[1],
            "dimension_scores": _json.loads(row[2]),
            "key_moments": _json.loads(row[3]),
            "summary": row[4],
            "soul_a_verdict": row[5],
            "soul_b_verdict": row[6],
        }

    def load_vib_transcript(self, vib_id: int) -> List[Dict]:
        """Load the full transcript of a vib session."""
        rows = self.db.execute(
            "SELECT vm.turn, s.name, vm.content, vm.phase "
            "FROM vib_messages vm "
            "JOIN souls s ON vm.speaker_soul_id = s.id "
            "WHERE vm.vib_id = ? ORDER BY vm.turn",
            (vib_id,),
        ).fetchall()
        return [
            {"turn": r[0], "speaker": r[1], "content": r[2], "phase": r[3]}
            for r in rows
        ]

    def list_vibs(self, soul_id: Optional[int] = None) -> List[Dict]:
        """List vib sessions, optionally filtered by soul participation."""
        if soul_id:
            rows = self.db.execute(
                "SELECT vs.id, sa.name, sb.name, vs.turns_completed, "
                "vs.started_at, vs.completed_at "
                "FROM vib_sessions vs "
                "JOIN souls sa ON vs.soul_a_id = sa.id "
                "JOIN souls sb ON vs.soul_b_id = sb.id "
                "WHERE vs.soul_a_id = ? OR vs.soul_b_id = ? "
                "ORDER BY vs.id DESC",
                (soul_id, soul_id),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT vs.id, sa.name, sb.name, vs.turns_completed, "
                "vs.started_at, vs.completed_at "
                "FROM vib_sessions vs "
                "JOIN souls sa ON vs.soul_a_id = sa.id "
                "JOIN souls sb ON vs.soul_b_id = sb.id "
                "ORDER BY vs.id DESC",
            ).fetchall()

        return [
            {
                "vib_id": r[0],
                "soul_a": r[1],
                "soul_b": r[2],
                "turns_completed": r[3],
                "started_at": r[4],
                "completed_at": r[5],
            }
            for r in rows
        ]

    def get_soul_id_by_name(self, name: str) -> Optional[int]:
        """Look up a soul's ID by name."""
        row = self.db.execute(
            "SELECT id FROM souls WHERE name = ?", (name,)
        ).fetchone()
        return row[0] if row else None
