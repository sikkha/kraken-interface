import { useEffect, useState } from "react";

import {
  fetchEngineStatus,
  fetchHistoryCycles,
  fetchHistoryExecutions,
  fetchHistoryPortfolio,
  fetchMarketCandles,
  fetchMarketSnapshot,
  fetchSystemStatus,
  resetEngine,
  runEngineOnce,
  sendChatMessage,
  startEngine,
  stopEngine,
} from "./api";
import AssistantPanel from "./components/AssistantPanel";
import EnginePanel from "./components/EnginePanel";
import EventLogPanel from "./components/EventLogPanel";
import HistoryPanel from "./components/HistoryPanel";
import MarketPanel from "./components/MarketPanel";
import StatusBar from "./components/StatusBar";
import SystemStatusPanel from "./components/SystemStatusPanel";

const RANGE_PRESETS = {
  "1D": { interval: 5, limit: 288, label: "1 day", intervalLabel: "5m" },
  "3D": { interval: 15, limit: 288, label: "3 days", intervalLabel: "15m" },
  "5D": { interval: 30, limit: 240, label: "5 days", intervalLabel: "30m" },
  "1M": { interval: 240, limit: 180, label: "1 month", intervalLabel: "4h" },
  "3M": { interval: 1440, limit: 90, label: "3 months", intervalLabel: "1d" },
};

const starterMessages = [
  {
    id: "assistant-intro",
    role: "assistant",
    content:
      "Assistant routing is scaffolded through the backend. If API keys are not configured, the server returns a safe fallback response while keeping the contract stable.",
    meta: "stub-aware",
  },
];

export default function App() {
  const [theme, setTheme] = useState(() => {
    if (typeof window === "undefined") {
      return "dark";
    }
    const stored = window.localStorage.getItem("workstation-theme");
    return stored === "light" ? "light" : "dark";
  });
  const [status, setStatus] = useState(null);
  const [engineStatus, setEngineStatus] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [candles, setCandles] = useState([]);
  const [selectedChartSymbol, setSelectedChartSymbol] = useState("BTCUSD");
  const [selectedRange, setSelectedRange] = useState("1D");
  const [chartStyle, setChartStyle] = useState("candlestick");
  const [engineInterval, setEngineInterval] = useState(60);
  const [enginePending, setEnginePending] = useState(false);
  const [engineError, setEngineError] = useState("");
  const [messages, setMessages] = useState(starterMessages);
  const [chatPending, setChatPending] = useState(false);
  const [marketError, setMarketError] = useState("");
  const [history, setHistory] = useState({ cycles: [], executions: [], snapshots: [], db_path: "" });

  async function loadSystem() {
    const nextStatus = await fetchSystemStatus();
    setStatus(nextStatus);
  }

  async function loadEngine() {
    const nextEngineStatus = await fetchEngineStatus();
    setEngineStatus(nextEngineStatus);
    setEngineInterval(nextEngineStatus?.interval_seconds || nextEngineStatus?.engine?.interval_seconds || 60);
    setEngineError("");
  }

  async function loadMarket(symbol = selectedChartSymbol) {
    const range = RANGE_PRESETS[selectedRange];
    try {
      const [nextSnapshot, nextCandles] = await Promise.all([
        fetchMarketSnapshot(symbol),
        fetchMarketCandles(symbol, range.interval, range.limit),
      ]);
      setSnapshot(nextSnapshot);
      setCandles(nextCandles?.candles || []);
      setMarketError("");
    } catch (error) {
      setMarketError(error.message);
    }
  }

  async function loadHistory() {
    const [cycles, executions, snapshots] = await Promise.all([
      fetchHistoryCycles(12),
      fetchHistoryExecutions(12),
      fetchHistoryPortfolio(40),
    ]);
    setHistory({
      cycles: cycles.cycles || [],
      executions: executions.executions || [],
      snapshots: snapshots.snapshots || [],
      db_path: cycles.db_path || executions.db_path || snapshots.db_path || "",
    });
  }

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    document.documentElement.dataset.theme = theme;
    window.localStorage?.setItem("workstation-theme", theme);
  }, [theme]);

  useEffect(() => {
    const selectedSymbols = engineStatus?.latest_universe?.selected_symbols || [];
    if (!selectedSymbols.length) {
      if (!selectedChartSymbol) {
        setSelectedChartSymbol("BTCUSD");
      }
      return;
    }
    if (!selectedSymbols.includes(selectedChartSymbol)) {
      setSelectedChartSymbol(selectedSymbols[0]);
    }
  }, [engineStatus, selectedChartSymbol]);

  useEffect(() => {
    loadSystem().catch((error) => console.error(error));
    loadEngine().catch((error) => console.error(error));
    loadMarket().catch((error) => console.error(error));
    loadHistory().catch((error) => console.error(error));

    const intervalId = window.setInterval(() => {
      loadSystem().catch((error) => console.error(error));
      loadEngine().catch((error) => console.error(error));
      loadMarket().catch((error) => console.error(error));
      loadHistory().catch((error) => console.error(error));
    }, 10000);

    return () => window.clearInterval(intervalId);
  }, [selectedRange, selectedChartSymbol]);

  async function refreshWorkspace() {
    await Promise.all([loadSystem(), loadEngine(), loadMarket(), loadHistory()]);
  }

  async function handleRunOnce() {
    setEnginePending(true);
    try {
      await runEngineOnce({ pair: "BTCUSD", interval_seconds: engineInterval });
      await refreshWorkspace();
    } catch (error) {
      setEngineError(error.message);
    } finally {
      setEnginePending(false);
    }
  }

  async function handleStartEngine() {
    setEnginePending(true);
    try {
      const nextEngineStatus = await startEngine({ pair: "BTCUSD", interval_seconds: engineInterval });
      setEngineStatus(nextEngineStatus);
      await Promise.all([loadSystem(), loadMarket()]);
      setEngineError("");
    } catch (error) {
      setEngineError(error.message);
    } finally {
      setEnginePending(false);
    }
  }

  async function handleStopEngine() {
    setEnginePending(true);
    try {
      const nextEngineStatus = await stopEngine();
      setEngineStatus(nextEngineStatus);
      await Promise.all([loadSystem(), loadMarket()]);
      setEngineError("");
    } catch (error) {
      setEngineError(error.message);
    } finally {
      setEnginePending(false);
    }
  }

  async function handleResetEngine() {
    setEnginePending(true);
    try {
      const nextEngineStatus = await resetEngine({
        scope: "all",
        reason: "Operator requested a clean paper experiment reset.",
      });
      setEngineStatus(nextEngineStatus);
      setEngineInterval(nextEngineStatus?.interval_seconds || 60);
      await Promise.all([loadSystem(), loadMarket(), loadHistory()]);
      setEngineError("");
    } catch (error) {
      setEngineError(error.message);
    } finally {
      setEnginePending(false);
    }
  }

  function buildChatContext() {
    const latestSignal = engineStatus?.latest_signal;
    const latestRisk = engineStatus?.latest_risk_decision;
    const latestExecution = engineStatus?.latest_execution;
    const portfolio = engineStatus?.portfolio;
    const universe = engineStatus?.latest_universe;
    return [
      `engine_running=${engineStatus?.engine?.running ?? false}`,
      `selected_symbols=${(universe?.selected_symbols || []).join(",") || "none"}`,
      `signal=${latestSignal?.signal || "none"}`,
      `confidence=${latestSignal?.confidence ?? "n/a"}`,
      `target_weight=${latestSignal?.target_weight ?? "n/a"}`,
      `exposure_state=${latestSignal?.exposure_state || "n/a"}`,
      `risk=${latestRisk?.reason || "none"}`,
      `risk_action=${latestRisk?.action_policy || "none"}`,
      `execution=${latestExecution?.status || "none"}`,
      `portfolio_value=${portfolio?.portfolio_value ?? "n/a"}`,
    ].join("\n");
  }

  async function handleSend(message) {
    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: message,
      meta: "",
    };
    setMessages((current) => [...current, userMessage]);
    setChatPending(true);

    try {
      const response = await sendChatMessage({ message, context: buildChatContext() });
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: response.reply,
          meta: `${response.source} | ${response.model}${response.error ? ` | ${response.error}` : ""}`,
        },
      ]);
      await Promise.all([loadSystem(), loadEngine()]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          content: "Backend chat route is unavailable right now.",
          meta: error.message,
        },
      ]);
    } finally {
      setChatPending(false);
    }
  }

  return (
    <div className="app-shell">
      <StatusBar
        status={status}
        engineStatus={engineStatus}
        theme={theme}
        onToggleTheme={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
      />

      <main className="workspace-grid">
        <section className="main-stack">
          <MarketPanel
            snapshot={snapshot}
            candles={candles}
            selectedSymbol={selectedChartSymbol}
            availableSymbols={engineStatus?.latest_universe?.selected_symbols || []}
            onSelectedSymbolChange={setSelectedChartSymbol}
            chartStyle={chartStyle}
            onChartStyleChange={setChartStyle}
            selectedRange={selectedRange}
            onRangeChange={setSelectedRange}
            rangePresets={RANGE_PRESETS}
            onRefresh={loadMarket}
            error={marketError}
          />
          <EnginePanel
            engineStatus={engineStatus}
            intervalSeconds={engineInterval}
            onIntervalChange={setEngineInterval}
            onStart={handleStartEngine}
            onStop={handleStopEngine}
            onRunOnce={handleRunOnce}
            onReset={handleResetEngine}
            pending={enginePending}
            error={engineError}
          />
          <div className="lower-grid">
            <SystemStatusPanel status={status} />
            <HistoryPanel
              cycles={history.cycles}
              executions={history.executions}
              portfolioSnapshots={history.snapshots}
              dbPath={history.db_path}
            />
            <EventLogPanel events={status?.recent_events || []} />
          </div>
        </section>

        <AssistantPanel messages={messages} pending={chatPending} onSend={handleSend} />
      </main>
    </div>
  );
}
