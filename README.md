# Cartonization Engine

Real 3D bin packing for an ammunition/firearms e-commerce operation. Given an
order (up to ~20 items, each with L/W/H/weight), it finds the smallest, cheapest
**closeable** shipping box that actually fits them — using an extreme-point 3D
packing heuristic, not volume math.

Items are dense and heavy, so the weight cap binds more often than volume.
Correctness beats cleverness: the engine **never claims a fit it cannot prove**
by an actual non-overlapping, supported, weight-legal placement of every item.
Volume math is only ever used for fast *rejection*.

## Layout

```
packing/        Pure-stdlib engine (zero deps). Importable & testable alone.
  models.py       Dataclasses: Item, ItemUnit, Box, Config, Placement, results.
  geometry.py     Usable dims, orientations, overlap & support checks.
  packer.py       Extreme-point packer + per-box fit checks (the core).
  selection.py    Box-selection ranking + billable weight.
  splitter.py     Multi-package splitting + balancing sweep.
  engine.py       Top-level pack() orchestration + output serialization.
  catalog.py      JSON loaders/savers for boxes / SKUs / config.
  __main__.py     CLI: python -m packing ORDER.json
data/           JSON catalog (boxes, SKUs, config) — edited at runtime, never hardcoded.
api/            FastAPI layer wrapping the engine.
frontend/       React + Vite + Tailwind + Three.js UI.
tests/          pytest suite — the acceptance bar.
```

The engine imports **no** framework code, so `packing/` lifts cleanly into
another project or runs as a batch script against a CSV.

## Engine quickstart

```bash
# Pack an order from the CLI (uses data/boxes.json + data/config.json):
python -m packing path/to/order.json --pretty

# order.json:
# { "items": [ {"sku": "...", "length": 11.5, "width": 7, "height": 5.5,
#               "weight_lb": 27.4, "quantity": 2} ],
#   "config": { "max_package_weight_lb": 65 } }
```

```python
from packing import Item, pack, load_boxes, load_config, result_to_dict

items = [Item(sku="AMMO-9MM-1000", length_in=11.5, width_in=7.0,
              height_in=5.5, weight_lb=27.4, quantity=2)]
result = pack(items, load_boxes(), load_config())
print(result_to_dict(result))
```

## Key rules baked in

- **Units are inches and pounds everywhere**, marked in the field names
  (`length_in`, `weight_lb`) so unit mixing is visible at the call site.
- **Clearance** (linear pad per axis, default 0.25") is the constraint that
  keeps boxes closeable. The dunnage volume reserve (default 15%) is a
  secondary fast-reject check.
- **A weight overflow means open another package — never use a bigger box.**
  A bigger box holds the same weight and bursts the same seam.
- **Every rejected box gets a one-line, human-readable reason** in the output
  `explanation` log. That log settles picker disputes and surfaces real bugs.
- **Deterministic**: the RNG is seeded, so identical input always yields
  identical output. Warehouse staff notice flip-flopping.

## Tests

```bash
python -m pytest -q
```

Acceptance bar: randomized invariant tests (no overlaps, in-bounds, weight cap,
item conservation), known-answer degenerate fixtures (exact fit, 0.01" over,
diagonal-only must fail, 60 lb under a 65 lb cap), the weight-split test (four
20 lb items → two packages), and a 100-run determinism check.

## Running the app

```bash
# 1. Backend (FastAPI on :8000)
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --port 8000

# 2. Frontend (Vite dev server on :5173, proxies /api to :8000)
cd frontend
npm install
npm run dev        # open http://localhost:5173
```

The UI has three tabs:

- **Packer** — left: order entry (SKU autocomplete, quantity steppers,
  paste-a-table import, config sliders with live re-pack); center: Three.js
  viewer with a placement step-through slider that doubles as pack
  instructions; right: chosen box(es), fill %, gross vs. billable weight,
  cost, dunnage estimate, and the full rejection log.
- **Box Catalog** — add/edit/deactivate boxes (the `active` toggle trials or
  retires a size without editing JSON).
- **Batch / What-if** — replay historical orders (CSV) for aggregate box-mix /
  fill / billable-weight stats, and re-run them against a modified catalog to
  answer "would adding a 14×10×6 pay for itself?" without touching the live one.

## Build phases

1. Engine core + CLI + tests ✅
2. Box selection ranking, billable weight, explanation log ✅
3. Multi-package splitting + balancing sweep ✅
4. FastAPI layer ✅
5. React UI (order entry + results) ✅
6. Three.js viewer + placement step-through ✅
7. SKU catalog, batch mode, what-if catalog analysis ✅
