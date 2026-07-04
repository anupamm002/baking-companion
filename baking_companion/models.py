"""Pydantic schema — the single source of truth for recipes.

Serializes to/from YAML (authoring) and SQLite (runtime). Durations are stored as
timedeltas and serialized to float seconds for lossless JSON round-trips.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .duration import parse_duration


class Ingredient(BaseModel):
    name: str
    qty: Optional[float] = None          # absolute quantity is first-class
    unit: Optional[str] = None
    role: Optional[str] = None           # e.g. flour / water / leaven / salt / inclusion


class Duration(BaseModel):
    model_config = ConfigDict(ser_json_timedelta="float")

    min: Optional[timedelta] = None
    typical: Optional[timedelta] = None
    max: Optional[timedelta] = None

    @field_validator("min", "typical", "max", mode="before")
    @classmethod
    def _parse(cls, v):
        return parse_duration(v)


class Reference(BaseModel):
    """Authored reference (instructor/YouTube clip) or a pinned memory reference."""
    type: Literal["youtube", "local_video", "image", "note", "memory"]
    url: Optional[str] = None
    path: Optional[str] = None
    t_start: Optional[str] = None        # timestamp into a video, e.g. "12:30"
    t_end: Optional[str] = None
    caption: Optional[str] = None
    instance_id: Optional[str] = None    # for type=memory: pin a past bake's shot
    node_id: Optional[str] = None


class Capture(BaseModel):
    prompt_photo: bool = False
    tags: List[str] = Field(default_factory=list)


class ScheduleConstraint(BaseModel):
    model_config = ConfigDict(ser_json_timedelta="float")

    kind: Literal["finish_by", "start_before", "no_earlier_than"]
    target: str                          # a node id (or START/END)
    lead: Optional[timedelta] = None

    @field_validator("lead", mode="before")
    @classmethod
    def _parse(cls, v):
        return parse_duration(v)


class Node(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str = "action"                 # prep|mix|wait|action|bake|capture|subrecipe
    title: Optional[str] = None
    description: Optional[str] = None
    ingredients: List[Ingredient] = Field(default_factory=list)
    temperature: Optional[str] = None
    duration: Optional[Duration] = None  # INTRINSIC time of the step
    readiness_hint: Optional[str] = None
    nudge_after: Optional[str] = None    # 'typical' or a duration string
    references: List[Reference] = Field(default_factory=list)
    capture: Optional[Capture] = None
    says: Optional[str] = None


class Edge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    constraint: Optional[ScheduleConstraint] = None   # cross-branch scheduling only


class Scaling(BaseModel):
    mode: Literal["bakers_percent", "linear"] = "linear"
    anchor: Optional[str] = None         # ingredient name/role used as 100%


class Recipe(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    version: int = 1
    name: str
    yield_: Optional[str] = Field(default=None, alias="yield")
    equipment: List[str] = Field(default_factory=list)
    scaling: Optional[Scaling] = None
    nodes: List[Node]
    edges: List[Edge]

    def node_map(self):
        return {n.id: n for n in self.nodes}
