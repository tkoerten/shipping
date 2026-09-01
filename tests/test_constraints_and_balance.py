"""Tests for balanced N-way splitting and the co-pack constraints
(ship-alone / "pack as is" and exclusion groups)."""
from __future__ import annotations

from packing import Config, pack, try_pack_box
from packing.models import expand_items
from packing.packer import copack_conflict

from tests.helpers import make_box, make_item

CFG64 = Config(time_budget_ms=60, max_package_weight_lb=64.0, allow_split=True)


def _catalog():
    return [
        make_box("s", 10, 8, 6, cost=0.5, max_gross=64.0),
        make_box("m", 16, 12, 8, cost=0.9, max_gross=64.0),
        make_box("l", 18, 12, 10, cost=1.1, max_gross=64.0),
    ]


# --------------------------------------------------------------------------- #
# #1 Balanced partition
# --------------------------------------------------------------------------- #
def test_four_20lb_split_is_balanced_2_and_2():
    # 4x20 = 80 > 64 cap -> 2 packages. Balanced means 2+2 (40/40), never the
    # greedy 3+1 (60/20).
    items = [make_item("W", 6, 5, 4, 20.0, quantity=4)]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    counts = sorted(len(p.placements) for p in result.packages)
    assert counts == [2, 2], counts
    for p in result.packages:
        assert p.gross_weight_lb <= 64.0 + 1e-6


def test_six_20lb_split_is_balanced_3_and_3():
    # 6x20 = 120 -> min 2 packages (each <= 3 items at 60 lb). Balanced 3/3.
    items = [make_item("W", 5, 5, 4, 20.0, quantity=6)]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    counts = sorted(len(p.placements) for p in result.packages)
    assert counts == [3, 3], counts


def test_balanced_split_minimizes_the_heaviest_package():
    # Mixed weights: heaviest package should be as light as the split allows.
    items = [
        make_item("A", 6, 5, 4, 30.0, quantity=2),
        make_item("B", 6, 5, 4, 20.0, quantity=2),
    ]  # total 100 lb -> 2 packages
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    assert result.total_packages == 2
    heaviest = max(p.gross_weight_lb for p in result.packages)
    # Best balance pairs a 30 with a 20 in each package -> ~50 lb each, not 60/40.
    assert heaviest <= 51.0, [p.gross_weight_lb for p in result.packages]


# --------------------------------------------------------------------------- #
# #2a ship-alone / "pack as is"
# --------------------------------------------------------------------------- #
def test_ship_alone_gets_its_own_package():
    items = [
        make_item("SOLO", 5, 4, 3, 2.0, ship_alone=True),
        make_item("OTHER", 5, 4, 3, 2.0),
    ]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    assert result.total_packages == 2
    # The SOLO package holds exactly one unit, and it's SOLO.
    solo_pkgs = [p for p in result.packages
                 if any(pl.unit.sku == "SOLO" for pl in p.placements)]
    assert len(solo_pkgs) == 1
    assert len(solo_pkgs[0].placements) == 1


def test_single_ship_alone_item_packs_normally():
    items = [make_item("SOLO", 5, 4, 3, 2.0, ship_alone=True)]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    assert result.total_packages == 1


def test_ship_alone_blocks_single_box_even_when_it_would_fit():
    # Both items are tiny and light -- geometrically/weight-wise one box is fine,
    # but ship_alone forbids combining, so no single box can hold both.
    items = [
        make_item("SOLO", 3, 3, 3, 1.0, ship_alone=True),
        make_item("X", 3, 3, 3, 1.0),
    ]
    units = expand_items(items)
    box = make_box("big", 18, 12, 10, max_gross=64.0)
    res = try_pack_box(units, box, CFG64)
    assert not res.ok
    assert "ship alone" in res.reason


# --------------------------------------------------------------------------- #
# #2b exclusion groups
# --------------------------------------------------------------------------- #
def test_different_exclusion_groups_never_share_a_package():
    items = [
        make_item("POWDER", 5, 4, 3, 2.0, exclusion_group="powder"),
        make_item("PRIMER", 5, 4, 3, 2.0, exclusion_group="primers"),
    ]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    assert result.total_packages == 2
    for p in result.packages:
        groups = {pl.unit.exclusion_group for pl in p.placements}
        assert len([g for g in groups if g]) <= 1


def test_same_exclusion_group_may_share():
    items = [
        make_item("POWDER-A", 5, 4, 3, 2.0, exclusion_group="powder"),
        make_item("POWDER-B", 5, 4, 3, 2.0, exclusion_group="powder"),
    ]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    assert result.total_packages == 1


def test_ungrouped_item_may_share_with_grouped():
    items = [
        make_item("POWDER", 5, 4, 3, 2.0, exclusion_group="powder"),
        make_item("PLAIN", 5, 4, 3, 2.0),
    ]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    assert result.total_packages == 1


def test_copack_conflict_helper():
    a = expand_items([make_item("A", 3, 3, 3, 1.0, exclusion_group="x")])[0]
    b = expand_items([make_item("B", 3, 3, 3, 1.0, exclusion_group="y")])[0]
    assert copack_conflict([a, b]) is not None
    assert copack_conflict([a]) is None


def test_exclusion_reason_surfaces_when_split_disabled():
    items = [
        make_item("POWDER", 5, 4, 3, 2.0, exclusion_group="powder"),
        make_item("PRIMER", 5, 4, 3, 2.0, exclusion_group="primers"),
    ]
    result = pack(items, _catalog(),
                  Config(time_budget_ms=60, max_package_weight_lb=64.0, allow_split=False))
    assert not result.ok
    assert any("exclusion groups" in line for line in result.explanation)
