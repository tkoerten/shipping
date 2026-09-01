import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "./api.js";
import { useDebounced } from "./util.js";
import OrderEntry from "./components/OrderEntry.jsx";
import Results from "./components/Results.jsx";
import PackViewer from "./components/PackViewer.jsx";
import BoxCatalog from "./components/BoxCatalog.jsx";
import BatchWhatIf from "./components/BatchWhatIf.jsx";
import ContainerSheet from "./components/ContainerSheet.jsx";

const TABS = [
  { id: "packer", label: "Packer" },
  { id: "output", label: "Output Sheet" },
  { id: "boxes", label: "Box Catalog" },
  { id: "batch", label: "Batch / What-if" },
];

const DEFAULT_CONFIG = {
  dunnage_reserve_pct: 0.15,
  clearance_in: 0.25,
  max_package_weight_lb: 65,
  dim_divisor: 139,
  allow_split: true,
  max_packages: 5,
};

export default function App() {
  const [tab, setTab] = useState("packer");
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [skuCatalog, setSkuCatalog] = useState({});
  const [items, setItems] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [packing, setPacking] = useState(false);
  const [activePkg, setActivePkg] = useState(0);

  // Load saved defaults + SKU catalog once.
  useEffect(() => {
    api.getConfig().then((c) => setConfig(c)).catch(() => {});
    api.getItems().then((r) => setSkuCatalog(r.items)).catch(() => {});
  }, []);

  // Live re-pack (debounced) whenever items or config change.
  const debouncedItems = useDebounced(items, 300);
  const debouncedConfig = useDebounced(config, 300);

  const runPack = useCallback(async (its, cfg) => {
    const valid = its.filter(
      (i) => i.sku && i.length > 0 && i.width > 0 && i.height > 0
    );
    if (valid.length === 0) {
      setResult(null);
      setError(null);
      return;
    }
    setPacking(true);
    try {
      const payload = valid.map((i) => ({
        sku: i.sku,
        description: i.description || "",
        quantity: Number(i.quantity) || 1,
        length: Number(i.length),
        width: Number(i.width),
        height: Number(i.height),
        weight_lb: Number(i.weight_lb),
        rotation: i.rotation || "free",
        stackable: i.stackable !== false,
        max_stack_load_lb:
          i.max_stack_load_lb === "" || i.max_stack_load_lb == null
            ? null
            : Number(i.max_stack_load_lb),
        fragile: !!i.fragile,
        ship_alone: !!i.ship_alone,
        exclusion_group: i.exclusion_group || null,
        goods_type: i.goods_type || "",
      }));
      const r = await api.pack(payload, cfg);
      setResult(r);
      setError(null);
      setActivePkg(0);
    } catch (e) {
      setError(e.message);
      setResult(null);
    } finally {
      setPacking(false);
    }
  }, []);

  useEffect(() => {
    runPack(debouncedItems, debouncedConfig);
  }, [debouncedItems, debouncedConfig, runPack]);

  return (
    <div className="h-full flex flex-col">
      <header className="flex items-center gap-6 px-6 py-3 border-b border-edge bg-panel">
        <div className="text-2xl font-black tracking-tight">
          <span className="text-accent">◧</span> Cartonization Engine
        </div>
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-t font-semibold text-lg ${
                tab === t.id
                  ? "bg-ink text-accent border-b-2 border-accent"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="ml-auto text-sm text-slate-400">
          {packing ? "packing…" : result ? `${result.totals.packages} pkg` : "—"}
        </div>
      </header>

      {tab === "packer" && (
        <div className="flex-1 grid grid-cols-[minmax(360px,1fr)_1.4fr_minmax(360px,1fr)] gap-px bg-edge overflow-hidden">
          <section className="bg-ink overflow-y-auto">
            <OrderEntry
              items={items}
              setItems={setItems}
              config={config}
              setConfig={setConfig}
              skuCatalog={skuCatalog}
            />
          </section>
          <section className="bg-ink overflow-hidden flex flex-col">
            <PackViewer
              result={result}
              activePkg={activePkg}
              setActivePkg={setActivePkg}
            />
          </section>
          <section className="bg-ink overflow-y-auto">
            <Results result={result} error={error} activePkg={activePkg} setActivePkg={setActivePkg} />
          </section>
        </div>
      )}

      {tab === "output" && (
        <div className="flex-1 overflow-y-auto">
          <ContainerSheet result={result} />
        </div>
      )}

      {tab === "boxes" && (
        <div className="flex-1 overflow-y-auto bg-ink">
          <BoxCatalog />
        </div>
      )}

      {tab === "batch" && (
        <div className="flex-1 overflow-y-auto bg-ink">
          <BatchWhatIf />
        </div>
      )}
    </div>
  );
}
