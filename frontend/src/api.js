// Thin client for the FastAPI backend. In dev, Vite proxies /api to :8000.

const BASE = "";

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch (_) {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  pack: (items, config) =>
    req("/api/pack", { method: "POST", body: JSON.stringify({ items, config }) }),

  packBatch: (payload) =>
    req("/api/pack/batch", { method: "POST", body: JSON.stringify(payload) }),

  packBatchCsv: (csvText) =>
    req("/api/pack/batch", {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: csvText,
    }),

  getBoxes: () => req("/api/boxes"),
  putBoxes: (boxes) =>
    req("/api/boxes", { method: "PUT", body: JSON.stringify({ boxes }) }),

  getItems: () => req("/api/items"),
  putItems: (items) =>
    req("/api/items", { method: "PUT", body: JSON.stringify({ items }) }),

  getConfig: () => req("/api/config"),
  putConfig: (config) =>
    req("/api/config", { method: "PUT", body: JSON.stringify(config) }),
};
