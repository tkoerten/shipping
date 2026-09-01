"""Loaders/serializers for the box catalog, SKU catalog and config.

Pure stdlib. The catalog lives in JSON (data/boxes.json, data/items.json,
data/config.json), editable at runtime through the UI -- nothing is hardcoded
in Python.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Box, Config, Dimensions, Item

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# --------------------------------------------------------------------------- #
# Boxes
# --------------------------------------------------------------------------- #
def box_from_dict(d: dict[str, Any]) -> Box:
    interior = d["interior"]
    return Box(
        id=d["id"],
        name=d["name"],
        interior=Dimensions(
            float(interior["length"]),
            float(interior["width"]),
            float(interior["height"]),
        ),
        wall_thickness_in=float(d.get("wall_thickness", 0.125)),
        tare_weight_lb=float(d.get("tare_weight_lb", 0.0)),
        cost=float(d.get("cost", 0.0)),
        max_gross_weight_lb=(
            None
            if d.get("max_gross_weight_lb") is None
            else float(d["max_gross_weight_lb"])
        ),
        active=bool(d.get("active", True)),
        notes=str(d.get("notes", "")),
        dimensions_are=str(d.get("dimensions_are", "interior")),
    )


def box_to_dict(b: Box) -> dict[str, Any]:
    return {
        "id": b.id,
        "name": b.name,
        "interior": {
            "length": b.interior.length_in,
            "width": b.interior.width_in,
            "height": b.interior.height_in,
        },
        "dimensions_are": b.dimensions_are,
        "wall_thickness": b.wall_thickness_in,
        "tare_weight_lb": b.tare_weight_lb,
        "cost": b.cost,
        "max_gross_weight_lb": b.max_gross_weight_lb,
        "active": b.active,
        "notes": b.notes,
    }


def load_boxes(path: str | Path | None = None) -> list[Box]:
    p = Path(path) if path else DATA_DIR / "boxes.json"
    data = json.loads(p.read_text())
    raw = data["boxes"] if isinstance(data, dict) else data
    return [box_from_dict(d) for d in raw]


def save_boxes(boxes: list[Box], path: str | Path | None = None) -> None:
    p = Path(path) if path else DATA_DIR / "boxes.json"
    payload = {"boxes": [box_to_dict(b) for b in boxes]}
    p.write_text(json.dumps(payload, indent=2))


# --------------------------------------------------------------------------- #
# Items / SKU catalog
# --------------------------------------------------------------------------- #
def item_from_dict(d: dict[str, Any]) -> Item:
    return Item(
        sku=d["sku"],
        description=str(d.get("description", "")),
        quantity=int(d.get("quantity", 1)),
        length_in=float(d["length"]),
        width_in=float(d["width"]),
        height_in=float(d["height"]),
        weight_lb=float(d["weight_lb"]),
        rotation=str(d.get("rotation", "free")),
        stackable=bool(d.get("stackable", True)),
        max_stack_load_lb=(
            None
            if d.get("max_stack_load_lb") is None
            else float(d["max_stack_load_lb"])
        ),
        fragile=bool(d.get("fragile", False)),
    )


def item_to_dict(it: Item) -> dict[str, Any]:
    return {
        "sku": it.sku,
        "description": it.description,
        "length": it.length_in,
        "width": it.width_in,
        "height": it.height_in,
        "weight_lb": it.weight_lb,
        "rotation": it.rotation,
        "stackable": it.stackable,
        "max_stack_load_lb": it.max_stack_load_lb,
        "fragile": it.fragile,
    }


def load_sku_catalog(path: str | Path | None = None) -> dict[str, Item]:
    p = Path(path) if path else DATA_DIR / "items.json"
    data = json.loads(p.read_text())
    raw = data["items"] if isinstance(data, dict) and "items" in data else data
    return {sku: item_from_dict(d) for sku, d in raw.items()}


def save_sku_catalog(catalog: dict[str, Item], path: str | Path | None = None) -> None:
    p = Path(path) if path else DATA_DIR / "items.json"
    payload = {"items": {sku: item_to_dict(it) for sku, it in catalog.items()}}
    p.write_text(json.dumps(payload, indent=2))


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def config_from_dict(d: dict[str, Any] | None) -> Config:
    d = d or {}
    kwargs: dict[str, Any] = {}
    for f in (
        "dunnage_reserve_pct",
        "clearance_in",
        "max_package_weight_lb",
        "dim_divisor",
        "allow_split",
        "max_packages",
        "time_budget_ms",
        "seed",
    ):
        if f in d and d[f] is not None:
            kwargs[f] = d[f]
    return Config(**kwargs)


def config_to_dict(c: Config) -> dict[str, Any]:
    return {
        "dunnage_reserve_pct": c.dunnage_reserve_pct,
        "clearance_in": c.clearance_in,
        "max_package_weight_lb": c.max_package_weight_lb,
        "dim_divisor": c.dim_divisor,
        "allow_split": c.allow_split,
        "max_packages": c.max_packages,
    }


def load_config(path: str | Path | None = None) -> Config:
    p = Path(path) if path else DATA_DIR / "config.json"
    if not p.exists():
        return Config()
    data = json.loads(p.read_text())
    return config_from_dict(data)
