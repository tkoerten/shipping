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
        # Add to the LIGHTEST existing package that can still take it. Preferring
        # the emptiest feasible package spreads weight out from the start, so the
        # balancing sweep has less to undo and splits come out even.
        candidates = sorted(
            packages,
            key=lambda p: (p.packed.billable_weight_lb if p.packed else 0.0),
        )
        for pkg in candidates:
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
    """Rank a whole split solution. Lower is better.

    1. package count (fewest)
    2. BALANCE: the per-package billable weights sorted descending, compared
       lexicographically -- this minimizes the heaviest package first, then the
       next, etc. That is what "the two (or N) smallest packages" means: a
       balanced split, not one full box plus a nearly-empty one.
    3. total box cost (tie-break)
    4. total billable weight (tie-break)

    Balance leads cost deliberately: a weight overflow is answered by splitting
    into the smallest possible packages, matching how carriers bill dense parcels
    (dimensional weight is still weight). Cost only breaks ties between equally
    balanced splits.
    """
    live = [p for p in packages if p.units and p.packed is not None]
    billables = sorted((p.packed.billable_weight_lb for p in live), reverse=True)
    total_cost = sum(p.packed.box.cost for p in live)
    total_billable = sum(billables)
    return (
        len(live),
        tuple(round(b, 4) for b in billables),
        round(total_cost, 4),
        round(total_billable, 4),
    )


def _balance(packages: list[_Package], boxes: list[Box], config: Config) -> None:
    """Hill-climb toward a balanced split.

    The neighborhood is both MOVES (relocate one unit to another package) and
    SWAPS (trade a unit between two packages). Swaps matter: two packages of
    {30,30} and {20,20} cannot be balanced to {30,20}+{30,20} by any single
    move (the target overflows), only by a swap. First improving neighbor wins;
    repeat until no neighbor helps.
    """
    guard = 0
    while guard < 1000:
        guard += 1
        base = _solution_score(packages)
        if not (_try_moves(packages, boxes, config, base)
                or _try_swaps(packages, boxes, config, base)):
            break
    # Drop any package emptied by the sweep.
    packages[:] = [p for p in packages if p.units]


def _accept(
    packages, src, dst, new_src_units, new_dst_units, boxes, config, base
) -> bool:
    """Tentatively repack src/dst with new contents; keep it iff the whole
    solution's score improves. src/dst are elements of `packages`, so mutating
    them mutates the scored solution directly."""
    dst_packed = _repack(new_dst_units, boxes, config)
    if dst_packed is None:
        return False
    src_packed = _repack(new_src_units, boxes, config) if new_src_units else None
    if new_src_units and src_packed is None:
        return False
    old = (list(src.units), src.packed, list(dst.units), dst.packed)
    src.units, src.packed = new_src_units, src_packed
    dst.units, dst.packed = new_dst_units, dst_packed
    if _solution_score(packages) < base:
        return True
    src.units, src.packed, dst.units, dst.packed = old
    return False


def _try_moves(packages, boxes, config, base) -> bool:
    for src in packages:
        if not src.units:
            continue
        for unit in list(src.units):
            for dst in packages:
                if dst is src:
                    continue
                new_src = [u for u in src.units if u.uid != unit.uid]
                new_dst = dst.units + [unit]
                if _accept(packages, src, dst, new_src, new_dst, boxes, config, base):
                    return True
    return False


def _try_swaps(packages, boxes, config, base) -> bool:
    live = [p for p in packages if p.units]
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            a, b = live[i], live[j]
            for ua in list(a.units):
                for ub in list(b.units):
                    new_a = [u for u in a.units if u.uid != ua.uid] + [ub]
                    new_b = [u for u in b.units if u.uid != ub.uid] + [ua]
                    if _accept(packages, a, b, new_a, new_b, boxes, config, base):
                        return True
    return False


def _label(u: ItemUnit) -> str:
    return u.sku or u.description or "item"
