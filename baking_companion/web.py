"""Stdlib HTTP server (no FastAPI/uvicorn) — the phone runs this in Termux and opens
the local web UI in Chrome. The browser does STT (Web Speech), TTS (speechSynthesis)
and camera (getUserMedia); this backend runs the FSM/router/scheduler.

Endpoints:
  GET  /                     -> web UI
  GET  /static/<file>        -> UI assets
  GET  /api/state            -> marking + schedule
  POST /api/ask   {text}     -> route an utterance (Tier-0 local / Tier-1 escalate)
  POST /api/command {cmd,node}-> begin | done | skip
  POST /api/capture?node=..  -> raw image/video bytes -> tagged media
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import importer, library, llm
from .duration import format_duration
from .engine import Engine
from .router import Router
from .scheduler import compute_schedule, expected_duration
from .store import Store

WEBDIR = Path(__file__).resolve().parent / "webui"
BUNDLED_RECIPES = Path(__file__).resolve().parent.parent / "recipes"


def state_payload(store, engine, bake_id):
    bake = store.get_bake(bake_id) if bake_id else None
    if bake is None:
        return {"bake": None, "nodes": [], "frontier": [], "eta": None,
                "suggestions": []}
    recipe = engine.recipe_of(bake)
    states = store.get_node_states(bake_id)
    smap = {s["node_id"]: dict(s) for s in states}
    sched = compute_schedule(recipe, states)

    def hm(nid):
        dt = sched["finish"].get(nid)
        return dt.strftime("%H:%M") if dt else None

    def ends_at(n):
        st = smap.get(n.id) or {}
        if st.get("status") == "active" and st.get("started_at"):
            dur = expected_duration(n, st)
            if dur.total_seconds() > 0:
                try:
                    return (datetime.fromisoformat(st["started_at"]) + dur).isoformat()
                except ValueError:
                    return None
        return None

    nodes = [{
        "id": n.id, "title": n.title, "type": n.type,
        "status": (smap.get(n.id) or {}).get("status", "blocked"),
        "says": n.says, "readiness": n.readiness_hint, "finish": hm(n.id),
        "ends_at": ends_at(n),
        "description": n.description, "temperature": n.temperature,
        "duration": (format_duration(n.duration.typical)
                     if n.duration and n.duration.typical else None),
        "ingredients": [{"name": i.name, "qty": i.qty, "unit": i.unit}
                        for i in n.ingredients],
        "references": [{"type": r.type, "url": r.url, "path": r.path,
                        "t_start": r.t_start, "caption": r.caption}
                       for r in n.references],
    } for n in recipe.nodes]
    end = sched["finish"].get("END")
    return {
        "bake": {"id": bake_id, "name": bake["name"], "status": bake["status"]},
        "nodes": nodes,
        "frontier": [s["node_id"] for s in states if s["status"] in ("ready", "active")],
        "eta": end.strftime("%a %H:%M") if end else None,
        "suggestions": [
            {"node": s["node"], "kind": s["kind"],
             "when": s["when"].strftime("%a %H:%M")}
            for s in sorted(sched["suggestions"], key=lambda x: x["when"])],
    }


def bakes_list(store):
    cur = current_bake_id(store)
    out = []
    for b in store.list_bakes():
        states = store.get_node_states(b["id"])
        total = len(states)
        done = sum(1 for s in states if s["status"] in ("done", "skipped"))
        out.append({"id": b["id"], "name": b["name"], "recipe": b["recipe_id"],
                    "status": b["status"], "done": done, "total": total,
                    "current": b["id"] == cur})
    return out


def current_bake_id(store):
    ptr = store.home / "current_bake.txt"
    if ptr.exists():
        bid = ptr.read_text().strip()
        if store.get_bake(bid):
            return bid
    return None


class Handler(BaseHTTPRequestHandler):
    store: Store = None
    engine: Engine = None
    router: Router = None

    def _bake_id(self):
        return current_bake_id(self.store)

    def _set_current(self, bid):
        (self.store.home / "current_bake.txt").write_text(bid)

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        return json.loads(raw or b"{}")

    def _serve_file(self, path: Path, ctype):
        if not path.exists():
            return self._send({"error": "not found"}, 404)
        self._send(path.read_bytes(), 200, ctype)

    def do_GET(self):
        parsed = urlparse(self.path)
        # Single-page app: /, /bakes, /recipes all serve the shell; the tab bar
        # and initial-screen-from-path logic live in app.js.
        if parsed.path in ("/", "/bakes", "/recipes"):
            return self._serve_file(WEBDIR / "index.html", "text/html")
        if parsed.path == "/api/bakes":
            return self._send(bakes_list(self.store))
        if parsed.path == "/api/recipes":
            return self._send(library.list_recipes(self.store.home))
        if parsed.path.startswith("/api/recipes/"):
            rid = parsed.path[len("/api/recipes/"):]
            y = library.get_yaml(self.store.home, rid)
            if y is None:
                return self._send({"error": "not found"}, 404)
            try:
                rec = importer.parse_and_validate(y).to_dict()
            except Exception:
                rec = None
            return self._send({"id": rid, "yaml": y, "recipe": rec})
        if parsed.path.startswith("/static/"):
            name = parsed.path[len("/static/"):]
            ctype = ("text/javascript" if name.endswith(".js")
                     else "text/css" if name.endswith(".css") else "text/plain")
            return self._serve_file(WEBDIR / name, ctype)
        if parsed.path == "/api/state":
            return self._send(state_payload(self.store, self.engine, self._bake_id()))
        if parsed.path == "/api/media":
            bid = self._bake_id()
            if not bid:
                return self._send([])
            items = self.store.get_media(bake_id=bid)
            out = [{"id": m["id"], "node": m["node_id"],
                    "url": f"/media/{bid}/{Path(m['path']).name}",
                    "ts": m["ts"], "kind": m["kind"], "caption": m["caption"],
                    "tags": json.loads(m["tags"] or "[]")} for m in items]
            return self._send(out)
        if parsed.path.startswith("/media/"):
            parts = parsed.path[len("/media/"):].split("/")
            if len(parts) != 2 or "." == parts[1] or "/" in parts[1] or ".." in parts[1]:
                return self._send({"error": "bad path"}, 400)
            fpath = self.store.media_dir(parts[0]) / parts[1]
            ext = fpath.suffix.lower()
            ctype = ({".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                      ".webm": "video/webm", ".mp4": "video/mp4"}
                     .get(ext, "application/octet-stream"))
            return self._serve_file(fpath, ctype)
        self._send({"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/recipes/"):
            rid = parsed.path[len("/api/recipes/"):]
            return self._send({"ok": library.delete(self.store.home, rid)})
        if parsed.path.startswith("/api/media/"):
            try:
                mid = int(parsed.path[len("/api/media/"):])
            except ValueError:
                return self._send({"ok": False}, 400)
            return self._send({"ok": self.store.delete_media(mid)})
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/recipes/import":
            if not llm.available():
                return self._send({"ok": False,
                                   "error": "No OPENROUTER_API_KEY set on the server."})
            b = self._read_json()
            try:
                res = importer.import_from_sources(
                    url=b.get("url") or None, text=b.get("text") or None,
                    images=b.get("images") or [])
                return self._send({"ok": True, "yaml": res["yaml"],
                                   "recipe": res["recipe"].to_dict(),
                                   "questions": res["questions"]})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)})
        if parsed.path == "/api/recipes/ai_edit":
            if not llm.available():
                return self._send({"ok": False, "error": "No OPENROUTER_API_KEY set."})
            b = self._read_json()
            try:
                res = importer.ai_edit(b["yaml"], b["instruction"])
                return self._send({"ok": True, "yaml": res["yaml"],
                                   "recipe": res["recipe"].to_dict()})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)})
        if parsed.path == "/api/recipes/save":
            b = self._read_json()
            try:
                r = library.save_yaml(self.store.home, b["yaml"])
                return self._send({"ok": True, "id": r.id, "name": r.name})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)})
        if parsed.path == "/api/bakes":                       # start a new bake instance
            b = self._read_json()
            y = library.get_yaml(self.store.home, b.get("recipe_id"))
            if not y:
                return self._send({"ok": False, "error": "recipe not found"})
            try:
                recipe = importer.parse_and_validate(y)
                bid = self.engine.create_bake(recipe, name=b.get("name") or None)
                self._set_current(bid)
                return self._send({"ok": True, "id": bid})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)})
        if parsed.path == "/api/bakes/select":
            bid = self._read_json().get("bake_id")
            if not self.store.get_bake(bid):
                return self._send({"ok": False, "error": "no such bake"})
            self._set_current(bid)
            return self._send({"ok": True})
        if parsed.path == "/api/ask":
            bid = self._bake_id()
            if not bid:
                return self._send({"tier": 0, "text": "No active bake — start one first."})
            text = self._read_json().get("text", "")
            resp = self.router.handle(text, bid)
            resp["state"] = state_payload(self.store, self.engine, bid)
            return self._send(resp)
        if parsed.path == "/api/command":
            bid = self._bake_id()
            if not bid:
                return self._send({"error": "no active bake"}, 400)
            body = self._read_json()
            cmd, node = body.get("cmd"), body.get("node")
            if cmd == "begin":
                self.engine.begin(bid, node)
            elif cmd == "done":
                self.engine.done(bid, node)
            elif cmd == "skip":
                self.engine.skip(bid, node, reason=body.get("reason"))
            elif cmd == "reopen":
                self.engine.reopen(bid, node)
            else:
                return self._send({"error": f"unknown cmd {cmd}"}, 400)
            return self._send(state_payload(self.store, self.engine, bid))
        if parsed.path == "/api/capture":
            bid = self._bake_id()
            if not bid:
                return self._send({"ok": False, "error": "no active bake"}, 400)
            qs = parse_qs(parsed.query)
            node = (qs.get("node") or [None])[0]
            tags = [t for t in (qs.get("tags") or [""])[0].split(",") if t]
            n = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(n) if n else b""
            ct = self.headers.get("Content-Type", "")
            suffix = ".jpg" if "image" in ct else ".mp4" if "mp4" in ct else ".webm"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                tf.write(data)
                tmp = tf.name
            dest = self.engine.capture(bid, node, tmp, tags=tags or ["capture"])
            return self._send({"ok": True, "path": str(dest)})
        self._send({"error": "not found"}, 404)


def serve(bake_id=None, host="0.0.0.0", port=8765, store=None):
    store = store or Store()
    engine = Engine(store)
    library.seed(store.home, BUNDLED_RECIPES)
    if bake_id and store.get_bake(bake_id):
        (store.home / "current_bake.txt").write_text(bake_id)
    Handler.store = store
    Handler.engine = engine
    Handler.router = Router(store, engine)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Baking companion serving on http://{host}:{port}")
    print("Open that URL in Chrome on the phone (localhost is a secure context).")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
