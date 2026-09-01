"""Pydantic request/response schemas for the API.

These are the wire contract. They convert to/from the pure-stdlib engine
dataclasses so the engine itself never imports pydantic or FastAPI.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from packing import Box, Config, Dimensions, Item
from packing.catalog import box_from_dict, config_from_dict, item_from_dict


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #
class ItemIn(BaseModel):
    sku: str
    description: str = ""
    quantity: int = 1
    length: float
    width: float
    height: float
    weight_lb: float
    rotation: str = "free"
    stackable: bool = True
    max_stack_load_lb: Optional[float] = None
    fragile: bool = False
    ship_alone: bool = False
    goods_type: str = ""

    def to_item(self) -> Item:
        return item_from_dict(self.model_dump())


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
class ConfigIn(BaseModel):
    dunnage_reserve_pct: Optional[float] = None
    clearance_in: Optional[float] = None
    max_package_weight_lb: Optional[float] = None
    dim_divisor: Optional[float] = None
    allow_split: Optional[bool] = None
    max_packages: Optional[int] = None
    time_budget_ms: Optional[int] = None
    seed: Optional[int] = None

    def to_config(self, base: Config) -> Config:
        merged = {
            "dunnage_reserve_pct": base.dunnage_reserve_pct,
            "clearance_in": base.clearance_in,
            "max_package_weight_lb": base.max_package_weight_lb,
            "dim_divisor": base.dim_divisor,
            "allow_split": base.allow_split,
            "max_packages": base.max_packages,
            "time_budget_ms": base.time_budget_ms,
            "seed": base.seed,
        }
        for k, v in self.model_dump().items():
            if v is not None:
                merged[k] = v
        return config_from_dict(merged)


# --------------------------------------------------------------------------- #
# Boxes
# --------------------------------------------------------------------------- #
class DimensionsIn(BaseModel):
    length: float
    width: float
    height: float


class BoxIn(BaseModel):
    id: str
    name: str
    interior: DimensionsIn
    dimensions_are: str = "interior"
    wall_thickness: float = 0.125
    tare_weight_lb: float = 0.0
    cost: float = 0.0
    max_gross_weight_lb: Optional[float] = None
    active: bool = True
    notes: str = ""

    def to_box(self) -> Box:
        return box_from_dict(self.model_dump())


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class PackRequest(BaseModel):
    items: list[ItemIn]
    config: Optional[ConfigIn] = None


class BatchOrder(BaseModel):
    order_id: Optional[str] = None
    items: list[ItemIn]
    config: Optional[ConfigIn] = None


class BatchRequest(BaseModel):
    orders: list[BatchOrder]
    config: Optional[ConfigIn] = None
    # Optional catalog override for "what-if" analysis. When present, the batch
    # is packed against THIS catalog instead of the saved one.
    boxes: Optional[list[BoxIn]] = None


class BoxesPut(BaseModel):
    boxes: list[BoxIn]


class ItemsPut(BaseModel):
    items: dict[str, ItemIn]


class ConfigPut(BaseModel):
    dunnage_reserve_pct: float
    clearance_in: float
    max_package_weight_lb: float
    dim_divisor: float
    allow_split: bool
    max_packages: int
