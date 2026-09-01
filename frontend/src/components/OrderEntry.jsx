import { useState } from "react";
import { colorForSku } from "../util.js";

let rowSeq = 1;
function blankRow() {
  return {
    _id: rowSeq++,
    sku: "",
    description: "",
    quantity: 1,
    length: "",
    width: "",
    height: "",
    weight_lb: "",
    rotation: "free",
    stackable: true,
    max_stack_load_lb: "",
    fragile: false,
    ship_alone: false,
    goods_type: "",
  };
}

export default function OrderEntry({ items, setItems, config, setConfig, skuCatalog }) {
  const update = (id, patch) =>
    setItems(items.map((it) => (it._id === id ? { ...it, ...patch } : it)));
  const remove = (id) => setItems(items.filter((it) => it._id !== id));
  const add = () => setItems([...items, blankRow()]);

  const applySku = (id, sku) => {
    const c = skuCatalog[sku];
    if (c) {
      update(id, {
        sku,
        description: c.description,
        length: c.length,
        width: c.width,
        height: c.height,
        weight_lb: c.weight_lb,
        rotation: c.rotation,
        stackable: c.stackable,
        max_stack_load_lb: c.max_stack_load_lb ?? "",
        fragile: c.fragile,
        ship_alone: c.ship_alone ?? false,
        goods_type: c.goods_type ?? "",
      });
    } else {
      update(id, { sku });
    }
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Order</h2>
        <div className="flex gap-2">
          <PasteImport skuCatalog={skuCatalog} onImport={(rows) => setItems([...items, ...rows])} />
          <button className="btn-accent text-lg" onClick={add}>+ Item</button>
        </div>
      </div>

      {items.length === 0 && (
        <p className="text-slate-500 text-sm">
          Add items by SKU (auto-fills dims &amp; weight) or manually. Re-packs live.
        </p>
      )}

      <div className="space-y-3">
        {items.map((it) => (
          <ItemRow
            key={it._id}
            it={it}
            skuCatalog={skuCatalog}
            onChange={(patch) => update(it._id, patch)}
            onSku={(sku) => applySku(it._id, sku)}
            onRemove={() => remove(it._id)}
          />
        ))}
      </div>

      <ConfigPanel config={config} setConfig={setConfig} />
    </div>
  );
}

function ItemRow({ it, skuCatalog, onChange, onSku, onRemove }) {
  const skus = Object.keys(skuCatalog);
  const color = it.sku ? colorForSku(it.sku) : "#334";
  return (
    <div className="bg-panel rounded-lg border border-edge p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: color }} />
        <input
          list="sku-list"
          className="flex-1 bg-panel2 border border-edge rounded px-2 py-1 font-mono focus:outline-none focus:border-accent2"
          placeholder="SKU"
          value={it.sku}
          onChange={(e) => onSku(e.target.value)}
        />
        <datalist id="sku-list">
          {skus.map((s) => (
            <option key={s} value={s}>{skuCatalog[s].description}</option>
          ))}
        </datalist>
        <Stepper
          value={it.quantity}
          onChange={(q) => onChange({ quantity: q })}
        />
        <button className="text-danger px-2 text-xl leading-none" onClick={onRemove} title="Remove">×</button>
      </div>

      <div className="grid grid-cols-4 gap-2 text-sm">
        <Field label="L" v={it.length} on={(v) => onChange({ length: v })} />
        <Field label="W" v={it.width} on={(v) => onChange({ width: v })} />
        <Field label="H" v={it.height} on={(v) => onChange({ height: v })} />
        <Field label="lb" v={it.weight_lb} on={(v) => onChange({ weight_lb: v })} />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <select
          className="bg-panel2 border border-edge rounded px-2 py-1"
          value={it.rotation}
          onChange={(e) => onChange({ rotation: e.target.value })}
        >
          <option value="free">free rotate</option>
          <option value="upright">upright</option>
          <option value="fixed">fixed</option>
        </select>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={it.stackable !== false}
                 onChange={(e) => onChange({ stackable: e.target.checked })} />
          stackable
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={!!it.fragile}
                 onChange={(e) => onChange({ fragile: e.target.checked })} />
          fragile
        </label>
        <label className="flex items-center gap-1">
          max load
          <input
            className="num-input w-16"
            placeholder="∞"
            value={it.max_stack_load_lb}
            onChange={(e) => onChange({ max_stack_load_lb: e.target.value })}
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label className="flex items-center gap-1" title="Must ship in its own package (pack-as-is)">
          <input type="checkbox" checked={!!it.ship_alone}
                 onChange={(e) => onChange({ ship_alone: e.target.checked })} />
          ship alone
        </label>
        <label className="flex items-center gap-1" title="Hazmat / commodity class shown on the pack slip">
          goods
          <input className="bg-panel2 border border-edge rounded px-2 py-1 w-20"
                 placeholder="ORM-D"
                 value={it.goods_type || ""}
                 onChange={(e) => onChange({ goods_type: e.target.value })} />
        </label>
      </div>
    </div>
  );
}

function Field({ label, v, on }) {
  return (
    <label className="flex flex-col">
      <span className="text-slate-400 text-xs">{label}</span>
      <input className="num-input" inputMode="decimal" value={v}
             onChange={(e) => on(e.target.value)} />
    </label>
  );
}

function Stepper({ value, onChange }) {
  const n = Number(value) || 1;
  return (
    <div className="flex items-center border border-edge rounded overflow-hidden">
      <button className="px-2 bg-panel2 text-lg" onClick={() => onChange(Math.max(1, n - 1))}>−</button>
      <input
        className="w-12 text-center bg-ink tabular-nums py-1"
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, "") || 1)}
      />
      <button className="px-2 bg-panel2 text-lg" onClick={() => onChange(n + 1)}>+</button>
    </div>
  );
}

function ConfigPanel({ config, setConfig }) {
  const set = (k, v) => setConfig({ ...config, [k]: v });
  return (
    <div className="bg-panel rounded-lg border border-edge p-4 space-y-4">
      <h3 className="font-bold text-lg">Config</h3>
      <Slider label="Dunnage reserve" suffix="%" min={0} max={40} step={1}
        value={Math.round(config.dunnage_reserve_pct * 100)}
        onChange={(v) => set("dunnage_reserve_pct", v / 100)} />
      <Slider label="Clearance" suffix="in" min={0} max={1} step={0.05}
        value={config.clearance_in}
        onChange={(v) => set("clearance_in", v)} />
      <Slider label="Max package weight" suffix="lb" min={5} max={150} step={1}
        value={config.max_package_weight_lb}
        onChange={(v) => set("max_package_weight_lb", v)} />
      <Slider label="Dim divisor" suffix="" min={100} max={200} step={1}
        value={config.dim_divisor}
        onChange={(v) => set("dim_divisor", v)} />
      <div className="flex items-center gap-4 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={config.allow_split}
                 onChange={(e) => set("allow_split", e.target.checked)} />
          allow split
        </label>
        <label className="flex items-center gap-2">
          max packages
          <input className="num-input w-16" value={config.max_packages}
                 onChange={(e) => set("max_packages", Number(e.target.value) || 1)} />
        </label>
      </div>
    </div>
  );
}

function Slider({ label, suffix, min, max, step, value, onChange }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-slate-300">{label}</span>
        <span className="tabular-nums font-mono text-accent">
          {value}
          {suffix}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <input type="range" className="flex-1" min={min} max={max} step={step}
               value={value} onChange={(e) => onChange(Number(e.target.value))} />
        <input className="num-input w-20" value={value}
               onChange={(e) => onChange(Number(e.target.value))} />
      </div>
    </div>
  );
}

function PasteImport({ skuCatalog, onImport }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");

  const parse = () => {
    const rows = [];
    for (const line of text.split(/\r?\n/)) {
      const t = line.trim();
      if (!t) continue;
      const cols = t.split(/[\t,]/).map((c) => c.trim());
      // Two shapes: "SKU  qty" (dims from catalog) or
      // "sku qty L W H weight".
      const [sku, qty, l, w, h, wt] = cols;
      const base = blankRow();
      base.sku = sku;
      base.quantity = Number(qty) || 1;
      const c = skuCatalog[sku];
      if (l && w && h) {
        base.length = Number(l); base.width = Number(w);
        base.height = Number(h); base.weight_lb = Number(wt) || 0;
      } else if (c) {
        base.description = c.description;
        base.length = c.length; base.width = c.width;
        base.height = c.height; base.weight_lb = c.weight_lb;
        base.rotation = c.rotation; base.fragile = c.fragile;
        base.max_stack_load_lb = c.max_stack_load_lb ?? "";
      }
      rows.push(base);
    }
    onImport(rows);
    setText("");
    setOpen(false);
  };

  return (
    <>
      <button className="btn-ghost" onClick={() => setOpen(true)}>Paste</button>
      {open && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
             onClick={() => setOpen(false)}>
          <div className="bg-panel border border-edge rounded-lg p-4 w-[520px]"
               onClick={(e) => e.stopPropagation()}>
            <h3 className="font-bold mb-2">Paste a table</h3>
            <p className="text-sm text-slate-400 mb-2">
              One row per line, tab- or comma-separated:
              <br /><code>SKU, qty</code> (dims from catalog) or
              <code> sku, qty, L, W, H, weight</code>
            </p>
            <textarea
              className="w-full h-40 bg-panel2 border border-edge rounded p-2 font-mono text-sm"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={"AMMO-9MM-1000, 2\nAMMO-556-500, 1, 9, 6, 4.5, 15.8"}
            />
            <div className="flex justify-end gap-2 mt-3">
              <button className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
              <button className="btn-accent" onClick={parse}>Import</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
