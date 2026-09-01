"""FastAPI layer wrapping the cartonization engine.

The engine stays a pure-stdlib library; this module only translates HTTP <->
engine and persists the JSON catalog. /api/pack is kept fast and stateless so
the storefront can quote shipping before checkout.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from packing import (
    Box,
    Config,
    Item,
    load_boxes,
    load_config,
    load_sku_catalog,
    pack,
    result_to_dict,
    save_boxes,
    save_sku_catalog,
)
from packing.catalog import (
    DATA_DIR,
    box_to_dict,
    config_to_dict,
    item_from_dict,
    item_to_dict,
)

from .schemas import (
    BatchRequest,
    BoxesPut,
    ConfigPut,
    ItemsPut,
    PackRequest,
)

app = FastAPI(title="Cartonization Engine", version="0.1.0")

# The UI is served from Vite's dev server in development; allow it to call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Pack
# --------------------------------------------------------------------------- #
@app.post("/api/pack")
def api_pack(req: PackRequest) -> dict[str, Any]:
    base = load_config()
    config = req.config.to_config(base) if req.config else base
    items = [i.to_item() for i in req.items]
    try:
        result = pack(items, load_boxes(), config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result_to_dict(result)


# --------------------------------------------------------------------------- #
# Batch pack (JSON body or CSV upload) + aggregate stats
# --------------------------------------------------------------------------- #
@app.post("/api/pack/batch")
async def api_pack_batch(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    base = load_config()

    if "text/csv" in content_type or "application/csv" in content_type:
        raw = (await request.body()).decode("utf-8")
        orders = _orders_from_csv(raw)
        override_boxes = None
        batch_config = base
    else:
        payload = await request.json()
        req = BatchRequest.model_validate(payload)
        batch_config = req.config.to_config(base) if req.config else base
        override_boxes = (
            [b.to_box() for b in req.boxes] if req.boxes is not None else None
        )
        orders = []
        for o in req.orders:
            cfg = o.config.to_config(batch_config) if o.config else batch_config
            orders.append((o.order_id, [i.to_item() for i in o.items], cfg))

    boxes = override_boxes if override_boxes is not None else load_boxes()

    results = []
    for idx, (order_id, items, cfg) in enumerate(orders):
        try:
            res = pack(items, boxes, cfg)
            results.append({
                "order_id": order_id or f"order-{idx + 1}",
                "result": result_to_dict(res),
            })
        except ValueError as exc:
            results.append({
                "order_id": order_id or f"order-{idx + 1}",
                "error": str(exc),
            })

    return {"results": results, "aggregate": _aggregate(results)}


def _orders_from_csv(raw: str) -> list[tuple[str | None, list[Item], Config]]:
    """Parse a CSV where each row is one item line, grouped by order_id.

    Columns: order_id, sku, quantity, length, width, height, weight_lb
    (rotation, stackable, max_stack_load_lb, fragile optional).
    """
    reader = csv.DictReader(io.StringIO(raw))
    grouped: dict[str, list[Item]] = {}
    order_sequence: list[str] = []
    base = load_config()
    for row in reader:
        oid = (row.get("order_id") or "order-1").strip()
        if oid not in grouped:
            grouped[oid] = []
            order_sequence.append(oid)
        d = {
            "sku": row.get("sku", ""),
            "description": row.get("description", ""),
            "quantity": int(row.get("quantity", 1) or 1),
            "length": float(row["length"]),
            "width": float(row["width"]),
            "height": float(row["height"]),
            "weight_lb": float(row["weight_lb"]),
        }
        for opt in ("rotation", "stackable", "max_stack_load_lb", "fragile"):
            if row.get(opt):
                d[opt] = row[opt]
        if "stackable" in d:
            d["stackable"] = str(d["stackable"]).lower() in ("1", "true", "yes")
        if "fragile" in d:
            d["fragile"] = str(d["fragile"]).lower() in ("1", "true", "yes")
        if "max_stack_load_lb" in d:
            d["max_stack_load_lb"] = float(d["max_stack_load_lb"])
        grouped[oid].append(item_from_dict(d))
    return [(oid, grouped[oid], base) for oid in order_sequence]


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    box_mix: dict[str, int] = {}
    total_billable = 0.0
    total_cost = 0.0
    fills: list[float] = []
    total_packages = 0
    ok_orders = 0
    for r in results:
        res = r.get("result")
        if not res or not res.get("ok"):
            continue
        ok_orders += 1
        total_packages += res["totals"]["packages"]
        total_billable += res["totals"]["billable_weight_lb"]
        total_cost += res["totals"]["box_cost"]
        for pkg in res["packages"]:
            box_mix[pkg["box"]] = box_mix.get(pkg["box"], 0) + 1
            fills.append(pkg["fill_pct"])
    return {
        "orders": len(results),
        "orders_packed": ok_orders,
        "total_packages": total_packages,
        "box_mix": box_mix,
        "average_fill_pct": round(sum(fills) / len(fills), 1) if fills else 0.0,
        "total_billable_weight_lb": round(total_billable, 2),
        "total_box_cost": round(total_cost, 2),
    }


# --------------------------------------------------------------------------- #
# Boxes catalog
# --------------------------------------------------------------------------- #
@app.get("/api/boxes")
def api_get_boxes() -> dict[str, Any]:
    return {"boxes": [box_to_dict(b) for b in load_boxes()]}


@app.put("/api/boxes")
def api_put_boxes(body: BoxesPut) -> dict[str, Any]:
    boxes = [b.to_box() for b in body.boxes]
    _validate_unique_ids([b.id for b in boxes], "box")
    save_boxes(boxes)
    return {"boxes": [box_to_dict(b) for b in boxes]}


# --------------------------------------------------------------------------- #
# SKU catalog
# --------------------------------------------------------------------------- #
@app.get("/api/items")
def api_get_items() -> dict[str, Any]:
    catalog = load_sku_catalog()
    return {"items": {sku: item_to_dict(it) for sku, it in catalog.items()}}


@app.put("/api/items")
def api_put_items(body: ItemsPut) -> dict[str, Any]:
    catalog = {sku: i.to_item() for sku, i in body.items.items()}
    save_sku_catalog(catalog)
    return {"items": {sku: item_to_dict(it) for sku, it in catalog.items()}}


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@app.get("/api/config")
def api_get_config() -> dict[str, Any]:
    return config_to_dict(load_config())


@app.put("/api/config")
def api_put_config(body: ConfigPut) -> dict[str, Any]:
    cfg = Config(
        dunnage_reserve_pct=body.dunnage_reserve_pct,
        clearance_in=body.clearance_in,
        max_package_weight_lb=body.max_package_weight_lb,
        dim_divisor=body.dim_divisor,
        allow_split=body.allow_split,
        max_packages=body.max_packages,
    )
    (DATA_DIR / "config.json").write_text(json.dumps(config_to_dict(cfg), indent=2))
    return config_to_dict(cfg)


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok"}


def _validate_unique_ids(ids: list[str], label: str) -> None:
    seen = set()
    for i in ids:
        if i in seen:
            raise HTTPException(status_code=422, detail=f"duplicate {label} id: {i}")
        seen.add(i)
