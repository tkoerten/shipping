"""Multi-package splitting and the balancing sweep.

Pure stdlib.

CRITICAL RULE -- read before touching this file:

    A weight overflow NEVER means "use the next box up." A bigger box holds the
    same weight; a heavier package still bursts the same seam and still blows the
    carrier's weight cap. A weight overflow means OPEN ANOTHER PACKAGE.

Dense ammo hits the 65 lb cap long before it fills a 16x12x8, so splitting is
driven by weight far more often than by volume. This module is the only place
that decides to add a package.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Box, Config, ItemUnit, PackedBox
from .selection import _rank_key, select_single_box


@dataclass
class _Package:
    units: list[ItemUnit] = field(default_factory=list)
    packed: PackedBox | None = None  # cached best single-box packing


def _repack(units: list[ItemUnit], boxes: list[Box], config: Config) -> PackedBox | None:
    packed, _log = select_single_box(units, boxes, config)
    return packed


def split_pack(
    units: list[ItemUnit], boxes: list[Box], config: Config
) -> tuple[list[PackedBox] | None, list[str]]:
    """Greedily split units across packages, then run a balancing sweep.

    Returns (packages, log). packages is None if the order cannot be packed
    within max_packages even after splitting.
    """
    log: list[str] = []

    # 1. Heaviest first -- pack the hard items while packages are empty.
    ordered = sorted(units, key=lambda u: -u.weight_lb)

    packages: list[_Package] = []
    for unit in ordered:
        placed = False
        # Try to add to an existing package (first-fit over current packages).
        for pkg in packages:
            trial = pkg.units + [unit]
            packed = _repack(trial, boxes, config)
            if packed is not None:
                pkg.units = trial
                pkg.packed = packed
                placed = True
                break
        if placed:
            continue
        # Open a new package for it.
        if len(packages) >= config.max_packages:
            log.append(
                f"Split failed: {config.max_packages}-package cap reached with "
                f"{_label(unit)} still unplaced."
            )
            return None, log
        solo = _repack([unit], boxes, config)
        if solo is None:
            log.append(
                f"Split failed: {_label(unit)} does not fit any active box "
                f"even on its own."
            )
            return None, log
        pkg = _Package(units=[unit], packed=solo)
        packages.append(pkg)

    # 2. Balancing sweep: try relocating each unit to another package to reduce
    #    total billable weight or the package count. Accept improving moves only.
    _balance(packages, boxes, config)

    result = [p.packed for p in packages if p.packed is not None]
    log.append(
        f"Order split into {len(result)} packages "
        f"(weight cap {config.max_package_weight_lb:g}lb per package; a heavier "
        f"box is never the answer to a weight overflow -- another package is)."
    )
    return result, log


def _solution_score(packages: list[_Package]) -> tuple:
    """Rank a whole split solution: fewer packages, then total billable weight,

    then total box cost. Lower is better.
    """
    live = [p for p in packages if p.units]
    total_billable = sum(
        p.packed.billable_weight_lb for p in live if p.packed is not None
    )
    total_cost = sum(p.packed.box.cost for p in live if p.packed is not None)
    return (len(live), round(total_billable, 4), round(total_cost, 4))


def _balance(packages: list[_Package], boxes: list[Box], config: Config) -> None:
    """Repeatedly move a unit to a better package while it improves the score."""
    improved = True
    guard = 0
    while improved and guard < 1000:
        improved = False
        guard += 1
        base_score = _solution_score(packages)
        for src in packages:
            if not src.units:
                continue
            for unit in list(src.units):
                for dst in packages:
                    if dst is src:
                        continue
                    # Try moving `unit` from src to dst.
                    new_src_units = [u for u in src.units if u.uid != unit.uid]
                    new_dst_units = dst.units + [unit]
                    dst_packed = _repack(new_dst_units, boxes, config)
                    if dst_packed is None:
                        continue
                    src_packed = (
                        _repack(new_src_units, boxes, config)
                        if new_src_units
                        else None
                    )
                    if new_src_units and src_packed is None:
                        continue  # source would no longer pack -- illegal move

                    # Tentatively apply and score.
                    old = (
                        list(src.units), src.packed,
                        list(dst.units), dst.packed,
                    )
                    src.units, src.packed = new_src_units, src_packed
                    dst.units, dst.packed = new_dst_units, dst_packed
                    if _solution_score(packages) < base_score:
                        improved = True
                        break
                    # Revert.
                    src.units, src.packed, dst.units, dst.packed = (
                        old[0], old[1], old[2], old[3],
                    )
                if improved:
                    break
            if improved:
                break
    # Drop any package emptied by the sweep.
    packages[:] = [p for p in packages if p.units]


def _label(u: ItemUnit) -> str:
    return u.sku or u.description or "item"
