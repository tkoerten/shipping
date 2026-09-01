import { useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Edges, Html } from "@react-three/drei";
import { colorForSku } from "../util.js";

// Engine axes: x=length, y=width, z=height(up). Three.js uses Y as up, so we
// map engine (x, y, z) -> three (x, z, y).
export default function PackViewer({ result, activePkg }) {
  const pkg = result?.ok ? result.packages[activePkg] : null;
  const count = pkg ? pkg.items.length : 0;
  const [step, setStep] = useState(count);
  const [playing, setPlaying] = useState(false);

  useEffect(() => setStep(count), [count, activePkg]);

  useEffect(() => {
    if (!playing) return;
    if (step >= count) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setStep((s) => Math.min(count, s + 1)), 600);
    return () => clearTimeout(t);
  }, [playing, step, count]);

  if (!pkg) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-600">
        {result && !result.ok ? "No packable arrangement" : "3D viewer"}
      </div>
    );
  }

  const inter = pkg.interior; // {length,width,height}
  const maxDim = Math.max(inter.length, inter.width, inter.height);

  return (
    <div className="flex-1 flex flex-col">
      <div className="flex-1 relative">
        <Canvas camera={{ position: [maxDim * 1.6, maxDim * 1.4, maxDim * 1.9], fov: 45 }}>
          <color attach="background" args={["#0b0f14"]} />
          <ambientLight intensity={0.7} />
          <directionalLight position={[10, 20, 10]} intensity={0.8} />
          <Scene pkg={pkg} inter={inter} step={step} />
          <OrbitControls makeDefault target={[0, inter.height / 2, 0]} />
        </Canvas>
        <div className="absolute top-2 left-2 text-sm bg-panel/80 rounded px-2 py-1 border border-edge">
          {pkg.box} · {inter.length}×{inter.width}×{inter.height} in
        </div>
      </div>

      <div className="p-3 border-t border-edge bg-panel flex items-center gap-3">
        <button className="btn-ghost" onClick={() => { setStep(0); setPlaying(true); }}>
          ▶ Play
        </button>
        <input
          type="range" className="flex-1" min={0} max={count} step={1}
          value={step}
          onChange={(e) => { setPlaying(false); setStep(Number(e.target.value)); }}
        />
        <span className="tabular-nums font-mono text-accent w-20 text-right">
          {step}/{count} placed
        </span>
      </div>
    </div>
  );
}

function Scene({ pkg, inter, step }) {
  // Center the container on the origin: shift by -half on each axis.
  const ox = -inter.length / 2;
  const oy = -inter.width / 2;
  const oz = 0; // keep floor at y=0

  const visible = useMemo(() => pkg.items.slice(0, step), [pkg.items, step]);

  return (
    <group>
      {/* Container wireframe (interior). */}
      <mesh position={[0, inter.height / 2, 0]}>
        <boxGeometry args={[inter.length, inter.height, inter.width]} />
        <meshBasicMaterial transparent opacity={0.03} color="#4aa8ff" />
        <Edges color="#4aa8ff" />
      </mesh>

      {/* Floor grid for depth reference. */}
      <gridHelper args={[Math.max(inter.length, inter.width) * 1.4, 12, "#2b3644", "#1c242e"]} />

      {visible.map((it, i) => {
        const [x, y, z] = it.position;
        const [dx, dy, dz] = it.orientation;
        const color = colorForSku(it.sku);
        // engine (x,y,z)+extent -> three center (x+dx/2, z+dz/2, y+dy/2)
        const cx = ox + x + dx / 2;
        const cy = oz + z + dz / 2;
        const cz = oy + y + dy / 2;
        const isLast = i === visible.length - 1;
        return (
          <mesh key={i} position={[cx, cy, cz]}>
            <boxGeometry args={[dx, dz, dy]} />
            <meshStandardMaterial
              color={color}
              transparent
              opacity={isLast ? 0.85 : 0.55}
              roughness={0.6}
            />
            <Edges color={color} />
            {isLast && (
              <Html center distanceFactor={Math.max(inter.length, inter.width) * 2}>
                <div className="px-1.5 py-0.5 rounded bg-ink/90 border text-xs whitespace-nowrap"
                     style={{ borderColor: color, color }}>
                  {it.sku}
                </div>
              </Html>
            )}
          </mesh>
        );
      })}
    </group>
  );
}
