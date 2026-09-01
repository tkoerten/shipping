import { Canvas } from "@react-three/fiber";
import { OrbitControls, Edges } from "@react-three/drei";
import { fmt } from "../util.js";

// Per-UNIT palette (each physical item gets its own color, like the reference
// pack slip) so a picker can match an on-screen block to a box in their hand.
const UNIT_COLORS = [
  "#2f6fd0", "#e03b3b", "#2ea84f", "#f08c1d", "#8a4fd0",
  "#12a7a7", "#d94f9c", "#6aa632", "#3b6ee0", "#c86a1a",
];
const unitColor = (i) => UNIT_COLORS[i % UNIT_COLORS.length];

export default function ContainerSheet({ result }) {
  if (!result) {
    return <div className="p-8 text-slate-500">Pack an order to generate the output sheet.</div>;
  }
  if (!result.ok) {
    return (
      <div className="p-8">
        <div className="bg-warn/20 border border-warn rounded p-4 text-warn">
          Order could not be packed: {result.message}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-100 min-h-full text-slate-800 p-6 space-y-6">
      {result.packages.map((pkg, i) => (
        <Container key={i} pkg={pkg} index={i} />
      ))}
    </div>
  );
}

function Container({ pkg, index }) {
  const ext = pkg.exterior || pkg.interior;
  const volume = ext.length * ext.width * ext.height;
  const itemVol = pkg.items.reduce(
    (s, it) => s + it.orientation[0] * it.orientation[1] * it.orientation[2],
    0
  );
  const voidVol = Math.max(0, volume - itemVol);
  const voidPct = volume > 0 ? (100 * voidVol) / volume : 0;

  // Group placements by SKU, preserving placement order, tracking each unit's
  // color so the table's left bar mirrors the 3D.
  const groups = [];
  const bySku = new Map();
  pkg.items.forEach((it, idx) => {
    const color = unitColor(idx);
    if (!bySku.has(it.sku)) {
      const g = { sku: it.sku, description: it.description, it, colors: [], count: 0 };
      bySku.set(it.sku, g);
      groups.push(g);
    }
    const g = bySku.get(it.sku);
    g.colors.push(color);
    g.count += 1;
  });

  return (
    <div className="bg-white rounded-md shadow-sm border border-slate-300 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2 bg-slate-200 border-b border-slate-300 text-slate-700 font-semibold">
        <span>▥</span> Container # {index + 1}
      </div>

      {/* 3D render */}
      <div className="h-[360px] border-b border-slate-200">
        <Canvas camera={{ position: [ext.length * 1.5, ext.height * 1.7, ext.width * 2.0], fov: 42 }}>
          <color attach="background" args={["#ffffff"]} />
          <ambientLight intensity={0.85} />
          <directionalLight position={[8, 18, 10]} intensity={0.7} />
          <SheetScene pkg={pkg} ext={ext} />
          <OrbitControls makeDefault target={[0, ext.height / 2, 0]} />
        </Canvas>
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-x-12 gap-y-1 px-8 py-4 text-sm">
        <Meta label="Name" value={pkg.box} link />
        <Meta label="Items" value={pkg.items.length} right />
        <Meta label="SKU" value={pkg.box_id} link />
        <Meta label="Weight" value={`${fmt(pkg.gross_weight_lb, 2)} lb`} right />
        <Meta
          label="Dimensions"
          value={`${fmt(ext.length, 3)} L x ${fmt(ext.width, 3)} W x ${fmt(ext.height, 3)} H in`}
        />
        <Meta label="Volume" value={`${fmt(volume, 1)} in³`} right />
        <div />
        <Meta label="Void Space" value={`${fmt(voidVol, 1)} in³ (${fmt(voidPct, 1)}% void)`} right />
      </div>

      {/* Item table */}
      <table className="w-full text-sm border-t border-slate-200">
        <thead>
          <tr className="bg-slate-100 text-slate-500 text-left">
            <th className="py-1.5 pl-4">Product</th>
            <th className="py-1.5 px-2">Goods Type</th>
            <th className="py-1.5 px-2 text-right">Weight</th>
            <th className="py-1.5 px-2 text-right">Length</th>
            <th className="py-1.5 px-2 text-right">Width</th>
            <th className="py-1.5 px-2 text-right pr-4">Height</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.sku} className="border-t border-slate-100 align-top">
              <td className="py-2 pl-0">
                <div className="flex">
                  <ColorBar colors={g.colors} />
                  <div className="pl-3">
                    <div className="font-semibold">
                      {g.count > 1 && <span className="text-slate-400 mr-1">{g.count}×</span>}
                      {g.sku}
                    </div>
                    <div className="text-slate-500">{g.description}</div>
                  </div>
                </div>
              </td>
              <td className="px-2">{g.it.goods_type || "—"}</td>
              <td className="px-2 text-right tabular-nums">{fmt(g.it.weight_lb, 2)} lb</td>
              <td className="px-2 text-right tabular-nums">{fmt(g.it.length_in, 2)} in</td>
              <td className="px-2 text-right tabular-nums">{fmt(g.it.width_in, 2)} in</td>
              <td className="px-2 text-right tabular-nums pr-4">{fmt(g.it.height_in, 2)} in</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ColorBar({ colors }) {
  return (
    <div className="w-2 self-stretch flex flex-col rounded-sm overflow-hidden min-h-[2.5rem]">
      {colors.map((c, i) => (
        <div key={i} className="flex-1" style={{ background: c }} />
      ))}
    </div>
  );
}

function Meta({ label, value, right, link }) {
  return (
    <div className={`flex gap-3 ${right ? "justify-end" : ""}`}>
      <span className="text-slate-400">{label}</span>
      <span className={link ? "text-sky-600" : "text-slate-800"}>{value}</span>
    </div>
  );
}

// Engine axes (x=length, y=width, z=height up) -> three (x, z, y).
function SheetScene({ pkg, ext }) {
  const ox = -ext.length / 2;
  const oy = -ext.width / 2;
  const wall = pkg.wall_thickness_in || 0;

  return (
    <group>
      {/* Grey ground plane (the "shadow" in the reference). */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
        <planeGeometry args={[ext.length * 2.6, ext.width * 2.6]} />
        <meshStandardMaterial color="#b9bcc0" />
      </mesh>

      {/* Cardboard container shell (exterior), drawn as tan edges. */}
      <mesh position={[0, ext.height / 2, 0]}>
        <boxGeometry args={[ext.length, ext.height, ext.width]} />
        <meshStandardMaterial color="#c8a06a" transparent opacity={0.12} />
        <Edges color="#a9782f" />
      </mesh>

      {/* Items, each in its own color, offset inward by the wall thickness. */}
      {pkg.items.map((it, i) => {
        const [x, y, z] = it.position;
        const [dx, dy, dz] = it.orientation;
        const cx = ox + wall + x + dx / 2;
        const cy = wall + z + dz / 2;
        const cz = oy + wall + y + dy / 2;
        const color = unitColor(i);
        return (
          <mesh key={i} position={[cx, cy, cz]}>
            <boxGeometry args={[dx, dz, dy]} />
            <meshStandardMaterial color={color} transparent opacity={0.72} roughness={0.5} />
            <Edges color={color} />
          </mesh>
        );
      })}
    </group>
  );
}
