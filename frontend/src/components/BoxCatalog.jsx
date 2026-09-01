import { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../util.js";

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default function BoxCatalog() {
  const [boxes, setBoxes] = useState([]);
  const [status, setStatus] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    api.getBoxes().then((r) => setBoxes(r.boxes)).catch((e) => setStatus(e.message));
  }, []);

  const update = (idx, patch) => {
    setBoxes(boxes.map((b, i) => (i === idx ? { ...b, ...patch } : b)));
    setDirty(true);
  };
  const updateDim = (idx, axis, v) => {
    const b = boxes[idx];
    update(idx, { interior: { ...b.interior, [axis]: Number(v) } });
  };
  const addBox = () => {
    setBoxes([
      ...boxes,
      {
        id: `box-${Date.now()}`,
        name: "New Box",
        interior: { length: 10, width: 8, height: 6 },
        dimensions_are: "interior",
        wall_thickness: 0.125,
        tare_weight_lb: 0.4,
        cost: 0.5,
        max_gross_weight_lb: 65,
        active: true,
        notes: "",
      },
    ]);
    setDirty(true);
  };
  const removeBox = (idx) => {
    setBoxes(boxes.filter((_, i) => i !== idx));
    setDirty(true);
  };

  const save = async () => {
    try {
      const normalized = boxes.map((b) => ({
        ...b,
        id: b.id || slugify(b.name),
        max_gross_weight_lb:
          b.max_gross_weight_lb === "" || b.max_gross_weight_lb == null
            ? null
            : Number(b.max_gross_weight_lb),
      }));
      const r = await api.putBoxes(normalized);
      setBoxes(r.boxes);
      setDirty(false);
      setStatus("Saved.");
      setTimeout(() => setStatus(""), 2000);
    } catch (e) {
      setStatus(e.message);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Box Catalog</h2>
        <div className="flex items-center gap-3">
          {status && <span className="text-sm text-accent">{status}</span>}
          <button className="btn-ghost" onClick={addBox}>+ Box</button>
          <button className={dirty ? "btn-accent" : "btn-ghost opacity-60"} onClick={save} disabled={!dirty}>
            Save catalog
          </button>
        </div>
      </div>

      <p className="text-sm text-slate-400">
        Toggle <b>active</b> to trial or retire a size without editing JSON. The two
        <code className="mx-1">-test</code> records ship inactive by default. Dimensions are
        interior unless a box is marked exterior (walls are then subtracted before packing).
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead className="text-slate-400 text-left">
            <tr className="border-b border-edge">
              <th className="p-2">Active</th>
              <th className="p-2">Name</th>
              <th className="p-2">L</th>
              <th className="p-2">W</th>
              <th className="p-2">H</th>
              <th className="p-2">Dims</th>
              <th className="p-2">Wall</th>
              <th className="p-2">Tare</th>
              <th className="p-2">Cost</th>
              <th className="p-2">Max gross</th>
              <th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {boxes.map((b, i) => (
              <tr key={i} className={`border-b border-edge ${b.active ? "" : "opacity-50"}`}>
                <td className="p-2">
                  <input type="checkbox" checked={b.active}
                         onChange={(e) => update(i, { active: e.target.checked })} />
                </td>
                <td className="p-2">
                  <input className="num-input text-left w-40" value={b.name}
                         onChange={(e) => update(i, { name: e.target.value })} />
                </td>
                <td className="p-2"><input className="num-input w-16" value={b.interior.length}
                       onChange={(e) => updateDim(i, "length", e.target.value)} /></td>
                <td className="p-2"><input className="num-input w-16" value={b.interior.width}
                       onChange={(e) => updateDim(i, "width", e.target.value)} /></td>
                <td className="p-2"><input className="num-input w-16" value={b.interior.height}
                       onChange={(e) => updateDim(i, "height", e.target.value)} /></td>
                <td className="p-2">
                  <select className="bg-panel2 border border-edge rounded px-1 py-1"
                          value={b.dimensions_are}
                          onChange={(e) => update(i, { dimensions_are: e.target.value })}>
                    <option value="interior">interior</option>
                    <option value="exterior">exterior</option>
                  </select>
                </td>
                <td className="p-2"><input className="num-input w-16" value={b.wall_thickness}
                       onChange={(e) => update(i, { wall_thickness: Number(e.target.value) })} /></td>
                <td className="p-2"><input className="num-input w-16" value={b.tare_weight_lb}
                       onChange={(e) => update(i, { tare_weight_lb: Number(e.target.value) })} /></td>
                <td className="p-2"><input className="num-input w-16" value={b.cost}
                       onChange={(e) => update(i, { cost: Number(e.target.value) })} /></td>
                <td className="p-2"><input className="num-input w-20" value={b.max_gross_weight_lb ?? ""}
                       placeholder="global"
                       onChange={(e) => update(i, { max_gross_weight_lb: e.target.value })} /></td>
                <td className="p-2 text-right">
                  <button className="text-danger px-2 text-lg" onClick={() => removeBox(i)}>×</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
