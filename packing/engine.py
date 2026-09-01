"""Top-level orchestration: items + config -> PackResult, plus serialization.

Pure stdlib. This ties the packer, box selection and splitter together and
produces the output document (with the mandatory rejection/explanation log).
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

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
from .selection import select_single_box
from .splitter import split_pack

# The synthetic "box" for an item that ships in its own manufacturer packaging.
NONOVERBOX_ID = "NonOverbox"
NONOVERBOX_NAME = "Manufacturer's Packaging"


def _nonoverbox_package(unit: ItemUnit, config: Config) -> PackedBox:
    """A package where the item's OWN dimensions are the container -- no overbox.

    The 'box' is exactly the item, with zero wall/tare/cost, and the fill/void
    are computed with no clearance or dunnage reserve, so it reads as 100% fill
    / 0 void (matching how a manufacturer-packaged / SIOC item actually ships).
    """
    box = Box(
        id=NONOVERBOX_ID,
        name=NONOVERBOX_NAME,
        interior=Dimensions(unit.length_in, unit.width_in, unit.height_in),
        wall_thickness_in=0.0,
        tare_weight_lb=0.0,
        cost=0.0,
        max_gross_weight_lb=None,
        active=True,
        notes="Ships in its own manufacturer packaging (no overbox).",
        dimensions_are="interior",
    )
    placement = Placement(
        unit=unit, x=0.0, y=0.0, z=0.0,
        dx=unit.length_in, dy=unit.width_in, dz=unit.height_in,
    )
    tight = replace(config, clearance_in=0.0, dunnage_reserve_pct=0.0)
    return PackedBox(box=box, placements=[placement], config=tight)


def pack(items: list[Item], boxes: list[Box], config: Config) -> PackResult:
    """Cartonize an order.

    Items flagged ``ship_in_own_container`` ship in their own manufacturer
    packaging (NonOverbox) -- each becomes its own container with 0 void. The
    remaining items are cartonized normally: prefer a single (smallest) box,
    else split into the smallest packages. A weight overflow is answered by
    another package, never a bigger box.
    """
    units = expand_items(items)
    if not units:
        return PackResult(packages=[], explanation=["No items to pack."], ok=False,
                          message="empty order")

    own_container = [u for u in units if u.ship_in_own_container]
    regular = [u for u in units if not u.ship_in_own_container]

    nb_packages = [_nonoverbox_package(u, config) for u in own_container]
    nb_log = [
        f"{u.sku or u.description or 'item'} ships in manufacturer's packaging "
        f"(NonOverbox), {u.length_in:g}x{u.width_in:g}x{u.height_in:g}in, "
        f"{u.weight_lb:g}lb."
        for u in own_container
    ]

    # Cartonize the remaining (overboxed) items.
    reg_packages: list[PackedBox] = []
    log: list[str] = []
    if regular:
        best, log = select_single_box(regular, boxes, config)
        if best is not None:
            reg_packages = [best]
        elif not config.allow_split:
            log.append("No single active box holds the order and splitting is disabled.")
            return PackResult(packages=[], explanation=log + nb_log, ok=False,
                              message="no single box fits; splitting disabled")
        else:
            packages, split_log = split_pack(regular, boxes, config)
            log.extend(split_log)
            if packages is None:
                return PackResult(packages=[], explanation=log + nb_log, ok=False,
                                  message="order cannot be packed within max_packages")
            reg_packages = packages

    return PackResult(
        packages=reg_packages + nb_packages,
        explanation=log + nb_log,
        ok=True,
    )


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
