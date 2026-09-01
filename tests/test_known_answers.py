"""Known-answer fixtures: hand-built orders where the right box is obvious,

including the degenerate cases called out in the spec.
"""
from __future__ import annotations

from packing import Config, pack, try_pack_box
from packing.models import expand_items

from tests.helpers import make_box, make_item


CFG = Config(time_budget_ms=50)
# Zero dunnage/clearance configs isolate a single constraint under test.
TIGHT = Config(time_budget_ms=50, dunnage_reserve_pct=0.0, clearance_in=0.0)


def test_item_exactly_at_size_limit_fits():
    # Item exactly equal to usable interior (clearance 0) must fit.
    box = make_box("exact", 10, 8, 6)
    item = make_item("A", 10, 8, 6, 5.0)
    res = try_pack_box(expand_items([item]), box, TIGHT)
    assert res.ok, res.reason


def test_item_one_hundredth_over_fails():
    # 0.01" over the usable interior on one axis must fail -- no fudging.
    box = make_box("tiny", 10, 8, 6)
    item = make_item("A", 10.01, 8, 6, 5.0)
    res = try_pack_box(expand_items([item]), box, TIGHT)
    assert not res.ok
    assert "no orientation" in res.reason or "exceeds" in res.reason


def test_diagonal_only_item_fails():
    # Fits diagonally but not axis-aligned -> must fail (no rotated placement).
    box = make_box("cube", 8, 8, 8)
    item = make_item("long", 10, 1, 1, 2.0)  # 10 > 8 on every axis-aligned try
    res = try_pack_box(expand_items([item]), box, TIGHT)
    assert not res.ok


def test_sixty_lb_single_item_under_sixtyfive_cap_fits():
    box = make_box("heavy", 12, 10, 8, max_gross=65.0)
    item = make_item("H", 10, 8, 6, 60.0)
    res = try_pack_box(expand_items([item]), box, Config(time_budget_ms=50,
                                                         max_package_weight_lb=65.0))
    assert res.ok, res.reason


def test_sixtysix_lb_single_item_over_cap_fails_every_box():
    boxes = [
        make_box("a", 12, 10, 8, max_gross=65.0),
        make_box("b", 18, 12, 10, max_gross=65.0),
    ]
    item = make_item("TooHeavy", 10, 8, 6, 66.0)
    result = pack([item], boxes, Config(time_budget_ms=50, max_package_weight_lb=65.0,
                                        allow_split=True))
    # A bigger box never fixes a weight overflow, and one indivisible 66 lb
    # unit cannot be split -> the order simply cannot be packed.
    assert not result.ok
    assert any("cap" in line for line in result.explanation)


def test_smallest_fitting_box_is_chosen(catalog_boxes):
    # A single 9mm case should land in a modest box, not the 18x12x10.
    item = make_item("AMMO-9MM-1000", 11.5, 7.0, 5.5, 27.4)
    result = pack([item], catalog_boxes, CFG)
    assert result.ok
    assert result.total_packages == 1
    chosen = result.packages[0].box.name
    assert chosen not in ("LQ 18x12x10", "LQ 14x11x11"), chosen


def test_volume_reject_reason_is_specific():
    # One box far too small on volume; reason must name the fill limit.
    box = make_box("small", 6, 5, 4)
    items = [make_item(f"c{i}", 3, 3, 3, 1.0) for i in range(4)]
    res = try_pack_box(expand_items(items), box, Config(time_budget_ms=50,
                                                        dunnage_reserve_pct=0.15))
    assert not res.ok
    assert "fill limit" in res.reason or "no orientation" in res.reason


def test_explanation_covers_every_smaller_box(catalog_boxes):
    item = make_item("AMMO-9MM-1000", 11.5, 7.0, 5.5, 27.4)
    result = pack([item], catalog_boxes, CFG)
    # Every active box should appear in the log (rejected or fits/selected).
    active_names = [b.name for b in catalog_boxes if b.active]
    joined = "\n".join(result.explanation)
    for name in active_names:
        assert name in joined, f"{name} missing from explanation log"
