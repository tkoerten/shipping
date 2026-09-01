import { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../util.js";

const SAMPLE_CSV = `order_id,sku,quantity,length,width,height,weight_lb
o1,AMMO-9MM-1000,2,11.5,7,5.5,27.4
o2,AMMO-556-500,3,9,6,4.5,15.8
o3,AMMO-12GA-250,2,12,8,6,22.5
o4,AMMO-45ACP-500,4,8.5,5.5,4,19.2`;

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const header = lines[0].split(",").map((h) => h.trim());
  const idx = (k) => header.indexOf(k);
  const orders = new Map();
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue;
    const c = line.split(",").map((s) => s.trim());
    const oid = c[idx("order_id")] || "order-1";
    if (!orders.has(oid)) orders.set(oid, { order_id: oid, items: [] });
    orders.get(oid).items.push({
      sku: c[idx("sku")],
      quantity: Number(c[idx("quantity")] || 1),
      length: Number(c[idx("length")]),
      width: Number(c[idx("width")]),
      height: Number(c[idx("height")]),
      weight_lb: Number(c[idx("weight_lb")]),
    });
  }
  return [...orders.values()];
}

export default function BatchWhatIf() {
  const [csv, setCsv] = useState(SAMPLE_CSV);
  const [baseline, setBaseline] = useState(null);
  const [whatif, setWhatif] = useState(null);
  const [boxesText, setBoxesText] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.getBoxes().then((r) => setBoxesText(JSON.stringify(r.boxes, null, 2))).catch(() => {});
  }, []);

  const runBaseline = async () => {
    setError("");
    try {
      const orders = parseCsv(csv);
      const r = await api.packBatch({ orders });
      setBaseline(r.aggregate);
    } catch (e) {
      setError(e.message);
    }
  };

  const runWhatIf = async () => {
    setError("");
    try {
      const orders = parseCsv(csv);
      const boxes = JSON.parse(boxesText);
      const r = await api.packBatch({ orders, boxes });
      setWhatif(r.aggregate);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-1">Batch replay &amp; what-if</h2>
        <p className="text-sm text-slate-400">
          Replay historical orders to measure savings. Edit the catalog on the right and
          re-run to answer "would adding a 14×10×6 pay for itself?" — without touching the
          live catalog.
        </p>
      </div>

      {error && (
        <div className="bg-danger/20 border border-danger rounded p-3 text-danger">{error}</div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <h3 className="font-bold mb-2">Orders (CSV)</h3>
          <textarea className="w-full h-64 bg-panel2 border border-edge rounded p-2 font-mono text-xs"
                    value={csv} onChange={(e) => setCsv(e.target.value)} />
          <button className="btn-accent mt-2" onClick={runBaseline}>Run baseline</button>
        </div>
        <div>
          <h3 className="font-bold mb-2">What-if catalog (JSON, not saved)</h3>
          <textarea className="w-full h-64 bg-panel2 border border-edge rounded p-2 font-mono text-xs"
                    value={boxesText} onChange={(e) => setBoxesText(e.target.value)} />
          <button className="btn-ghost mt-2" onClick={runWhatIf}>Run what-if</button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <AggCard title="Baseline" agg={baseline} />
        <AggCard title="What-if" agg={whatif} compare={baseline} />
      </div>
    </div>
  );
}

function AggCard({ title, agg, compare }) {
  if (!agg) {
    return (
      <div className="bg-panel border border-edge rounded-lg p-4 text-slate-500">
        {title}: run to see results.
      </div>
    );
  }
  const delta = (a, b) => {
    if (compare == null || b == null) return null;
    const d = a - b;
    if (Math.abs(d) < 1e-9) return <span className="text-slate-500 text-xs ml-1">=</span>;
    return (
      <span className={`text-xs ml-1 ${d < 0 ? "text-accent" : "text-warn"}`}>
        ({d > 0 ? "+" : ""}{fmt(d, 2)})
      </span>
    );
  };
  return (
    <div className="bg-panel border border-edge rounded-lg p-4 space-y-2">
      <h3 className="font-bold text-lg">{title}</h3>
      <Row label="Orders packed" value={`${agg.orders_packed}/${agg.orders}`} />
      <Row label="Total packages" value={agg.total_packages}
           extra={delta(agg.total_packages, compare?.total_packages)} />
      <Row label="Avg fill" value={`${fmt(agg.average_fill_pct, 1)}%`} />
      <Row label="Total billable lb" value={fmt(agg.total_billable_weight_lb, 1)}
           extra={delta(agg.total_billable_weight_lb, compare?.total_billable_weight_lb)} />
      <Row label="Total box cost" value={`$${fmt(agg.total_box_cost, 2)}`}
           extra={delta(agg.total_box_cost, compare?.total_box_cost)} />
      <div>
        <div className="text-slate-400 text-sm mt-2 mb-1">Box mix</div>
        <div className="flex flex-wrap gap-1">
          {Object.entries(agg.box_mix).map(([name, n]) => (
            <span key={name} className="tag border-edge">{name} ×{n}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, extra }) {
  return (
    <div className="flex justify-between items-baseline">
      <span className="text-slate-400">{label}</span>
      <span className="tabular-nums font-semibold">{value}{extra}</span>
    </div>
  );
}
