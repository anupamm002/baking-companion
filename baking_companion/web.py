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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import Engine
from .router import Router
from .scheduler import compute_schedule
from .store import Store

WEBDIR = Path(__file__).resolve().parent / "webui"


def state_payload(store, engine, bake_id):
    bake = store.get_bake(bake_id)
    recipe = engine.recipe_of(bake)
    states = store.get_node_states(bake_id)
    smap = {s["node_id"]: dict(s) for s in states}
    sched = compute_schedule(recipe, states)

    def hm(nid):
        dt = sched["finish"].get(nid)
        return dt.strftime("%H:%M") if dt else None

    nodes = [{
        "id": n.id, "title": n.title, "type": n.type,
        "status": (smap.get(n.id) or {}).get("status", "blocked"),
        "says": n.says, "readiness": n.readiness_hint, "finish": hm(n.id),
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


class Handler(BaseHTTPRequestHandler):
    store: Store = None
    engine: Engine = None
    router: Router = None
    bake_id: str = None

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
        if parsed.path == "/":
            return self._serve_file(WEBDIR / "index.html", "text/html")
        if parsed.path.startswith("/static/"):
            name = parsed.path[len("/static/"):]
            ctype = ("text/javascript" if name.endswith(".js")
                     else "text/css" if name.endswith(".css") else "text/plain")
            return self._serve_file(WEBDIR / name, ctype)
        if parsed.path == "/api/state":
            return self._send(state_payload(self.store, self.engine, self.bake_id))
        if parsed.path == "/api/media":
            items = self.store.get_media(bake_id=self.bake_id)
            out = [{"node": m["node_id"],
                    "url": f"/media/{self.bake_id}/{Path(m['path']).name}",
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

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/ask":
            text = self._read_json().get("text", "")
            resp = self.router.handle(text, self.bake_id)
            resp["state"] = state_payload(self.store, self.engine, self.bake_id)
            return self._send(resp)
        if parsed.path == "/api/command":
            body = self._read_json()
            cmd, node = body.get("cmd"), body.get("node")
            if cmd == "begin":
                self.engine.begin(self.bake_id, node)
            elif cmd == "done":
                self.engine.done(self.bake_id, node)
            elif cmd == "skip":
                self.engine.skip(self.bake_id, node, reason=body.get("reason"))
            else:
                return self._send({"error": f"unknown cmd {cmd}"}, 400)
            return self._send(state_payload(self.store, self.engine, self.bake_id))
        if parsed.path == "/api/capture":
            qs = parse_qs(parsed.query)
            node = (qs.get("node") or [None])[0]
            tags = (qs.get("tags") or [""])[0]
            tags = [t for t in tags.split(",") if t]
            n = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(n) if n else b""
            suffix = ".jpg" if "image" in self.headers.get("Content-Type", "") else ".webm"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                tf.write(data)
                tmp = tf.name
            dest = self.engine.capture(self.bake_id, node, tmp, tags=tags or ["voice"])
            return self._send({"ok": True, "path": str(dest)})
        self._send({"error": "not found"}, 404)


def serve(bake_id=None, host="0.0.0.0", port=8765, store=None):
    store = store or Store()
    engine = Engine(store)
    if bake_id is None:
        ptr = store.home / "current_bake.txt"
        if not ptr.exists():
            raise SystemExit("No current bake. `bc start ...` or pass --bake.")
        bake_id = ptr.read_text().strip()
    if not store.get_bake(bake_id):
        raise SystemExit(f"No such bake: {bake_id}")
    Handler.store = store
    Handler.engine = engine
    Handler.router = Router(store, engine)
    Handler.bake_id = bake_id
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Baking companion serving {bake_id} on http://{host}:{port}")
    print("Open that URL in Chrome on the phone (localhost is a secure context).")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
