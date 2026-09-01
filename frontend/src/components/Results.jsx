import { colorForSku, fmt } from "../util.js";

export default function Results({ result, error, activePkg, setActivePkg }) {
  if (error) {
    return (
      <div className="p-4">
        <div className="bg-danger/20 border border-danger rounded p-3 text-danger">
          {error}
        </div>
      </div>
    );
  }
  if (!result) {
    return <div className="p-6 text-slate-500">Add items to see results.</div>;
  }

  if (!result.ok) {
    return (
      <div className="p-4 space-y-4">
        <div className="bg-warn/20 border border-warn rounded p-3 text-warn font-semibold">
          Could not pack: {result.message}
        </div>
        <RejectionLog explanation={result.explanation} />
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      <div className="grid grid-cols-3 gap-2">
        <Stat label="Packages" value={result.totals.packages} big />
        <Stat label="Billable lb" value={fmt(result.totals.billable_weight_lb, 1)} big />
        <Stat label="Box cost" value={`$${fmt(result.totals.box_cost, 2)}`} big />
      </div>

      <div className="space-y-3">
        {result.packages.map((pkg, i) => (
          <PackageCard
            key={i}
            pkg={pkg}
            idx={i}
            active={i === activePkg}
            onClick={() => setActivePkg(i)}
          />
        ))}
      </div>

      <RejectionLog explanation={result.explanation} />
    </div>
  );
}

function PackageCard({ pkg, idx, active, onClick }) {
  return (
    <div
      onClick={onClick}
      className={`rounded-lg border p-3 cursor-pointer transition-colors ${
        active ? "border-accent bg-panel" : "border-edge bg-panel/60 hover:border-accent2"
      }`}
    >
      <div className="flex items-baseline justify-between">
        <div className="text-lg font-bold">
          <span className="text-slate-400 text-sm mr-2">#{idx + 1}</span>
          {pkg.box}
        </div>
        <div className="text-sm text-slate-400">${fmt(pkg.box_cost, 2)}</div>
      </div>

      <div className="grid grid-cols-3 gap-2 mt-2 text-sm">
        <Mini label="Fill" value={`${fmt(pkg.fill_pct, 0)}%`} />
        <Mini label="Gross" value={`${fmt(pkg.gross_weight_lb, 1)} lb`} />
        <Mini
          label="Billable"
          value={`${fmt(pkg.billable_weight_lb, 1)} lb`}
          hint={pkg.billable_weight_lb > pkg.gross_weight_lb ? "dim" : ""}
        />
      </div>

      <FillBar pct={pkg.fill_pct} />

      <div className="text-xs text-slate-400 mt-2">
        void {fmt(pkg.void_volume_cu_in, 0)} cu-in · dunnage {pkg.estimated_dunnage}
      </div>

      <div className="mt-2 flex flex-wrap gap-1">
        {summarize(pkg.items).map((s) => (
          <span key={s.sku} className="tag border-edge flex items-center gap-1"
                style={{ borderColor: colorForSku(s.sku) }}>
            <span className="w-2 h-2 rounded-sm" style={{ background: colorForSku(s.sku) }} />
            {s.sku} ×{s.count}
          </span>
        ))}
      </div>
    </div>
  );
}

function summarize(items) {
  const m = new Map();
  for (const it of items) m.set(it.sku, (m.get(it.sku) || 0) + 1);
  return [...m.entries()].map(([sku, count]) => ({ sku, count }));
}

function FillBar({ pct }) {
  const p = Math.min(100, pct);
  const color = p > 80 ? "#ff5c5c" : p > 55 ? "#ffb020" : "#39d98a";
  return (
    <div className="h-2 bg-panel2 rounded mt-2 overflow-hidden">
      <div className="h-full rounded" style={{ width: `${p}%`, background: color }} />
    </div>
  );
}

function Stat({ label, value, big }) {
  return (
    <div className="bg-panel rounded-lg border border-edge p-3 text-center">
      <div className="text-slate-400 text-xs uppercase tracking-wide">{label}</div>
      <div className={big ? "text-2xl font-black tabular-nums" : "text-lg"}>{value}</div>
    </div>
  );
}

function Mini({ label, value, hint }) {
  return (
    <div>
      <div className="text-slate-400 text-xs">{label}</div>
      <div className="tabular-nums font-semibold">
        {value}
        {hint && <span className="text-warn text-xs ml-1">({hint})</span>}
      </div>
    </div>
  );
}

function RejectionLog({ explanation }) {
  if (!explanation || explanation.length === 0) return null;
  return (
    <div className="bg-panel rounded-lg border border-edge p-3">
      <h3 className="font-bold mb-2">Why these boxes</h3>
      <ul className="space-y-1 text-sm font-mono">
        {explanation.map((line, i) => {
          const selected = line.includes("selected:");
          const fits = line.includes("fits:");
          return (
            <li key={i}
                className={
                  selected ? "text-accent"
                    : fits ? "text-accent2"
                    : "text-slate-400"
                }>
              {selected ? "✓ " : fits ? "· " : "✗ "}
              {line}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
