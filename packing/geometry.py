"""Geometry helpers: usable box space, allowed orientations, overlap & support.

Pure stdlib. All lengths in inches.
"""
from __future__ import annotations

from .models import (
    Box,
    Config,
    Dimensions,
    ItemUnit,
    Placement,
    ROTATION_FIXED,
    ROTATION_FREE,
    ROTATION_UPRIGHT,
)

# Float slop for geometric comparisons. Generous enough to absorb rounding but
# far below the 0.25" default clearance, so it never manufactures a fit.
EPS = 1e-6


def usable_dims(box: Box, config: Config) -> Dimensions:
    """Interior dimensions minus 2 x clearance on each axis.

    This is the space the packer is actually allowed to fill. The linear
    clearance -- not the volume percentage -- is the constraint that keeps a
    box closeable, so it is subtracted from every axis up front.
    """
    interior = box.interior_dims()
    pad = 2.0 * config.clearance_in
    return Dimensions(
        max(0.0, interior.length_in - pad),
        max(0.0, interior.width_in - pad),
        max(0.0, interior.height_in - pad),
    )


def orientations(unit: ItemUnit) -> list[tuple[float, float, float]]:
    """Allowed (dx, dy, dz) extents for a unit given its rotation rule.

    - free:    all 6 axis-aligned orientations (unique perms of l/w/h).
    - upright: height axis stays vertical (dz = height); footprint may spin on
               Z, so length/width may swap -> up to 2 orientations.
    - fixed:   exactly one orientation, (length, width, height).

    We never do rotated (non-axis-aligned) placement -- an item that only fits
    diagonally does not fit.
    """
    l, w, h = unit.length_in, unit.width_in, unit.height_in
    if unit.rotation == ROTATION_FIXED:
        cands = [(l, w, h)]
    elif unit.rotation == ROTATION_UPRIGHT:
        cands = [(l, w, h), (w, l, h)]
    elif unit.rotation == ROTATION_FREE:
        cands = [
            (l, w, h),
            (l, h, w),
            (w, l, h),
            (w, h, l),
            (h, l, w),
            (h, w, l),
        ]
    else:  # pragma: no cover - guarded in Item.__post_init__
        raise ValueError(f"unknown rotation {unit.rotation!r}")

    # Dedup orientations that are numerically identical (e.g. a cube, or l==w).
    seen: list[tuple[float, float, float]] = []
    for c in cands:
        if not any(_close3(c, s) for s in seen):
            seen.append(c)
    return seen


def _close3(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    return (
        abs(a[0] - b[0]) < EPS
        and abs(a[1] - b[1]) < EPS
        and abs(a[2] - b[2]) < EPS
    )


def fits_within(
    extent: tuple[float, float, float], dims: Dimensions
) -> bool:
    """True if an axis-aligned extent fits inside dims (with slop)."""
    dx, dy, dz = extent
    return (
        dx <= dims.length_in + EPS
        and dy <= dims.width_in + EPS
        and dz <= dims.height_in + EPS
    )


def any_orientation_fits(unit: ItemUnit, dims: Dimensions) -> bool:
    """True if at least one allowed orientation of unit fits inside dims."""
    return any(fits_within(o, dims) for o in orientations(unit))


def overlaps_1d(a0: float, a1: float, b0: float, b1: float) -> float:
    """Length of overlap of [a0,a1] and [b0,b1] (0 if disjoint)."""
    return max(0.0, min(a1, b1) - max(a0, b0))


def boxes_overlap(p: Placement, x: float, y: float, z: float,
                  dx: float, dy: float, dz: float) -> bool:
    """True if placed p overlaps the AABB at (x,y,z)+(dx,dy,dz) with volume."""
    ox = overlaps_1d(p.x, p.x2, x, x + dx)
    oy = overlaps_1d(p.y, p.y2, y, y + dy)
    oz = overlaps_1d(p.z, p.z2, z, z + dz)
    return ox > EPS and oy > EPS and oz > EPS


def support_area(
    placed: list[Placement], x: float, y: float, z: float, dx: float, dy: float
) -> float:
    """Contact area (in^2) supporting a base footprint at height z.

    Support comes from the floor (z ~= 0) or from the top faces of items whose
    top plane is level with z and whose xy-projection overlaps the footprint.
    """
    if z <= EPS:
        return dx * dy  # resting on the container floor: full support

    area = 0.0
    for p in placed:
        if abs(p.z2 - z) > EPS:
            continue  # top face is not level with this base
        ox = overlaps_1d(p.x, p.x2, x, x + dx)
        oy = overlaps_1d(p.y, p.y2, y, y + dy)
        if ox > EPS and oy > EPS:
            area += ox * oy
    return area
