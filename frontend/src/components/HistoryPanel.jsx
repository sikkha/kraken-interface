function currency(value) {
  return typeof value === "number"
    ? value.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })
    : "--";
}

function timestamp(value) {
  if (!value) {
    return "--";
  }
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function percent(value) {
  return typeof value === "number"
    ? `${(value * 100).toLocaleString(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`
    : "--";
}

function buildSparklinePoints(snapshots = []) {
  if (!snapshots.length) {
    return "";
  }
  const width = 280;
  const height = 84;
  const values = snapshots.map((snapshot) => snapshot.portfolio_value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  return snapshots
    .slice()
    .reverse()
    .map((snapshot, index, ordered) => {
      const x = (index / Math.max(ordered.length - 1, 1)) * width;
      const y = height - ((snapshot.portfolio_value - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");
}

export default function HistoryPanel({ cycles, executions, portfolioSnapshots, dbPath }) {
  const sparkline = buildSparklinePoints(portfolioSnapshots);
  const latest = portfolioSnapshots?.[0];
  const oldest = portfolioSnapshots?.[portfolioSnapshots.length - 1];
  const delta = latest && oldest ? latest.portfolio_value - oldest.portfolio_value : 0;

  return (
    <section className="panel history-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Experiment Ledger</p>
          <h2>Recent History</h2>
        </div>
      </div>

      <div className="history-sparkline-card">
        <div className="status-card-top">
          <strong>Equity Trace</strong>
          <span className="pill neutral">{portfolioSnapshots?.length || 0} points</span>
        </div>
        {sparkline ? (
          <svg className="history-sparkline" viewBox="0 0 280 84" preserveAspectRatio="none" aria-label="Equity curve">
            <polyline fill="none" stroke="var(--accent)" strokeWidth="3" points={sparkline} />
          </svg>
        ) : (
          <p className="empty-state">Run the paper engine to accumulate portfolio history.</p>
        )}
        <p className="summary-copy">
          Recent portfolio delta: {delta >= 0 ? "+" : ""}${currency(delta)} | latest value: ${currency(latest?.portfolio_value)}
        </p>
      </div>

      <div className="history-grid">
        <article className="summary-card">
          <div className="status-card-top">
            <strong>Recent Cycles</strong>
            <span className="pill neutral">{cycles?.length || 0}</span>
          </div>
          <div className="history-list">
            {(cycles || []).slice(0, 5).map((cycle) => (
              <div className="history-row" key={cycle.id}>
                <div>
                  <strong>{cycle.cycle_outcome}</strong>
                  <span>{timestamp(cycle.finished_at_ms || cycle.started_at_ms)}</span>
                </div>
                <small>{cycle.market_source} | {cycle.signal_engine_type} | {(cycle.selected_symbols || []).join(", ") || "no active picks"}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="summary-card">
          <div className="status-card-top">
            <strong>Recent Executions</strong>
            <span className="pill neutral">{executions?.length || 0}</span>
          </div>
          <div className="history-list">
            {(executions || []).slice(0, 5).map((execution) => (
              <div className="history-row" key={execution.id}>
                <div>
                  <strong>{execution.symbol} {execution.status}</strong>
                  <span>{execution.action_policy || execution.side} @ ${currency(execution.price)}</span>
                </div>
                <small>{timestamp(execution.timestamp_ms)} | target {percent(execution.target_weight)}</small>
              </div>
            ))}
          </div>
        </article>
      </div>

      <div className="panel-footer">
        <span>ledger db: {dbPath || "--"}</span>
        <span>Reset Experiment wipes ledger history for a clean new run</span>
        <span>latest-state JSON remains active for workstation compatibility</span>
      </div>
    </section>
  );
}
