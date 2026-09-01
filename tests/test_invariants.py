"""Invariant tests over randomized item sets.

For any packing the engine claims succeeds:
  - no two placed items overlap,
  - nothing extends past usable bounds,
  - every package respects the weight cap,
  - total items in == total items out.
"""
from __future__ import annotations

import random

import pytest

from packing import Config, pack
from packing.geometry import boxes_overlap, usable_dims
from packing.models import expand_items

from tests.helpers import make_box, make_item

EPS = 1e-6


def _catalog():
    return [
        make_box("s", 10, 8, 6, cost=0.5, max_gross=65.0),
        make_box("m", 13, 9, 7, cost=0.7, max_gross=65.0),
        make_box("l", 16, 12, 8, cost=0.9, max_gross=65.0),
        make_box("xl", 18, 12, 10, cost=1.1, max_gross=65.0),
    ]


def _assert_package_sound(pkg, config):
    usable = usable_dims(pkg.box, config)
    placements = pkg.placements
    # Within usable bounds.
    for p in placements:
        assert p.x >= -EPS and p.y >= -EPS and p.z >= -EPS
        assert p.x2 <= usable.length_in + EPS
        assert p.y2 <= usable.width_in + EPS
        assert p.z2 <= usable.height_in + EPS
    # No overlaps.
    for i in range(len(placements)):
        a = placements[i]
        for j in range(i + 1, len(placements)):
            b = placements[j]
            assert not boxes_overlap(a, b.x, b.y, b.z, b.dx, b.dy, b.dz), (
                f"overlap between {a.unit.uid} and {b.unit.uid}"
            )
    # Weight cap.
    cap = pkg.box.gross_cap_lb(config.max_package_weight_lb)
    assert pkg.gross_weight_lb <= cap + EPS


@pytest.mark.parametrize("seed", range(40))
def test_random_orders_are_sound(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 8)
    items = []
    for i in range(n):
        l = rng.uniform(2, 9)
        w = rng.uniform(2, 8)
        h = rng.uniform(2, 6)
        wt = rng.uniform(1, 30)
        qty = rng.randint(1, 3)
        items.append(make_item(f"I{i}", l, w, h, wt, quantity=qty))

    config = Config(time_budget_ms=40, max_package_weight_lb=65.0)
    result = pack(items, _catalog(), config)

    if not result.ok:
        # A clean failure is allowed; if it fails it must explain itself.
        assert result.explanation
        return

    total_in = sum(it.quantity for it in items)
    total_out = sum(len(p.placements) for p in result.packages)
    assert total_out == total_in, "item conservation violated"

    for pkg in result.packages:
        _assert_package_sound(pkg, config)


def test_no_false_positive_on_oversize_item():
    # An item larger than every box must never be reported as packed.
    boxes = _catalog()
    items = [make_item("BIG", 40, 40, 40, 5.0)]
    result = pack(items, boxes, Config(time_budget_ms=40))
    assert not result.ok
