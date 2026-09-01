"""Tests for smallest-box optimization (single box + N-way split) and the
ship-alone / "pack as is" constraint."""
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


def _box_names(result):
    return sorted(p.box.id for p in result.packages)


# --------------------------------------------------------------------------- #
# Smallest box -- single package
# --------------------------------------------------------------------------- #
def test_single_item_picks_the_smallest_fitting_box(catalog_boxes):
    # A single 9mm case (11.5x7x5.5) -> the smallest catalog box that fits it is
    # LQ 13x9x7 (819 cu-in), not a larger box that merely bills the same.
    item = make_item("AMMO-9MM-1000", 11.5, 7.0, 5.5, 27.4)
    result = pack([item], catalog_boxes, CFG64)
    assert result.ok
    assert result.total_packages == 1
    assert result.packages[0].box.name == "LQ 13x9x7", result.packages[0].box.name


def test_smaller_box_wins_even_when_a_bigger_one_also_fits():
    small = make_box("small", 12, 10, 8, cost=1.0, max_gross=64.0)   # 960 cu-in
    big = make_box("big", 18, 12, 12, cost=1.0, max_gross=64.0)      # 2592 cu-in
    item = make_item("X", 10, 8, 6, 5.0)
    result = pack([item], [big, small], CFG64)
    assert result.ok
    assert result.packages[0].box.id == "small"


# --------------------------------------------------------------------------- #
# Smallest boxes -- weight split
# --------------------------------------------------------------------------- #
def test_weight_split_produces_two_packages_under_cap():
    # 4x20 = 80 lb > 64 -> 2 packages, each under the cap.
    items = [make_item("W", 6, 5, 4, 20.0, quantity=4)]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    assert result.total_packages == 2
    for p in result.packages:
        assert p.gross_weight_lb <= 64.0 + 1e-6


def test_split_prefers_the_two_smallest_boxes():
    # 4x20: one package must hold >=2 items (needs the medium box); the other
    # holds a single item and can use the SMALL box. So the smallest-box split
    # is {m, s} -- not two mediums. This is "the two smallest packages".
    items = [make_item("W", 6, 5, 4, 20.0, quantity=4)]
    result = pack(items, _catalog(), CFG64)
    assert _box_names(result) == ["m", "s"], _box_names(result)


def test_split_uses_medium_pair_only_when_forced():
    # 6x20: the small box cannot hold 3 items, so each of the two packages needs
    # the medium box -> {m, m}. Nothing smaller is possible.
    items = [make_item("W", 5, 5, 4, 20.0, quantity=6)]
    result = pack(items, _catalog(), CFG64)
    assert result.total_packages == 2
    assert _box_names(result) == ["m", "m"], _box_names(result)


def test_split_never_uses_a_bigger_box_for_a_weight_overflow():
    # A single box could hold all 4 geometrically, but weight forces a split.
    # The result must never be a single (bigger) box.
    items = [make_item("W", 6, 5, 4, 20.0, quantity=4)]
    result = pack(items, _catalog(), CFG64)
    assert result.total_packages >= 2


def test_item_conservation_across_split():
    items = [make_item("W", 5, 5, 4, 18.0, quantity=7)]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    assert sum(len(p.placements) for p in result.packages) == 7


# --------------------------------------------------------------------------- #
# ship-alone / "pack as is"
# --------------------------------------------------------------------------- #
def test_ship_alone_gets_its_own_package():
    items = [
        make_item("SOLO", 5, 4, 3, 2.0, ship_alone=True),
        make_item("OTHER", 5, 4, 3, 2.0),
    ]
    result = pack(items, _catalog(), CFG64)
    assert result.ok
    assert result.total_packages == 2
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
    items = [
        make_item("SOLO", 3, 3, 3, 1.0, ship_alone=True),
        make_item("X", 3, 3, 3, 1.0),
    ]
    units = expand_items(items)
    box = make_box("big", 18, 12, 10, max_gross=64.0)
    res = try_pack_box(units, box, CFG64)
    assert not res.ok
    assert "ship alone" in res.reason


def test_copack_conflict_helper():
    a = expand_items([make_item("A", 3, 3, 3, 1.0, ship_alone=True)])[0]
    b = expand_items([make_item("B", 3, 3, 3, 1.0)])[0]
    assert copack_conflict([a, b]) is not None
    assert copack_conflict([b]) is None
