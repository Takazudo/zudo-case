"""Frozen module hook data types."""
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import cadquery as cq

ExportKind = Literal["step", "stl", "dxf"]


@dataclass(frozen=True)
class Part:
    id: str
    solid: cq.Shape
    category: str
    material: str
    qty: int
    export_kinds: tuple[ExportKind, ...]
    dxf_outline: tuple[tuple[float, float], ...] | None = None
    dxf_holes: tuple[tuple[float, float, float], ...] = ()
    dxf_slots: tuple[tuple[float, float, float, float], ...] = ()


@dataclass(frozen=True)
class BuildContext:
    root: Path
    out: Path
    params: dict[str, dict]
    revision: str = "R9-PROTOTYPE-01"
    model: str = "7u40"

    def value(self, namespace: str, key: str):
        return self.params[namespace][key]["value"]
