// Small shared helpers.
import { useEffect, useState } from "react";

// Stable, distinct color per SKU for the 3D viewer + legend.
const PALETTE = [
  "#39d98a", "#4aa8ff", "#ffb020", "#ff5c5c", "#b57cff",
  "#38e1d0", "#f97316", "#a3e635", "#f472b6", "#60a5fa",
];

const skuColorCache = new Map();
export function colorForSku(sku) {
  if (skuColorCache.has(sku)) return skuColorCache.get(sku);
  let h = 0;
  for (let i = 0; i < sku.length; i++) h = (h * 31 + sku.charCodeAt(i)) >>> 0;
  const c = PALETTE[h % PALETTE.length];
  skuColorCache.set(sku, c);
  return c;
}

export function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function fmt(n, d = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return Number(n).toFixed(d);
}
