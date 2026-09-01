"""Cartonization engine -- pure-stdlib 3D bin packing.

Importable and testable on its own with no web server. Keep this package free
of framework imports so it can be lifted into another project or run as a batch
script against a CSV without dragging FastAPI along.
"""
from __future__ import annotations

from .catalog import (
    config_from_dict,
    config_to_dict,
    load_boxes,
    load_config,
    load_sku_catalog,
    save_boxes,
    save_sku_catalog,
)
from .engine import estimate_dunnage, pack, result_to_dict
from .models import (
    Box,
    Config,
    Dimensions,
    Item,
    ItemUnit,
    PackResult,
    PackedBox,
    Placement,
    expand_items,
)
from .packer import FitResult, try_pack_box
from .selection import select_single_box
from .splitter import split_pack

__all__ = [
    "Box",
    "Config",
    "Dimensions",
    "Item",
    "ItemUnit",
    "Placement",
    "PackedBox",
    "PackResult",
    "expand_items",
    "pack",
    "result_to_dict",
    "estimate_dunnage",
    "try_pack_box",
    "FitResult",
    "select_single_box",
    "split_pack",
    "load_boxes",
    "save_boxes",
    "load_sku_catalog",
    "save_sku_catalog",
    "load_config",
    "config_from_dict",
    "config_to_dict",
]
