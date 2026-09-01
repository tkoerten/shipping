"""API smoke tests. Skipped if FastAPI/httpx are not installed."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_get_config_has_defaults():
    cfg = client.get("/api/config").json()
    assert cfg["max_package_weight_lb"] == 65.0
    assert cfg["dim_divisor"] == 139.0


def test_get_boxes_and_items():
    boxes = client.get("/api/boxes").json()["boxes"]
    assert any(b["name"] == "LQ 13x9x7" for b in boxes)
    # -test boxes are carried but inactive by default.
    inactive = [b for b in boxes if not b["active"]]
    assert any("test" in b["id"] for b in inactive)
    items = client.get("/api/items").json()["items"]
    assert "AMMO-9MM-1000" in items


def test_pack_single_item():
    r = client.post("/api/pack", json={
        "items": [{"sku": "AMMO-9MM-1000", "length": 11.5, "width": 7.0,
                   "height": 5.5, "weight_lb": 27.4, "quantity": 1}]
    })
    j = r.json()
    assert j["ok"]
    assert j["totals"]["packages"] == 1
    assert j["explanation"]  # rejection/selection log is present


def test_pack_weight_split_yields_two_packages():
    r = client.post("/api/pack", json={
        "items": [{"sku": "W", "length": 6, "width": 5, "height": 4,
                   "weight_lb": 20, "quantity": 4}]
    })
    j = r.json()
    assert j["ok"]
    assert j["totals"]["packages"] == 2


def test_batch_csv_upload():
    csv_body = (
        "order_id,sku,quantity,length,width,height,weight_lb\n"
        "o1,AMMO-9MM-1000,2,11.5,7,5.5,27.4\n"
        "o2,AMMO-556-500,1,9,6,4.5,15.8\n"
    )
    r = client.post("/api/pack/batch", content=csv_body,
                    headers={"content-type": "text/csv"})
    j = r.json()
    assert len(j["results"]) == 2
    assert j["aggregate"]["orders_packed"] >= 1


def test_put_boxes_rejects_duplicate_ids(tmp_path, monkeypatch):
    # Duplicate ids should 422 without touching disk.
    dup = {
        "id": "x", "name": "X",
        "interior": {"length": 10, "width": 8, "height": 6},
    }
    r = client.put("/api/boxes", json={"boxes": [dup, dup]})
    assert r.status_code == 422
