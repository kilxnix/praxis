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
    "mood_baseline", "mood_volatility", "sleep_pattern",
    "hunger_relationship", "food_preferences", "risk_window_pattern",
    "movement_pattern", "social_pattern", "stressor_signals",
    "response_style",
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
        # Wellness tables
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                soul_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                at TEXT NOT NULL,
                logged_at TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                tagged_as_binge INTEGER,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS entries_soul_at_idx ON entries (soul_id, at DESC);
            CREATE INDEX IF NOT EXISTS entries_soul_kind_idx ON entries (soul_id, kind, at DESC);

            CREATE TABLE IF NOT EXISTS vib_state (
                soul_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                attunement_confidence REAL NOT NULL DEFAULT 0.5,
                post_binge_mode TEXT,
                post_binge_until TEXT,
                recomputed_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS risk_windows (
                id TEXT PRIMARY KEY,
                soul_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                hour_start INTEGER NOT NULL,
                hour_end INTEGER NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                hit_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS risk_windows_soul_idx ON risk_windows (soul_id);

            CREATE TABLE IF NOT EXISTS nudges (
                id TEXT PRIMARY KEY,
                soul_id INTEGER NOT NULL,
                sent_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                message_id TEXT,
                responded INTEGER,
                acted_on INTEGER,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS nudges_soul_sent_idx ON nudges (soul_id, sent_at DESC);

            CREATE TABLE IF NOT EXISTS shortcuts (
                id TEXT PRIMARY KEY,
                soul_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                label TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                use_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS shortcuts_soul_kind_idx ON shortcuts (soul_id, kind);
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
            if dimension in ("response_style", "mood_baseline", "hunger_relationship"):
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

    # ── Wellness entries ──

    def save_entry(self, soul_id: int, entry_id: str, kind: str,
                   payload: dict, at: str, source: str,
                   confidence: float = 1.0, tagged_as_binge: Optional[int] = None):
        import json as _json
        self.db.execute(
            "INSERT INTO entries "
            "(id, soul_id, kind, payload_json, at, logged_at, source, confidence, tagged_as_binge) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, soul_id, kind, _json.dumps(payload), at,
             datetime.now().isoformat(), source, confidence, tagged_as_binge),
        )
        self.db.commit()

    def load_entries(self, soul_id: int, kind: Optional[str] = None,
                     limit: int = 50) -> List[Dict]:
        import json as _json
        if kind:
            rows = self.db.execute(
                "SELECT id, kind, payload_json, at, logged_at, source, confidence, tagged_as_binge "
                "FROM entries WHERE soul_id = ? AND kind = ? ORDER BY at DESC LIMIT ?",
                (soul_id, kind, limit),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT id, kind, payload_json, at, logged_at, source, confidence, tagged_as_binge "
                "FROM entries WHERE soul_id = ? ORDER BY at DESC LIMIT ?",
                (soul_id, limit),
            ).fetchall()
        return [
            {
                "id": r[0], "kind": r[1], "payload": _json.loads(r[2]),
                "at": r[3], "logged_at": r[4], "source": r[5],
                "confidence": r[6], "tagged_as_binge": r[7],
            }
            for r in rows
        ]

    def tag_entry_as_binge(self, entry_id: str):
        self.db.execute(
            "UPDATE entries SET tagged_as_binge = 1 WHERE id = ?",
            (entry_id,),
        )
        self.db.commit()

    # ── Vib state cache ──

    def save_vib_state(self, soul_id: int, state_json: str,
                       attunement: float, post_binge_mode: Optional[str] = None,
                       post_binge_until: Optional[str] = None):
        self.db.execute(
            "INSERT OR REPLACE INTO vib_state "
            "(soul_id, state_json, attunement_confidence, post_binge_mode, "
            "post_binge_until, recomputed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (soul_id, state_json, attunement, post_binge_mode,
             post_binge_until, datetime.now().isoformat()),
        )
        self.db.commit()

    def load_vib_state(self, soul_id: int) -> Optional[Dict]:
        import json as _json
        row = self.db.execute(
            "SELECT state_json, attunement_confidence, post_binge_mode, post_binge_until "
            "FROM vib_state WHERE soul_id = ?",
            (soul_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "state": _json.loads(row[0]),
            "attunement": row[1],
            "post_binge_mode": row[2],
            "post_binge_until": row[3],
        }

    def get_soul_id_by_name(self, name: str) -> Optional[int]:
        """Look up a soul's ID by name."""
        row = self.db.execute(
            "SELECT id FROM souls WHERE name = ?", (name,)
        ).fetchone()
        return row[0] if row else None
