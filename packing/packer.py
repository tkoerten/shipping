"""Extreme-point 3D bin packing heuristic.

Pure stdlib. This is the heart of the engine and the part that must be
bulletproof: a false positive (engine says it fits, packer cannot close the
box) destroys trust immediately. So a fit is ONLY ever claimed when an actual
non-overlapping, supported, weight-legal placement of every item is found.
Volume math is used exclusively for fast *rejection*, never to assert a fit.

We deliberately do NOT depend on py3dbp or similar -- they are unmaintained and
have known placement bugs. This is a self-contained ~implementation we can trust
and modify.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

from .geometry import (
    EPS,
    any_orientation_fits,
    boxes_overlap,
    orientations,
    support_area,
    usable_dims,
)
from .models import Box, Config, Dimensions, ItemUnit, Placement

# Minimum share of an item's base that must rest on a surface to be "supported".
MIN_SUPPORT_RATIO = 0.70


@dataclass
class FitResult:
    """Outcome of trying to pack one ordered item list into one box."""

    ok: bool
    placements: list[Placement]
    reason: str = ""  # human-readable rejection reason when ok is False


# --------------------------------------------------------------------------- #
# Fast rejects (volume/weight only ever produce a NO, never a YES)
# --------------------------------------------------------------------------- #
def fast_reject(
    units: list[ItemUnit], box: Box, config: Config
) -> Optional[str]:
    """Return a rejection reason if the box obviously cannot hold the units.

    None means "not obviously impossible" -- placement still has to prove it.
    """
    usable = usable_dims(box, config)

    # 1. Any single item with no orientation fitting inside usable dims.
    for u in units:
        if not any_orientation_fits(u, usable):
            longest_axis = max(
                usable.length_in, usable.width_in, usable.height_in
            )
            smallest_span = min(u.length_in, u.width_in, u.height_in)
            if smallest_span > longest_axis + EPS:
                return (
                    f"{_item_label(u)} smallest side {smallest_span:g}in exceeds "
                    f"longest usable axis ({longest_axis:g}in)."
                )
            return (
                f"{_item_label(u)} ({u.length_in:g}x{u.width_in:g}x{u.height_in:g}in) "
                f"has no orientation fitting usable interior "
                f"{usable.length_in:g}x{usable.width_in:g}x{usable.height_in:g}in."
            )

    # 2. Volume vs dunnage reserve.
    item_vol = sum(u.volume_cu_in for u in units)
    fill_limit = usable.volume_cu_in * (1.0 - config.dunnage_reserve_pct)
    if item_vol > fill_limit + EPS:
        pct = int(round((1.0 - config.dunnage_reserve_pct) * 100))
        return (
            f"item set volume {item_vol:.0f}cu-in exceeds {pct}% fill limit "
            f"({fill_limit:.0f}cu-in of {usable.volume_cu_in:.0f})."
        )

    # 3. Weight vs the binding cap (box gross cap and global package cap).
    total_weight = sum(u.weight_lb for u in units) + box.tare_weight_lb
    cap = box.gross_cap_lb(config.max_package_weight_lb)
    if total_weight > cap + EPS:
        return (
            f"gross weight {total_weight:.1f}lb (incl. {box.tare_weight_lb:g}lb "
            f"tare) exceeds {cap:g}lb cap."
        )

    return None


# --------------------------------------------------------------------------- #
# Single placement attempt for one item order
# --------------------------------------------------------------------------- #
class _Board:
    """Mutable packing state for a single ordered attempt inside one box."""

    def __init__(self, usable: Dimensions):
        self.usable = usable
        self.placed: list[Placement] = []
        # Each placed item's direct supporters (indices into self.placed) and
        # the running load resting on it.
        self.supporters: list[list[int]] = []
        self.carried_load: list[float] = []
        # Extreme points -- candidate min-corners. Seeded with the origin.
        self.eps: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)]

    # -- validity of a candidate placement -------------------------------- #
    def _in_bounds(self, x, y, z, dx, dy, dz) -> bool:
        return (
            x >= -EPS
            and y >= -EPS
            and z >= -EPS
            and x + dx <= self.usable.length_in + EPS
            and y + dy <= self.usable.width_in + EPS
            and z + dz <= self.usable.height_in + EPS
        )

    def _no_overlap(self, x, y, z, dx, dy, dz) -> bool:
        return not any(
            boxes_overlap(p, x, y, z, dx, dy, dz) for p in self.placed
        )

    def _supported(self, x, y, z, dx, dy, dz) -> bool:
        area = support_area(self.placed, x, y, z, dx, dy)
        base = dx * dy
        return base <= EPS or area >= MIN_SUPPORT_RATIO * base - EPS

    def _support_closure(self, x, y, z, dx, dy) -> list[int]:
        """Indices of all placed items in the vertical support column below a

        base footprint at height z (direct supporters and, transitively,
        everything under them). Used for stack-load and fragile checks.
        """
        # Direct supporters: top face level with z and overlapping footprint.
        direct: list[int] = []
        for i, p in enumerate(self.placed):
            if abs(p.z2 - z) > EPS:
                continue
            if (
                min(p.x2, x + dx) - max(p.x, x) > EPS
                and min(p.y2, y + dy) - max(p.y, y) > EPS
            ):
                direct.append(i)
        # Walk down the support graph.
        closure: set[int] = set()
        stack = list(direct)
        while stack:
            i = stack.pop()
            if i in closure:
                continue
            closure.add(i)
            stack.extend(self.supporters[i])
        return direct, sorted(closure)

    def _stack_and_fragile_ok(self, unit, x, y, z, dx, dy) -> tuple[bool, list[int]]:
        direct, closure = self._support_closure(x, y, z, dx, dy)
        for i in closure:
            below = self.placed[i].unit
            # A heavy item on a fragile one is forbidden outright: fragile
            # items must stay at the top of their column.
            if below.fragile:
                return False, direct
            # Stack-load accumulates down the column: every item beneath must
            # be able to bear this unit's full weight on top of what it already
            # carries (full weight through every path is intentionally
            # conservative -- bias toward "go up a size").
            if below.max_stack_load_lb is not None:
                if self.carried_load[i] + unit.weight_lb > below.max_stack_load_lb + EPS:
                    return False, direct
        return True, direct

    def valid(self, unit, x, y, z, dx, dy, dz) -> tuple[bool, list[int]]:
        if not self._in_bounds(x, y, z, dx, dy, dz):
            return False, []
        if not self._no_overlap(x, y, z, dx, dy, dz):
            return False, []
        if not self._supported(x, y, z, dx, dy, dz):
            return False, []
        return self._stack_and_fragile_ok(unit, x, y, z, dx, dy)

    # -- committing a placement ------------------------------------------- #
    def place(self, unit, x, y, z, dx, dy, dz, direct: list[int]) -> None:
        idx = len(self.placed)
        p = Placement(unit=unit, x=x, y=y, z=z, dx=dx, dy=dy, dz=dz)
        self.placed.append(p)
        self.supporters.append(list(direct))
        self.carried_load.append(0.0)
        # Propagate this unit's weight down the whole support closure.
        _, closure = self._support_closure(x, y, z, dx, dy)
        for i in closure:
            self.carried_load[i] += unit.weight_lb

        # New extreme points at the far corners along each axis, then project
        # each one straight down onto whatever supports it.
        new_eps = [
            (p.x2, p.y, p.z),
            (p.x, p.y2, p.z),
            (p.x, p.y, p.z2),
        ]
        for ex, ey, ez in new_eps:
            self.eps.append((ex, ey, self._drop_z(ex, ey, ez)))
        # Prune extreme points now buried inside the freshly placed item.
        self.eps = [e for e in self.eps if not self._buried(e)]
        # Dedup.
        uniq: list[tuple[float, float, float]] = []
        for e in self.eps:
            if not any(
                abs(e[0] - u[0]) < EPS
                and abs(e[1] - u[1]) < EPS
                and abs(e[2] - u[2]) < EPS
                for u in uniq
            ):
                uniq.append(e)
        self.eps = uniq

    def _drop_z(self, x: float, y: float, z: float) -> float:
        """Lower z to the highest surface at (x,y) not above z (gravity)."""
        best = 0.0
        for p in self.placed:
            if p.z2 <= z + EPS and (
                min(p.x2, x) - max(p.x, x) >= -EPS  # x within p's span
                and p.x - EPS <= x <= p.x2 + EPS
                and p.y - EPS <= y <= p.y2 + EPS
            ):
                if p.z2 > best:
                    best = p.z2
        return min(best, z)

    def _buried(self, e: tuple[float, float, float]) -> bool:
        x, y, z = e
        for p in self.placed:
            if (
                p.x - EPS < x < p.x2 - EPS
                and p.y - EPS < y < p.y2 - EPS
                and p.z - EPS < z < p.z2 - EPS
            ):
                return True
        return False


def _pack_one_order(units: list[ItemUnit], usable: Dimensions) -> Optional[list[Placement]]:
    """Try to place an ordered list of units. Return placements or None."""
    board = _Board(usable)
    for unit in units:
        best = None  # (z, y, x, x,y,z,dx,dy,dz, direct)
        for ori in orientations(unit):
            dx, dy, dz = ori
            for (ex, ey, ez) in board.eps:
                ok, direct = board.valid(unit, ex, ey, ez, dx, dy, dz)
                if not ok:
                    continue
                key = (ez, ey, ex)
                if best is None or key < best[0]:
                    best = (key, ex, ey, ez, dx, dy, dz, direct)
        if best is None:
            return None  # this unit could not be placed anywhere
        _, ex, ey, ez, dx, dy, dz, direct = best
        board.place(unit, ex, ey, ez, dx, dy, dz, direct)
    return board.placed


# --------------------------------------------------------------------------- #
# Multi-order attempt with deterministic randomized restarts
# --------------------------------------------------------------------------- #
def _orderings(units: list[ItemUnit]) -> list[list[ItemUnit]]:
    """Deterministic seed orderings. Item order drives the result."""
    return [
        sorted(units, key=lambda u: -u.volume_cu_in),          # volume desc
        sorted(units, key=lambda u: -u.longest_in),            # longest side desc
        sorted(units, key=lambda u: -u.weight_lb),             # weight desc
        sorted(units, key=lambda u: -u.footprint_in2),         # footprint desc
    ]


def try_pack_box(
    units: list[ItemUnit], box: Box, config: Config
) -> FitResult:
    """Attempt to pack all units into one box. Deterministic.

    Runs the fixed seed orderings, then deterministic shuffles (heavy items
    biased early) under a wall-clock budget. The first ordering that places
    every unit wins; identical input always yields identical output.
    """
    reason = fast_reject(units, box, config)
    if reason is not None:
        return FitResult(ok=False, placements=[], reason=f"{box.name} rejected: {reason}")

    usable = usable_dims(box, config)

    # Deterministic seed orderings first.
    for order in _orderings(units):
        placements = _pack_one_order(order, usable)
        if placements is not None:
            return FitResult(ok=True, placements=placements)

    # Deterministic randomized restarts under a time budget. Bias heavy items
    # early so the center of gravity stays low.
    rng = random.Random(config.seed ^ (hash(box.id) & 0xFFFFFFFF))
    deadline = time.monotonic() + config.time_budget_ms / 1000.0
    heavy_first = sorted(units, key=lambda u: -u.weight_lb)
    while time.monotonic() < deadline:
        order = _biased_shuffle(heavy_first, rng)
        placements = _pack_one_order(order, usable)
        if placements is not None:
            return FitResult(ok=True, placements=placements)

    return FitResult(
        ok=False,
        placements=[],
        reason=(
            f"{box.name} rejected: could not place all {len(units)} items "
            f"(no valid arrangement found)."
        ),
    )


def _biased_shuffle(units: list[ItemUnit], rng: random.Random) -> list[ItemUnit]:
    """Shuffle with heavy items biased toward the front (deterministic)."""
    scored = [
        (u.weight_lb + rng.random() * max(1.0, u.weight_lb), u) for u in units
    ]
    scored.sort(key=lambda t: -t[0])
    return [u for _, u in scored]


def _item_label(u: ItemUnit) -> str:
    return u.sku or u.description or "item"
