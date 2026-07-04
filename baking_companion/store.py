"""SQLite persistence for bake instances, marking, timeline events, and media.

Recipe templates live as YAML files; everything mutable lives here. Media files sit
on disk under <home>/media/<bake_id>/ with metadata rows pointing to them.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS bakes (
    id TEXT PRIMARY KEY,
    recipe_id TEXT, recipe_version INTEGER, name TEXT,
    status TEXT, anchor_kind TEXT, anchor_time TEXT,
    created_at TEXT, recipe_snapshot TEXT
);
CREATE TABLE IF NOT EXISTS node_states (
    bake_id TEXT, node_id TEXT, status TEXT,
    started_at TEXT, completed_at TEXT, expected_seconds REAL,
    PRIMARY KEY (bake_id, node_id)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bake_id TEXT, node_id TEXT, type TEXT, payload TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bake_id TEXT, node_id TEXT, path TEXT, kind TEXT,
    tags TEXT, caption TEXT, ts TEXT, elapsed_seconds REAL
);
"""


def default_home():
    return Path(os.environ.get("BAKING_HOME", Path.home() / ".baking_companion"))


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Store:
    def __init__(self, home=None):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "media").mkdir(exist_ok=True)
        # check_same_thread=False: the web server handles requests on worker threads;
        # writes are serialized through _lock so single-user access stays safe.
        self.db = sqlite3.connect(self.home / "baking.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self.db.executescript(SCHEMA)
        self.db.commit()

    def _write(self, sql, params=()):
        with self._lock:
            self.db.execute(sql, params)
            self.db.commit()

    # --- bakes ---
    def insert_bake(self, bake_id, recipe_id, version, name, status,
                    anchor_kind, anchor_time, created_at, snapshot):
        self._write(
            "INSERT INTO bakes VALUES (?,?,?,?,?,?,?,?,?)",
            (bake_id, recipe_id, version, name, status,
             anchor_kind, anchor_time, created_at, snapshot),
        )

    def get_bake(self, bake_id):
        return self.db.execute(
            "SELECT * FROM bakes WHERE id=?", (bake_id,)).fetchone()

    def list_bakes(self):
        return self.db.execute(
            "SELECT * FROM bakes ORDER BY created_at DESC").fetchall()

    def set_bake_status(self, bake_id, status):
        self._write("UPDATE bakes SET status=? WHERE id=?", (status, bake_id))

    # --- node states (the marking) ---
    def upsert_node_state(self, bake_id, node_id, status,
                          started_at=None, completed_at=None, expected_seconds=None):
        self._write(
            "INSERT OR REPLACE INTO node_states VALUES (?,?,?,?,?,?)",
            (bake_id, node_id, status, started_at, completed_at, expected_seconds),
        )

    def get_node_states(self, bake_id):
        return self.db.execute(
            "SELECT * FROM node_states WHERE bake_id=?", (bake_id,)).fetchall()

    def get_node_state(self, bake_id, node_id):
        return self.db.execute(
            "SELECT * FROM node_states WHERE bake_id=? AND node_id=?",
            (bake_id, node_id)).fetchone()

    def set_node_status(self, bake_id, node_id, status,
                        started_at=None, completed_at=None):
        sets, vals = ["status=?"], [status]
        if started_at is not None:
            sets.append("started_at=?"); vals.append(started_at)
        if completed_at is not None:
            sets.append("completed_at=?"); vals.append(completed_at)
        vals += [bake_id, node_id]
        self._write(
            f"UPDATE node_states SET {','.join(sets)} WHERE bake_id=? AND node_id=?",
            vals)

    def set_expected(self, bake_id, node_id, seconds):
        self._write(
            "UPDATE node_states SET expected_seconds=? WHERE bake_id=? AND node_id=?",
            (seconds, bake_id, node_id))

    # --- events (timeline / deviations / notes) ---
    def add_event(self, bake_id, node_id, type_, payload):
        self._write(
            "INSERT INTO events (bake_id,node_id,type,payload,ts) VALUES (?,?,?,?,?)",
            (bake_id, node_id, type_, json.dumps(payload), now_iso()))

    def get_events(self, bake_id):
        return self.db.execute(
            "SELECT * FROM events WHERE bake_id=? ORDER BY id", (bake_id,)).fetchall()

    # --- media ---
    def media_dir(self, bake_id):
        d = self.home / "media" / bake_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def add_media(self, bake_id, node_id, path, kind, tags, caption, elapsed_seconds):
        self._write(
            "INSERT INTO media (bake_id,node_id,path,kind,tags,caption,ts,elapsed_seconds)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (bake_id, node_id, path, kind, json.dumps(tags), caption,
             now_iso(), elapsed_seconds))

    def delete_media(self, media_id):
        row = self.db.execute(
            "SELECT * FROM media WHERE id=?", (media_id,)).fetchone()
        if not row:
            return False
        try:
            Path(row["path"]).unlink(missing_ok=True)
        except OSError:
            pass
        self._write("DELETE FROM media WHERE id=?", (media_id,))
        return True

    def get_media(self, bake_id=None, node_id=None, recipe_id=None):
        """Query media; recipe_id joins across bakes on the stable (recipe, node) key."""
        clauses, vals = [], []
        if recipe_id is not None:
            clauses.append("m.bake_id IN (SELECT id FROM bakes WHERE recipe_id=?)")
            vals.append(recipe_id)
        if bake_id is not None:
            clauses.append("m.bake_id=?"); vals.append(bake_id)
        if node_id is not None:
            clauses.append("m.node_id=?"); vals.append(node_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return self.db.execute(
            f"SELECT m.* FROM media m{where} ORDER BY m.ts", vals).fetchall()
