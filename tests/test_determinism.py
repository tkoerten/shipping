"""Determinism: identical input must yield byte-identical output every time.

Warehouse staff notice flip-flopping, so the RNG is seeded and the whole
pipeline is deterministic.
"""
from __future__ import annotations

import json

from packing import Config, pack, result_to_dict

from tests.helpers import make_box, make_item


def _catalog():
    return [
        make_box("s", 10, 8, 6, cost=0.5, max_gross=65.0),
        make_box("m", 13, 9, 7, cost=0.7, max_gross=65.0),
        make_box("l", 16, 12, 8, cost=0.9, max_gross=65.0),
        make_box("xl", 18, 12, 10, cost=1.1, max_gross=65.0),
    ]


def test_single_box_output_stable_over_100_runs():
    items = [
        make_item("A", 8, 6, 4, 12.0, quantity=2),
        make_item("B", 5, 5, 5, 6.0, quantity=3),
        make_item("C", 9, 7, 3, 9.0),
    ]
    config = Config(time_budget_ms=40)
    first = json.dumps(result_to_dict(pack(items, _catalog(), config)), sort_keys=True)
    for _ in range(100):
        again = json.dumps(
            result_to_dict(pack(items, _catalog(), config)), sort_keys=True
        )
        assert again == first


def test_split_output_stable_over_50_runs():
    items = [make_item("W", 6, 5, 4, 20.0, quantity=4)]
    config = Config(time_budget_ms=40, max_package_weight_lb=65.0)
    first = json.dumps(result_to_dict(pack(items, _catalog(), config)), sort_keys=True)
    for _ in range(50):
        again = json.dumps(
            result_to_dict(pack(items, _catalog(), config)), sort_keys=True
        )
        assert again == first
