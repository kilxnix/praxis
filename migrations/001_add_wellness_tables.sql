-- migrations/001_add_wellness_tables.sql
-- Adds wellness-pivot tables to the existing Vib SQLite database.
-- Idempotent — safe to run multiple times.
-- Run with: sqlite3 vib.db < migrations/001_add_wellness_tables.sql

PRAGMA foreign_keys = ON;

-- ─── The polymorphic log ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entries (
  id              TEXT PRIMARY KEY,
  soul_id         TEXT NOT NULL,
  kind            TEXT NOT NULL,
  -- 'meal' | 'mood' | 'water' | 'sleep' | 'walk' | 'sunlight' | 'social' |
  -- 'weight' | 'purchase' | 'binge_marker' | 'note'
  payload_json    TEXT NOT NULL,
  at              TEXT NOT NULL,           -- ISO timestamp, when it happened
  logged_at       TEXT NOT NULL,           -- ISO timestamp, when it was logged
  source          TEXT NOT NULL,
  -- 'voice' | 'photo' | 'tap' | 'scan' | 'proactive' | 'manual'
  confidence      REAL NOT NULL DEFAULT 1.0,
  tagged_as_binge INTEGER,                 -- nullable; for meal entries
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS entries_soul_at_idx
  ON entries (soul_id, at DESC);

CREATE INDEX IF NOT EXISTS entries_soul_kind_idx
  ON entries (soul_id, kind, at DESC);

CREATE INDEX IF NOT EXISTS entries_soul_binge_idx
  ON entries (soul_id, at DESC)
  WHERE kind = 'binge_marker' OR tagged_as_binge = 1;

-- ─── VibState cache (one row per soul) ────────────────────────────

CREATE TABLE IF NOT EXISTS vib_state (
  soul_id              TEXT PRIMARY KEY,
  state_json           TEXT NOT NULL,
  attunement_confidence REAL NOT NULL DEFAULT 0.5,
  post_binge_mode      TEXT,                -- NULL | 'acute' | 'soft_morning'
  post_binge_until     TEXT,                -- ISO timestamp
  recomputed_at        TEXT NOT NULL,
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

-- ─── Risk windows (learned per user) ──────────────────────────────

CREATE TABLE IF NOT EXISTS risk_windows (
  id          TEXT PRIMARY KEY,
  soul_id     TEXT NOT NULL,
  day_of_week INTEGER NOT NULL,             -- 0..6 (Sun..Sat)
  hour_start  INTEGER NOT NULL,             -- 0..23
  hour_end    INTEGER NOT NULL,             -- 1..24
  confidence  REAL NOT NULL DEFAULT 0.5,
  hit_count   INTEGER NOT NULL DEFAULT 0,
  updated_at  TEXT NOT NULL,
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS risk_windows_soul_idx
  ON risk_windows (soul_id);

-- ─── Nudges (rate-limit + audit Vib's proactive messages) ─────────

CREATE TABLE IF NOT EXISTS nudges (
  id          TEXT PRIMARY KEY,
  soul_id     TEXT NOT NULL,
  sent_at     TEXT NOT NULL,
  reason      TEXT NOT NULL,
  message_id  TEXT,
  responded   INTEGER,                      -- 0/1/null
  acted_on    INTEGER,                      -- 0/1/null
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE,
  FOREIGN KEY (message_id) REFERENCES messages(id)
);

CREATE INDEX IF NOT EXISTS nudges_soul_sent_idx
  ON nudges (soul_id, sent_at DESC);

-- ─── Store cache (for the suggestion engine) ──────────────────────

CREATE TABLE IF NOT EXISTS store_items (
  id            TEXT PRIMARY KEY,
  soul_id       TEXT NOT NULL,
  store_name    TEXT NOT NULL,
  item_name     TEXT NOT NULL,
  macros_json   TEXT NOT NULL,
  price_cents   INTEGER,
  last_seen_at  TEXT NOT NULL,
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS store_items_soul_store_idx
  ON store_items (soul_id, store_name);

-- ─── Shortcuts (tap-to-log) ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS shortcuts (
  id          TEXT PRIMARY KEY,
  soul_id     TEXT NOT NULL,
  kind        TEXT NOT NULL,
  label       TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  use_count   INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL,
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS shortcuts_soul_kind_idx
  ON shortcuts (soul_id, kind);

-- ─── Extend the existing souls table with wellness preferences ────
-- These ALTER statements will fail with "duplicate column" on re-run.
-- Wrap your migration runner with try/except per ALTER, or use a
-- schema_versions table to gate it. For SQLite without a runner, you
-- can comment these out after the first successful run.

ALTER TABLE souls ADD COLUMN macro_targets_json TEXT;
ALTER TABLE souls ADD COLUMN food_budget_cents INTEGER;
ALTER TABLE souls ADD COLUMN food_budget_period_days INTEGER DEFAULT 7;
ALTER TABLE souls ADD COLUMN food_budget_period_start TEXT;
ALTER TABLE souls ADD COLUMN sidekick_name TEXT DEFAULT 'Vib';
ALTER TABLE souls ADD COLUMN quiet_hours_start TEXT DEFAULT '22:00';
ALTER TABLE souls ADD COLUMN quiet_hours_end TEXT DEFAULT '08:00';
ALTER TABLE souls ADD COLUMN max_nudges_per_day INTEGER DEFAULT 2;
ALTER TABLE souls ADD COLUMN timezone TEXT DEFAULT 'America/New_York';

-- ─── Drop the dating-Vib-only tables ──────────────────────────────
-- Uncomment after you're sure you don't want the data back.
-- (Keep them around during the pivot in case you want to reference
-- patterns from the dating conversations as evidence for the new
-- dimensions.)

-- DROP TABLE IF EXISTS vib_sessions;
-- DROP TABLE IF EXISTS vib_messages;
-- DROP TABLE IF EXISTS vib_results;
