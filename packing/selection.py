"""Box selection: rank the boxes that actually succeeded.

Pure stdlib. The ranking encodes the business rule that billable weight matters
more than raw volume: a slightly larger box that bills the same is fine; a
smaller box that bills the same but risks a burst seam is not.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import usable_dims
from .models import Box, Config, PackedBox
from .packer import FitResult, try_pack_box


@dataclass
class BoxAttempt:
    box: Box
    result: FitResult


def dim_weight_lb(box: Box, config: Config) -> int:
    """Dimensional weight from the box's nominal (catalog) dimensions."""
    d = box.nominal_dims()
    return math.ceil(d.volume_cu_in / config.dim_divisor)


def billable_weight_lb(packed: PackedBox) -> float:
    return packed.billable_weight_lb


def _rank_key(packed: PackedBox) -> tuple:
    """Winner ranking for single-box solutions: PURELY the smallest box.

    Per operator direction we optimize for the smallest box that fits under all
    constraints -- not billable weight or carrier cost. The weight cap is still
    a hard constraint (a box only reaches ranking if every item fits and the
    package is under the cap), so the smallest box that gets here is a safe,
    closeable choice.

    1. interior volume (smallest box wins)
    2. box cost (tie-break between equal-size boxes: cheaper)
    3. box id (final deterministic tie-break)
    """
    return (
        round(packed.box.interior_dims().volume_cu_in, 4),
        round(packed.box.cost, 4),
        packed.box.id,
    )


def active_boxes_by_volume(boxes: list[Box], config: Config) -> list[Box]:
    """Active boxes sorted ascending by usable volume (evaluation order)."""
    active = [b for b in boxes if b.active]
    return sorted(active, key=lambda b: usable_dims(b, config).volume_cu_in)


def select_single_box(
    units, boxes: list[Box], config: Config
) -> tuple[PackedBox | None, list[str]]:
    """Try every active box; return the best single-box packing and a log.

    The log carries one human-readable line per box: why it was rejected, or
    that it succeeded. Every box smaller than the winner therefore has a
    stated reason -- that log is how a picker settles a dispute and how we find
    real bugs.
    """
    ordered = active_boxes_by_volume(boxes, config)
    winners: list[PackedBox] = []
    log: list[str] = []

    for box in ordered:
        res = try_pack_box(units, box, config)
        if res.ok:
            packed = PackedBox(box=box, placements=res.placements, config=config)
            winners.append(packed)
            log.append(
                f"{box.name} fits: all {len(units)} items placed, "
                f"{packed.fill_pct:.0f}% fill, "
                f"{packed.gross_weight_lb:.1f}lb gross / "
                f"{packed.billable_weight_lb:.0f}lb billable."
            )
        else:
            log.append(res.reason)

    if not winners:
        return None, log

    winners.sort(key=_rank_key)
    best = winners[0]

    # Reorder the log so the winner's selection line is explicit.
    final_log: list[str] = []
    for line in log:
        if line.startswith(f"{best.box.name} fits:"):
            continue
        final_log.append(line)
    final_log.append(
        f"{best.box.name} selected: all {len(units)} items placed, "
        f"{best.fill_pct:.0f}% fill, {best.gross_weight_lb:.1f}lb of "
        f"{best.box.gross_cap_lb(config.max_package_weight_lb):.0f}lb cap, "
        f"{best.billable_weight_lb:.0f}lb billable."
    )
    return best, final_log
