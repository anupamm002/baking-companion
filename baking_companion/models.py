"""Recipe schema on stdlib dataclasses (no third-party deps).

The single source of truth for recipes. `from_dict`/`to_dict` (de)serialize to/from YAML
(authoring) and SQLite/JSON (runtime). Durations are timedeltas; they serialize to float
seconds for lossless JSON round-trips. Kept dependency-free so the app installs on any
phone with just PyYAML.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Optional

from .duration import parse_duration


def _secs(td):
    return td.total_seconds() if isinstance(td, timedelta) else None


@dataclass
class Ingredient:
    name: str
    qty: Optional[float] = None          # absolute quantity is first-class
    unit: Optional[str] = None
    role: Optional[str] = None           # flour / water / leaven / salt / inclusion

    @classmethod
    def from_dict(cls, d):
        return cls(name=d["name"], qty=d.get("qty"),
                   unit=d.get("unit"), role=d.get("role"))

    def to_dict(self):
        return {"name": self.name, "qty": self.qty,
                "unit": self.unit, "role": self.role}


@dataclass
class Duration:
    min: Optional[timedelta] = None
    typical: Optional[timedelta] = None
    max: Optional[timedelta] = None

    @classmethod
    def from_dict(cls, d):
        if d is None:
            return None
        return cls(min=parse_duration(d.get("min")),
                   typical=parse_duration(d.get("typical")),
                   max=parse_duration(d.get("max")))

    def to_dict(self):
        return {"min": _secs(self.min), "typical": _secs(self.typical),
                "max": _secs(self.max)}


@dataclass
class Reference:
    type: str                            # youtube|local_video|image|note|memory
    url: Optional[str] = None
    path: Optional[str] = None
    t_start: Optional[str] = None
    t_end: Optional[str] = None
    caption: Optional[str] = None
    instance_id: Optional[str] = None
    node_id: Optional[str] = None

    _FIELDS = ("type", "url", "path", "t_start", "t_end",
               "caption", "instance_id", "node_id")

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: d.get(k) for k in cls._FIELDS})

    def to_dict(self):
        return {k: getattr(self, k) for k in self._FIELDS}


@dataclass
class Capture:
    prompt_photo: bool = False
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d):
        return cls(prompt_photo=bool(d.get("prompt_photo", False)),
                   tags=list(d.get("tags") or []))

    def to_dict(self):
        return {"prompt_photo": self.prompt_photo, "tags": list(self.tags)}


@dataclass
class ScheduleConstraint:
    kind: str                            # finish_by|start_before|no_earlier_than
    target: str
    lead: Optional[timedelta] = None

    @classmethod
    def from_dict(cls, d):
        return cls(kind=d["kind"], target=d["target"],
                   lead=parse_duration(d.get("lead")))

    def to_dict(self):
        return {"kind": self.kind, "target": self.target, "lead": _secs(self.lead)}


@dataclass
class Node:
    id: str
    type: str = "action"
    title: Optional[str] = None
    description: Optional[str] = None
    ingredients: List[Ingredient] = field(default_factory=list)
    temperature: Optional[str] = None
    duration: Optional[Duration] = None
    readiness_hint: Optional[str] = None
    nudge_after: Optional[str] = None
    references: List[Reference] = field(default_factory=list)
    capture: Optional[Capture] = None
    says: Optional[str] = None

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"], type=d.get("type", "action"),
            title=d.get("title"), description=d.get("description"),
            ingredients=[Ingredient.from_dict(i) for i in d.get("ingredients") or []],
            temperature=d.get("temperature"),
            duration=Duration.from_dict(d.get("duration")),
            readiness_hint=d.get("readiness_hint"), nudge_after=d.get("nudge_after"),
            references=[Reference.from_dict(r) for r in d.get("references") or []],
            capture=Capture.from_dict(d["capture"]) if d.get("capture") else None,
            says=d.get("says"))

    def to_dict(self):
        return {
            "id": self.id, "type": self.type, "title": self.title,
            "description": self.description,
            "ingredients": [i.to_dict() for i in self.ingredients],
            "temperature": self.temperature,
            "duration": self.duration.to_dict() if self.duration else None,
            "readiness_hint": self.readiness_hint, "nudge_after": self.nudge_after,
            "references": [r.to_dict() for r in self.references],
            "capture": self.capture.to_dict() if self.capture else None,
            "says": self.says}


@dataclass
class Edge:
    from_: str
    to: str
    constraint: Optional[ScheduleConstraint] = None

    @classmethod
    def from_dict(cls, d):
        return cls(from_=d.get("from", d.get("from_")), to=d["to"],
                   constraint=(ScheduleConstraint.from_dict(d["constraint"])
                               if d.get("constraint") else None))

    def to_dict(self):
        return {"from": self.from_, "to": self.to,
                "constraint": self.constraint.to_dict() if self.constraint else None}


@dataclass
class Scaling:
    mode: str = "linear"                 # linear | bakers_percent
    anchor: Optional[str] = None

    @classmethod
    def from_dict(cls, d):
        return cls(mode=d.get("mode", "linear"), anchor=d.get("anchor"))

    def to_dict(self):
        return {"mode": self.mode, "anchor": self.anchor}


@dataclass
class Recipe:
    id: str
    name: str
    version: int = 1
    yield_: Optional[str] = None
    equipment: List[str] = field(default_factory=list)
    scaling: Optional[Scaling] = None
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d):
        if isinstance(d, dict) and "recipe" in d and isinstance(d["recipe"], dict):
            d = d["recipe"]
        return cls(
            id=d["id"], name=d["name"], version=d.get("version", 1),
            yield_=d.get("yield", d.get("yield_")),
            equipment=list(d.get("equipment") or []),
            scaling=Scaling.from_dict(d["scaling"]) if d.get("scaling") else None,
            nodes=[Node.from_dict(n) for n in d.get("nodes") or []],
            edges=[Edge.from_dict(e) for e in d.get("edges") or []])

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "version": self.version,
            "yield": self.yield_, "equipment": list(self.equipment),
            "scaling": self.scaling.to_dict() if self.scaling else None,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges]}

    def node_map(self):
        return {n.id: n for n in self.nodes}

    def copy_deep(self):
        return copy.deepcopy(self)
