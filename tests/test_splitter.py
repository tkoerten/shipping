"""Multi-package splitting tests -- the weight-overflow rule in particular."""
from __future__ import annotations

from packing import Config, pack

from tests.helpers import make_box, make_item


def test_four_twenty_lb_items_split_into_two_packages():
    # The spec's acceptance case: four 20 lb items with a 65 lb cap must
    # produce TWO packages, never one bigger box. 4x20 = 80 > 65.
    boxes = [
        make_box("s", 10, 8, 6, max_gross=65.0),
        make_box("m", 16, 12, 8, max_gross=65.0),
        make_box("l", 18, 12, 10, max_gross=65.0),
    ]
    items = [make_item("W", 6, 5, 4, 20.0, quantity=4)]
    result = pack(items, boxes, Config(time_budget_ms=50, max_package_weight_lb=65.0,
                                       allow_split=True))
    assert result.ok
    assert result.total_packages == 2, result.explanation
    for pkg in result.packages:
        assert pkg.gross_weight_lb <= 65.0 + 1e-6


def test_no_package_exceeds_weight_cap_after_split():
    boxes = [make_box("m", 16, 12, 8, max_gross=65.0),
             make_box("l", 18, 12, 10, max_gross=65.0)]
    items = [make_item("W", 5, 5, 4, 18.0, quantity=7)]  # 126 lb total
    result = pack(items, boxes, Config(time_budget_ms=50, max_package_weight_lb=65.0))
    assert result.ok
    assert result.total_packages >= 2
    for pkg in result.packages:
        assert pkg.gross_weight_lb <= 65.0 + 1e-6


def test_split_disabled_fails_when_no_single_box_holds_all():
    boxes = [make_box("m", 16, 12, 8, max_gross=65.0)]
    items = [make_item("W", 6, 5, 4, 20.0, quantity=4)]
    result = pack(items, boxes, Config(time_budget_ms=50, max_package_weight_lb=65.0,
                                       allow_split=False))
    assert not result.ok


def test_max_packages_cap_respected():
    boxes = [make_box("s", 8, 6, 5, max_gross=65.0)]
    # 10 items of 30 lb each -> needs >=5 packages at 2 per box (60 lb).
    items = [make_item("W", 5, 4, 3, 30.0, quantity=10)]
    result = pack(items, boxes, Config(time_budget_ms=50, max_package_weight_lb=65.0,
                                       allow_split=True, max_packages=3))
    # Cannot fit 300 lb into 3 packages capped at 65 lb -> fail cleanly.
    assert not result.ok


def test_item_conservation_across_split():
    boxes = [make_box("m", 16, 12, 8, max_gross=65.0),
             make_box("l", 18, 12, 10, max_gross=65.0)]
    items = [make_item("W", 5, 5, 4, 18.0, quantity=7)]
    result = pack(items, boxes, Config(time_budget_ms=50, max_package_weight_lb=65.0))
    assert result.ok
    total_out = sum(len(p.placements) for p in result.packages)
    assert total_out == 7
