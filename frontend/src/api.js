const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  || `${window.location.protocol}//${window.location.hostname}:8002/api`;

async function parseJson(response) {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }
  return response.json();
}

function unwrapPayload(payload, keys = []) {
  if (!payload || typeof payload !== "object") {
    return payload;
  }

  for (const key of keys) {
    if (payload[key] && typeof payload[key] === "object") {
      return payload[key];
    }
  }

  return payload;
}

function normalizeMarketSnapshot(payload) {
  return unwrapPayload(payload, ["snapshot", "market", "data"]);
}

function normalizeMarketCandles(payload) {
  return unwrapPayload(payload, ["market", "data"]);
}

function normalizeSystemStatus(payload) {
  return unwrapPayload(payload, ["status", "system", "data"]);
}

function normalizeEngineStatus(payload) {
  return unwrapPayload(payload, ["status", "data"]);
}

function normalizeHistoryList(payload, key) {
  const unwrapped = unwrapPayload(payload, ["history", "data"]);
  if (!unwrapped || typeof unwrapped !== "object") {
    return { db_path: "", [key]: [] };
  }
  return {
    db_path: unwrapped.db_path || "",
    [key]: Array.isArray(unwrapped[key]) ? unwrapped[key] : [],
  };
}

export async function fetchSystemStatus() {
  const response = await fetch(`${API_BASE_URL}/system/state`);
  return normalizeSystemStatus(await parseJson(response));
}

export async function fetchMarketSnapshot(pair = "BTCUSD") {
  const response = await fetch(`${API_BASE_URL}/market/snapshot?pair=${encodeURIComponent(pair)}`);
  return normalizeMarketSnapshot(await parseJson(response));
}

export async function fetchMarketCandles(pair = "BTCUSD", interval = 1, limit = 120) {
  const response = await fetch(
    `${API_BASE_URL}/market/candles?pair=${encodeURIComponent(pair)}&interval=${encodeURIComponent(interval)}&limit=${encodeURIComponent(limit)}`,
  );
  return normalizeMarketCandles(await parseJson(response));
}

export async function sendChatMessage(payload) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function fetchEngineStatus() {
  const response = await fetch(`${API_BASE_URL}/engine/status`);
  return normalizeEngineStatus(await parseJson(response));
}

export async function runEngineOnce(payload = { pair: "BTCUSD", interval_seconds: 60 }) {
  const response = await fetch(`${API_BASE_URL}/engine/run-once`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function startEngine(payload) {
  const response = await fetch(`${API_BASE_URL}/engine/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return normalizeEngineStatus(await parseJson(response));
}

export async function stopEngine() {
  const response = await fetch(`${API_BASE_URL}/engine/stop`, {
    method: "POST",
  });
  return normalizeEngineStatus(await parseJson(response));
}

export async function resetEngine(payload = { scope: "all", reason: "Operator requested a fresh paper experiment." }) {
  const response = await fetch(`${API_BASE_URL}/engine/reset`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return normalizeEngineStatus(await parseJson(response));
}

export async function fetchHistoryCycles(limit = 20) {
  const response = await fetch(`${API_BASE_URL}/history/cycles?limit=${encodeURIComponent(limit)}`);
  return normalizeHistoryList(await parseJson(response), "cycles");
}

export async function fetchHistorySignals(limit = 20) {
  const response = await fetch(`${API_BASE_URL}/history/signals?limit=${encodeURIComponent(limit)}`);
  return normalizeHistoryList(await parseJson(response), "signals");
}

export async function fetchHistoryRiskDecisions(limit = 20) {
  const response = await fetch(`${API_BASE_URL}/history/risk-decisions?limit=${encodeURIComponent(limit)}`);
  return normalizeHistoryList(await parseJson(response), "decisions");
}

export async function fetchHistoryExecutions(limit = 20) {
  const response = await fetch(`${API_BASE_URL}/history/executions?limit=${encodeURIComponent(limit)}`);
  return normalizeHistoryList(await parseJson(response), "executions");
}

export async function fetchHistoryPortfolio(limit = 60) {
  const response = await fetch(`${API_BASE_URL}/history/portfolio?limit=${encodeURIComponent(limit)}`);
  return normalizeHistoryList(await parseJson(response), "snapshots");
}
