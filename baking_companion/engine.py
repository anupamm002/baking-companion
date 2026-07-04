"""Bake instance engine: create a bake from a recipe snapshot, drive the marking
(confirm-only advance), and record media / notes / deviations as an editable overlay.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path

from .graph import build_adjacency, START
from .models import Recipe
from .store import Store, now_iso

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp"}
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def _guess_kind(path):
    ext = Path(path).suffix.lower()
    if ext in _IMAGE_EXT:
        return "image"
    if ext in _VIDEO_EXT:
        return "video"
    return "file"


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def new_bake_id(recipe_id):
    return f"{date.today().isoformat()}_{recipe_id}_{uuid.uuid4().hex[:4]}"


class Engine:
    def __init__(self, store: Store):
        self.store = store

    # --- lifecycle ---
    def create_bake(self, recipe: Recipe, name=None,
                    anchor_kind="start_now", anchor_time=None):
        bake_id = new_bake_id(recipe.id)
        snapshot = json.dumps(recipe.model_dump(mode="json", by_alias=True))
        self.store.insert_bake(
            bake_id, recipe.id, recipe.version, name or recipe.name, "active",
            anchor_kind, anchor_time or now_iso(), now_iso(), snapshot)
        _, pred = build_adjacency(recipe)
        done = {START}
        for n in recipe.nodes:
            ready = all(p in done for p in pred.get(n.id, []))
            self.store.upsert_node_state(
                bake_id, n.id, "ready" if ready else "blocked")
        self.store.add_event(bake_id, None, "create", {"recipe": recipe.id,
                                                        "version": recipe.version})
        return bake_id

    def recipe_of(self, bake) -> Recipe:
        return Recipe.model_validate(json.loads(bake["recipe_snapshot"]))

    def _recompute_ready(self, bake_id, recipe):
        _, pred = build_adjacency(recipe)
        states = {r["node_id"]: r["status"] for r in self.store.get_node_states(bake_id)}
        done = {START} | {k for k, v in states.items() if v == "done"}
        for n in recipe.nodes:
            if states.get(n.id) in ("done", "active"):
                continue
            want = "ready" if all(p in done for p in pred.get(n.id, [])) else "blocked"
            if states.get(n.id) != want:
                self.store.set_node_status(bake_id, n.id, want)

    # --- marking transitions (only user actions move state) ---
    def begin(self, bake_id, node_id, at=None, expected=None):
        self.store.set_node_status(bake_id, node_id, "active",
                                   started_at=at or now_iso())
        if expected is not None:
            self.store.set_expected(bake_id, node_id, expected.total_seconds())
        self.store.add_event(bake_id, node_id, "begin",
                             {"at": at or now_iso(),
                              "expected_s": expected.total_seconds() if expected else None})

    def done(self, bake_id, node_id, at=None):
        self.store.set_node_status(bake_id, node_id, "done",
                                   completed_at=at or now_iso())
        self.store.add_event(bake_id, node_id, "done", {"at": at or now_iso()})
        bake = self.store.get_bake(bake_id)
        self._recompute_ready(bake_id, self.recipe_of(bake))

    def skip(self, bake_id, node_id, reason=None):
        self.store.set_node_status(bake_id, node_id, "skipped",
                                   completed_at=now_iso())
        self.store.add_event(bake_id, node_id, "skip", {"reason": reason})
        bake = self.store.get_bake(bake_id)
        self._recompute_ready(bake_id, self.recipe_of(bake))

    def note(self, bake_id, node_id, text):
        self.store.add_event(bake_id, node_id, "note", {"text": text})

    def deviation(self, bake_id, node_id, kind, detail):
        self.store.add_event(bake_id, node_id, "deviation",
                             {"kind": kind, "detail": detail})

    # --- forking (material divide) ---
    def fork(self, parent_bake_id, recipe, satisfied_nodes, name):
        """Spawn a child instance seeded with `satisfied_nodes` already done.

        Models a material divide: the child continues from "dough ready", either on a
        branch of the same recipe or grafted into another recipe (entry point) whose
        earlier dough-prep nodes are marked satisfied.
        """
        child_id = self.create_bake(recipe, name=name, anchor_kind="fork")
        for nid in satisfied_nodes:
            self.store.set_node_status(child_id, nid, "done", completed_at=now_iso())
        self._recompute_ready(child_id, recipe)
        self.store.add_event(child_id, None, "forked_from",
                             {"parent": parent_bake_id})
        self.store.add_event(parent_bake_id, None, "fork",
                             {"child": child_id, "name": name})
        return child_id

    # --- media ---
    def capture(self, bake_id, node_id, src, tags=None, caption=None):
        src = Path(src).expanduser()
        if not src.exists():
            raise FileNotFoundError(src)
        dest_dir = self.store.media_dir(bake_id)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = dest_dir / f"{stamp}_{node_id}_{src.name}"
        shutil.copy2(src, dest)
        elapsed = None
        st = self.store.get_node_state(bake_id, node_id)
        if st and st["started_at"]:
            started = _parse_dt(st["started_at"])
            if started:
                elapsed = (datetime.now().astimezone() - started).total_seconds()
        self.store.add_media(bake_id, node_id, str(dest), _guess_kind(src),
                             tags or [], caption, elapsed)
        self.store.add_event(bake_id, node_id, "capture",
                             {"path": str(dest), "tags": tags or []})
        return dest
