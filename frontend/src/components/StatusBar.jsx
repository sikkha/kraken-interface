function statusTone(readiness) {
  return readiness === "scaffold-ready" || readiness === "live-ready" ? "ok" : "warn";
}

export default function StatusBar({ status, engineStatus, theme, onToggleTheme }) {
  return (
    <header className="status-bar">
      <div>
        <p className="eyebrow">Operator Console</p>
        <h1>Kraken Interface Workstation</h1>
      </div>
      <div className="status-actions">
        <div className="status-pills">
          <span className={`pill ${statusTone(status?.readiness)}`}>
            {status?.readiness || "loading"}
          </span>
          <span className="pill neutral">mode: {status?.mode || "..."}</span>
          <span className="pill neutral">market: {status?.market_source || "..."}</span>
          <span className="pill neutral">engine: {engineStatus?.engine?.running ? "running" : "stopped"}</span>
          <span className="pill neutral">signal: {engineStatus?.active_signal_engine_id || engineStatus?.signal_engine_type || "..."}</span>
          <span className="pill neutral">classes: {engineStatus?.latest_universe?.selected_classes?.length ?? 0}</span>
          <span className="pill neutral">active assets: {engineStatus?.latest_universe?.selected_symbols?.length ?? 0}</span>
          <span className="pill neutral">ai: {status?.ai_route || "..."}</span>
        </div>
        <button className="theme-toggle" type="button" onClick={onToggleTheme} title="Toggle dark or light mode">
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </div>
    </header>
  );
}
