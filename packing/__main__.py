"""CLI: python -m packing ORDER.json [--boxes data/boxes.json] [--pretty]

ORDER.json is either:
  { "items": [ {Item}, ... ], "config": { ...optional overrides... } }
or a bare list of Item dicts.

Runs the engine against the box catalog and prints the result document as JSON.
This exists so the engine is usable as a batch script with no web server.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import config_from_dict, item_from_dict, load_boxes, load_config
from .engine import pack, result_to_dict
from .models import Item


def _load_order(path: Path) -> tuple[list[Item], dict]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        raw_items, raw_config = data, {}
    else:
        raw_items = data.get("items", [])
        raw_config = data.get("config", {})
    items = [item_from_dict(d) for d in raw_items]
    return items, raw_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m packing")
    parser.add_argument("order", type=Path, help="path to order JSON")
    parser.add_argument("--boxes", type=Path, default=None, help="box catalog JSON")
    parser.add_argument("--config", type=Path, default=None, help="config JSON")
    parser.add_argument("--pretty", action="store_true", help="indent output")
    args = parser.parse_args(argv)

    items, raw_config = _load_order(args.order)
    boxes = load_boxes(args.boxes)

    base = load_config(args.config) if args.config else load_config()
    # Merge base config with per-order overrides.
    merged = {**{
        "dunnage_reserve_pct": base.dunnage_reserve_pct,
        "clearance_in": base.clearance_in,
        "max_package_weight_lb": base.max_package_weight_lb,
        "dim_divisor": base.dim_divisor,
        "allow_split": base.allow_split,
        "max_packages": base.max_packages,
        "time_budget_ms": base.time_budget_ms,
        "seed": base.seed,
    }, **raw_config}
    config = config_from_dict(merged)

    result = pack(items, boxes, config)
    out = result_to_dict(result)
    print(json.dumps(out, indent=2 if args.pretty else None))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
