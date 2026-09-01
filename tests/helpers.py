"""Test construction helpers (importable by all test modules)."""
from __future__ import annotations

from packing import Box, Dimensions, Item


def make_box(
    id_: str,
    l: float,
    w: float,
    h: float,
    *,
    cost: float = 1.0,
    tare: float = 0.0,
    max_gross: float | None = None,
    active: bool = True,
    dimensions_are: str = "interior",
    wall: float = 0.125,
) -> Box:
    return Box(
        id=id_,
        name=id_,
        interior=Dimensions(l, w, h),
        wall_thickness_in=wall,
        tare_weight_lb=tare,
        cost=cost,
        max_gross_weight_lb=max_gross,
        active=active,
        dimensions_are=dimensions_are,
    )


def make_item(
    sku: str,
    l: float,
    w: float,
    h: float,
    weight: float,
    *,
    quantity: int = 1,
    rotation: str = "free",
    stackable: bool = True,
    max_stack_load_lb: float | None = None,
    fragile: bool = False,
    ship_alone: bool = False,
    exclusion_group: str | None = None,
) -> Item:
    return Item(
        sku=sku,
        length_in=l,
        width_in=w,
        height_in=h,
        weight_lb=weight,
        quantity=quantity,
        rotation=rotation,
        stackable=stackable,
        max_stack_load_lb=max_stack_load_lb,
        fragile=fragile,
        ship_alone=ship_alone,
        exclusion_group=exclusion_group,
    )
