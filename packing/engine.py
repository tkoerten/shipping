"""Top-level orchestration: items + config -> PackResult, plus serialization.

Pure stdlib. This ties the packer, box selection and splitter together and
produces the output document (with the mandatory rejection/explanation log).
"""
from __future__ import annotations

import math
from typing import Any

from .models import (
    Box,
    Config,
    Item,
    ItemUnit,
    PackResult,
    PackedBox,
    Placement,
    expand_items,
)
from .selection import select_single_box
from .splitter import split_pack


def pack(items: list[Item], boxes: list[Box], config: Config) -> PackResult:
    """Cartonize an order.

    Strategy: prefer a single box (fewest packages). Only when no single active
    box holds everything -- usually the weight cap, not volume -- do we split
    into multiple packages. A weight overflow is answered by another package,
    never by a bigger box.
    """
    units = expand_items(items)
    if not units:
        return PackResult(packages=[], explanation=["No items to pack."], ok=False,
                          message="empty order")

    # 1. Single-box attempt.
    best, log = select_single_box(units, boxes, config)
    if best is not None:
        return PackResult(packages=[best], explanation=log, ok=True)

    # 2. No single box works. Split if allowed.
    if not config.allow_split:
        log.append("No single active box holds the order and splitting is disabled.")
        return PackResult(packages=[], explanation=log, ok=False,
                          message="no single box fits; splitting disabled")

    packages, split_log = split_pack(units, boxes, config)
    log.extend(split_log)
    if packages is None:
        return PackResult(packages=[], explanation=log, ok=False,
                          message="order cannot be packed within max_packages")

    return PackResult(packages=packages, explanation=log, ok=True)


# --------------------------------------------------------------------------- #
# Dunnage estimate
# --------------------------------------------------------------------------- #
_AIR_PILLOW_CU_IN = 8.0 * 4.0 * 2.0  # a single 8x4x2 air pillow


def estimate_dunnage(void_cu_in: float) -> str:
    if void_cu_in <= 1.0:
        return "none (snug fit)"
    pillows = max(1, math.ceil(void_cu_in / _AIR_PILLOW_CU_IN))
    return f"~ {pillows} air pillows (8x4x2)"


# --------------------------------------------------------------------------- #
# Serialization to the spec's output document
# --------------------------------------------------------------------------- #
def placement_to_dict(p: Placement) -> dict[str, Any]:
    return {
        "sku": p.unit.sku,
        "description": p.unit.description,
        "position": [round(p.x, 4), round(p.y, 4), round(p.z, 4)],
        "orientation": [round(p.dx, 4), round(p.dy, 4), round(p.dz, 4)],
        "weight_lb": p.unit.weight_lb,
        "length_in": p.unit.length_in,
        "width_in": p.unit.width_in,
        "height_in": p.unit.height_in,
        "goods_type": p.unit.goods_type,
    }


def package_to_dict(pkg: PackedBox) -> dict[str, Any]:
    return {
        "box": pkg.box.name,
        "box_id": pkg.box.id,
        "items": [placement_to_dict(p) for p in pkg.placements],
        "gross_weight_lb": round(pkg.gross_weight_lb, 2),
        "billable_weight_lb": round(pkg.billable_weight_lb, 2),
        "dim_weight_lb": pkg.dim_weight_lb,
        "fill_pct": round(pkg.fill_pct, 1),
        "void_volume_cu_in": round(pkg.void_volume_cu_in, 1),
        "estimated_dunnage": estimate_dunnage(pkg.void_volume_cu_in),
        "box_cost": pkg.box.cost,
        "wall_thickness_in": pkg.box.wall_thickness_in,
        "interior": {
            "length": pkg.box.interior_dims().length_in,
            "width": pkg.box.interior_dims().width_in,
            "height": pkg.box.interior_dims().height_in,
        },
        "exterior": {
            "length": round(pkg.box.interior_dims().length_in + 2 * pkg.box.wall_thickness_in, 3),
            "width": round(pkg.box.interior_dims().width_in + 2 * pkg.box.wall_thickness_in, 3),
            "height": round(pkg.box.interior_dims().height_in + 2 * pkg.box.wall_thickness_in, 3),
        },
    }


def result_to_dict(result: PackResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "message": result.message,
        "packages": [package_to_dict(p) for p in result.packages],
        "totals": {
            "packages": result.total_packages,
            "billable_weight_lb": round(result.total_billable_weight_lb, 2),
            "box_cost": round(result.total_box_cost, 2),
        },
        "explanation": result.explanation,
    }
