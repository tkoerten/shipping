"""Box-selection ranking, billable weight, and stacking/fragile rules."""
from __future__ import annotations

import math

from packing import Config, pack, try_pack_box
from packing.models import expand_items
from packing.selection import dim_weight_lb

from tests.helpers import make_box, make_item

CFG = Config(time_budget_ms=50)


def test_dim_weight_formula():
    box = make_box("b", 13, 9, 7)
    # 13*9*7 / 139 = 5.89 -> ceil 6
    assert dim_weight_lb(box, CFG) == 6


def test_billable_is_max_of_gross_and_dim():
    # A light bulky item: dim weight dominates.
    box = make_box("b", 18, 12, 10, tare=1.0)
    item = make_item("light", 16, 10, 8, 2.0)
    res = try_pack_box(expand_items([item]), box, CFG)
    assert res.ok
    from packing.models import PackedBox

    packed = PackedBox(box=box, placements=res.placements, config=CFG)
    dimw = math.ceil(18 * 12 * 10 / 139)  # 16
    assert packed.billable_weight_lb == max(packed.gross_weight_lb, dimw)
    assert packed.billable_weight_lb == dimw  # dim wins here


def test_ranking_prefers_lower_billable_weight():
    # Two boxes that both fit; the one with lower dim weight should win when
    # gross is equal and below both dim weights.
    small = make_box("small", 12, 10, 8, cost=1.0, max_gross=65.0)  # dim 7
    big = make_box("big", 18, 12, 12, cost=1.0, max_gross=65.0)     # dim 19
    item = make_item("L", 10, 8, 6, 3.0)
    result = pack([item], [small, big], CFG)
    assert result.ok
    assert result.packages[0].box.id == "small"


def test_ties_broken_by_cost_then_volume():
    # Equal billable weight (gross dominates), decide by cost.
    cheap = make_box("cheap", 13, 9, 7, cost=0.5, max_gross=65.0)
    pricey = make_box("pricey", 13, 9, 7, cost=0.9, max_gross=65.0)
    item = make_item("H", 10, 8, 6, 30.0)
    result = pack([item], [pricey, cheap], CFG)
    assert result.ok
    assert result.packages[0].box.id == "cheap"


def test_stack_load_limit_blocks_when_no_ordering_is_legal():
    # Two items that each weigh 10 lb but can bear only 5 lb on top. In a
    # single-column box they cannot sit side by side and cannot stack in
    # EITHER order (10 lb on a 5 lb cap), so the box must fail. This is the
    # case the engine cannot dodge by putting the capped item on top.
    box = make_box("narrow", 7, 5, 12, max_gross=65.0)  # one 6x4 column
    a = make_item("A", 6, 4, 4, 10.0, max_stack_load_lb=5.0)
    b = make_item("B", 6, 4, 4, 10.0, max_stack_load_lb=5.0)
    res = try_pack_box(expand_items([a, b]), box,
                       Config(time_budget_ms=50, dunnage_reserve_pct=0.0))
    assert not res.ok


def test_stack_load_capped_item_rides_on_top():
    # The engine SHOULD solve a weak-cap item by placing it on top of the heavy
    # one (nothing rests on it), rather than failing.
    box = make_box("narrow", 7, 5, 12, max_gross=65.0)
    weak = make_item("WEAK", 6, 4, 4, 3.0, max_stack_load_lb=5.0)
    heavy = make_item("HEAVY", 6, 4, 4, 20.0)
    res = try_pack_box(expand_items([weak, heavy]), box,
                       Config(time_budget_ms=50, dunnage_reserve_pct=0.0))
    assert res.ok, res.reason
    # WEAK must be the top item; nothing sits on it.
    top = max(res.placements, key=lambda p: p.z)
    assert top.unit.sku == "WEAK"


def test_stack_load_limit_allows_light_on_top():
    box = make_box("col", 7, 5, 12, max_gross=65.0)
    weak = make_item("WEAK", 6, 4, 4, 3.0, max_stack_load_lb=5.0)
    light = make_item("LIGHT", 6, 4, 4, 2.0)  # under the 5 lb cap
    res = try_pack_box(expand_items([weak, light]), box,
                       Config(time_budget_ms=50, dunnage_reserve_pct=0.0))
    assert res.ok, res.reason


def test_nothing_stacks_on_fragile():
    # Two fragile items in a single column: nothing may rest on a fragile item
    # in EITHER order, so they cannot stack and only one fits -> fail.
    box = make_box("col", 7, 5, 12, max_gross=65.0)
    a = make_item("FRAG-A", 6, 4, 4, 1.0, fragile=True)
    b = make_item("FRAG-B", 6, 4, 4, 1.0, fragile=True)
    res = try_pack_box(expand_items([a, b]), box,
                       Config(time_budget_ms=50, dunnage_reserve_pct=0.0))
    assert not res.ok


def test_fragile_item_rides_on_top():
    # One fragile + one normal in a single column: the fragile one must end up
    # on top (nothing rests on it), and the pack succeeds.
    box = make_box("col", 7, 5, 12, max_gross=65.0)
    frag = make_item("FRAG", 6, 4, 4, 1.0, fragile=True)
    other = make_item("OTHER", 6, 4, 4, 5.0)
    res = try_pack_box(expand_items([frag, other]), box,
                       Config(time_budget_ms=50, dunnage_reserve_pct=0.0))
    assert res.ok, res.reason
    top = max(res.placements, key=lambda p: p.z)
    assert top.unit.sku == "FRAG"


def test_exterior_box_subtracts_walls():
    # Exterior 10x8x6 with 0.25 walls -> interior 9.5x7.5x5.5; an item 9.4 long
    # fits interior but a 9.6 long item does not.
    box = make_box("ext", 10, 8, 6, dimensions_are="exterior", wall=0.25,
                   max_gross=65.0)
    ok_item = make_item("ok", 9.4, 7.0, 5.0, 2.0)
    bad_item = make_item("bad", 9.9, 7.0, 5.0, 2.0)
    tight = Config(time_budget_ms=50, clearance_in=0.0, dunnage_reserve_pct=0.0)
    assert try_pack_box(expand_items([ok_item]), box, tight).ok
    assert not try_pack_box(expand_items([bad_item]), box, tight).ok
