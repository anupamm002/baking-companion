"""LLM-assisted recipe import: URL / photo / text  ->  validated recipe YAML.

Fetches the source, prompts the model with our schema (cacheable) + rules, extracts the
emitted YAML, and validates it against the Pydantic schema + DAG rules before saving.
"""
from __future__ import annotations

import base64
import re
from html.parser import HTMLParser
from pathlib import Path

import urllib.request
import yaml

from . import llm
from .graph import validate_graph
from .models import Recipe

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

SCHEMA_GUIDE = """You convert baking recipes into a strict YAML graph for the Baking \
Companion app. Output ONE recipe as a directed acyclic graph of logical steps.

Rules:
- Implicit START and END nodes. Every real step is a node; edges give ordering/causality.
- FLATTEN loops: "3 folds every 30 min" -> fold_1, fold_2, fold_3 nodes (each ~30m).
- Nodes = LOGICAL STEPS only. Ingredients, quantities, temperature and technique are
  ATTRIBUTES of a node, never separate nodes. Something is a node ONLY if it has its own
  time footprint or needs its own notification (a levain build = node; "add 2 g salt" =
  attribute).
- Absolute ingredient quantities are FIRST-CLASS: {name, qty, unit, role}. Optionally add
  top-level `scaling: {mode: bakers_percent, anchor: <ingredient name>}` for bread.
- TIME: intrinsic step time goes on the node as `duration: {min, typical, max}` using
  strings like 30m, 1h30m, 7h. CROSS-BRANCH scheduling goes on an EDGE `constraint`:
  {kind: finish_by|start_before|no_earlier_than, target: <node id>, lead: <dur>}.
  Model parallel prep (preheat, pulling dough from the fridge, scoring) as parallel
  branches joined with such constraints.
- Optional per-node: readiness_hint, references [{type: youtube|local_video|image|note,
  url, path, t_start, caption}], capture {prompt_photo, tags}, temperature, says (a short
  spoken instruction).

YAML shape:
recipe:
  id: snake_case_id
  version: 1
  name: ...
  yield: ...
  equipment: [...]
  scaling: { mode: bakers_percent, anchor: bread flour }   # optional
  nodes:
    - id: ...
      type: prep|mix|wait|action|bake|capture|subrecipe
      title: ...
      description: ...
      ingredients: [{ name: ..., qty: 000, unit: g, role: flour }]
      temperature: "250C"
      duration: { min: 20m, typical: 30m, max: 45m }
      readiness_hint: ...
      capture: { prompt_photo: true, tags: [...] }
      says: ...
  edges:
    - { from: START, to: <first> }
    - { from: <a>, to: <b> }
    - { from: <branch>, to: <join>, constraint: { kind: finish_by, target: <join> } }
    - { from: <last>, to: END }

If critical info is missing, put a `# QUESTIONS` comment block with your clarifying
questions at the TOP of the YAML, then the best-effort recipe below it. Output ONLY a
single ```yaml fenced block — no prose outside the fence."""


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())

    def text(self):
        return "\n".join(self.parts)


def fetch_text(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (baking-companion)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode(errors="ignore")
    p = _HTMLText()
    p.feed(html)
    return p.text()


def build_messages(source_desc, source_text=None, image_b64=None, image_mime=None):
    system = [{"type": "text", "text": SCHEMA_GUIDE,
               "cache_control": {"type": "ephemeral"}}]
    content = [{"type": "text",
                "text": f"Convert the following into recipe YAML.\nSOURCE: {source_desc}"}]
    if source_text:
        content.append({"type": "text", "text": "RECIPE TEXT:\n" + source_text[:20000]})
    if image_b64:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}})
    return [{"role": "system", "content": system},
            {"role": "user", "content": content}]


def extract_yaml(text):
    m = re.search(r"```(?:yaml)?\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def parse_and_validate(yaml_text) -> Recipe:
    data = yaml.safe_load(yaml_text)
    recipe = Recipe.from_dict(data)
    validate_graph(recipe)
    return recipe


def _prepare(source):
    src = str(source)
    p = Path(src).expanduser()
    if src.startswith("http://") or src.startswith("https://"):
        return src, fetch_text(src), None, None
    if p.exists() and p.suffix.lower() in IMAGE_EXT:
        mime = "image/" + p.suffix.lower().lstrip(".").replace("jpg", "jpeg")
        return f"photo:{p.name}", None, base64.b64encode(p.read_bytes()).decode(), mime
    if p.exists():
        return f"file:{p.name}", p.read_text(), None, None
    return "pasted text", src, None, None      # treat unknown as raw text


def import_recipe(source, out_dir="recipes", model=None, dry_run=False):
    desc, text, img, mime = _prepare(source)
    messages = build_messages(desc, text, img, mime)
    if dry_run:
        return {"messages": messages, "source_desc": desc}
    raw = llm.chat(messages, model=model)
    recipe = parse_and_validate(extract_yaml(raw))   # raises on invalid
    out = Path(out_dir) / f"{recipe.id}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(extract_yaml(raw) + "\n")
    questions = [ln for ln in raw.splitlines() if ln.strip().startswith("# -")]
    return {"recipe": recipe, "path": out, "raw": raw, "questions": questions}
