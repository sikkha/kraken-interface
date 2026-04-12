function currency(value) {
  return typeof value === "number"
    ? value.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })
    : "--";
}

function quantity(value) {
  return typeof value === "number"
    ? value.toLocaleString(undefined, { maximumFractionDigits: 8 })
    : "--";
}

function percent(value) {
  return typeof value === "number"
    ? `${(value * 100).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}%`
    : "--";
}

function bps(value) {
  return typeof value === "number"
    ? `${value >= 0 ? "+" : ""}${value.toLocaleString(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 })} bps`
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
    second: "2-digit",
  });
}

function toneForDecision(approved) {
  return approved ? "ok" : "warn";
}

function DetailRow({ label, value }) {
  return (
    <div className="detail-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function weightForPosition(portfolioValue, position) {
  if (!position || !portfolioValue || portfolioValue <= 0) {
    return null;
  }
  return position.market_value / portfolioValue;
}

const COMPOSITION_COLORS = [
  "#60a5fa",
  "#22c55e",
  "#f59e0b",
  "#f87171",
  "#a78bfa",
  "#14b8a6",
  "#fb7185",
  "#38bdf8",
];

function compositionColor(index) {
  return COMPOSITION_COLORS[index % COMPOSITION_COLORS.length];
}

function buildDonutBackground(entries) {
  const slices = entries.filter((entry) => entry.actual_weight > 0);
  if (!slices.length) {
    return "conic-gradient(rgba(148, 163, 184, 0.18) 0 100%)";
  }

  let cursor = 0;
  const parts = slices.map((entry, index) => {
    const start = cursor;
    const end = cursor + (entry.actual_weight * 100);
    cursor = end;
    return `${compositionColor(index)} ${start}% ${end}%`;
  });
  if (cursor < 100) {
    parts.push(`rgba(148, 163, 184, 0.16) ${cursor}% 100%`);
  }
  return `conic-gradient(${parts.join(", ")})`;
}

function PortfolioCompositionCard({ entries, portfolioValue }) {
  const activeEntries = entries.filter((entry) => entry.actual_weight > 0.001 || entry.kind === "cash");
  const deployedWeight = activeEntries
    .filter((entry) => entry.kind !== "cash")
    .reduce((total, entry) => total + entry.actual_weight, 0);

  return (
    <article className="summary-card">
      <div className="status-card-top">
        <strong>Portfolio Mix</strong>
        <span className="pill neutral">{activeEntries.length} slices</span>
      </div>
      <div className="portfolio-visual">
        <div className="portfolio-donut" style={{ background: buildDonutBackground(activeEntries) }}>
          <div className="portfolio-donut-center">
            <strong>{percent(deployedWeight)}</strong>
            <span>deployed</span>
          </div>
        </div>
        <div className="portfolio-legend">
          {activeEntries.map((entry, index) => (
            <div className="composition-row" key={entry.symbol}>
              <div className="composition-label">
                <span className="composition-swatch" style={{ backgroundColor: compositionColor(index) }} />
                <div>
                  <strong>{entry.symbol}</strong>
                  <span>{entry.kind === "cash" ? "cash reserve" : entry.category || "portfolio asset"}</span>
                </div>
              </div>
              <div className="composition-values">
                <strong>{percent(entry.actual_weight)}</strong>
                <span>${currency(entry.market_value)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <p className="summary-copy">Actual deployed capital is rendered from backend portfolio weights, with cash included as its own slice.</p>
      <dl className="detail-list">
        <DetailRow label="Portfolio value" value={`$${currency(portfolioValue)}`} />
        <DetailRow label="Cash weight" value={percent(entries.find((entry) => entry.kind === "cash")?.actual_weight)} />
      </dl>
    </article>
  );
}

function PnlContributionCard({ entries }) {
  const rows = entries
    .filter((entry) => entry.kind === "asset" && (entry.market_value > 0 || Math.abs(entry.unrealized_pnl) > 0.01))
    .sort((left, right) => Math.abs(right.unrealized_pnl) - Math.abs(left.unrealized_pnl));
  const maxAbsPnl = Math.max(...rows.map((entry) => Math.abs(entry.unrealized_pnl)), 1);

  return (
    <article className="summary-card">
      <div className="status-card-top">
        <strong>PnL Contribution</strong>
        <span className="pill neutral">{rows.length || 0} assets</span>
      </div>
      <div className="mini-chart-list">
        {rows.length ? rows.map((entry) => (
          <div className="mini-chart-row" key={entry.symbol}>
            <div className="mini-chart-header">
              <strong>{entry.symbol}</strong>
              <span>{entry.unrealized_pnl >= 0 ? "+" : ""}${currency(entry.unrealized_pnl)}</span>
            </div>
            <div className="mini-chart-track">
              <div
                className={`mini-chart-bar ${entry.unrealized_pnl >= 0 ? "positive" : "negative"}`}
                style={{ width: `${Math.max((Math.abs(entry.unrealized_pnl) / maxAbsPnl) * 100, 6)}%` }}
              />
            </div>
            <small>wt {percent(entry.actual_weight)} | mv ${currency(entry.market_value)}</small>
          </div>
        )) : <p className="empty-state">No open asset contribution to display yet.</p>}
      </div>
    </article>
  );
}

function WeightAlignmentCard({ entries }) {
  const rows = entries
    .filter((entry) => entry.actual_weight > 0.001 || (entry.target_weight ?? 0) > 0.001 || entry.kind === "cash")
    .sort((left, right) => (right.target_weight ?? 0) - (left.target_weight ?? 0));

  return (
    <article className="summary-card">
      <div className="status-card-top">
        <strong>Target vs Actual</strong>
        <span className="pill neutral">{rows.length || 0} rows</span>
      </div>
      <div className="mini-chart-list">
        {rows.length ? rows.map((entry) => {
          const actualWidth = Math.max((entry.actual_weight || 0) * 100, 0);
          const targetWidth = Math.max(((entry.target_weight ?? 0)) * 100, 0);
          return (
            <div className="mini-chart-row" key={entry.symbol}>
              <div className="mini-chart-header">
                <strong>{entry.symbol}</strong>
                <span>{percent(entry.actual_weight)} / {percent(entry.target_weight)}</span>
              </div>
              <div className="weight-compare-stack">
                <div className="weight-compare-label">actual</div>
                <div className="weight-compare-track">
                  <div className="weight-compare-bar actual" style={{ width: `${actualWidth}%` }} />
                </div>
                <div className="weight-compare-label">target</div>
                <div className="weight-compare-track">
                  <div className="weight-compare-bar target" style={{ width: `${targetWidth}%` }} />
                </div>
              </div>
              <small>
                gap {percent(entry.weight_gap)} | {entry.exposure_state || entry.category || "portfolio"}
              </small>
            </div>
          );
        }) : <p className="empty-state">No target/actual comparison is available yet.</p>}
      </div>
    </article>
  );
}

function ClassAllocationCard({ latestUniverse }) {
  const classes = latestUniverse?.class_allocations || [];

  return (
    <article className="summary-card">
      <div className="status-card-top">
        <strong>Class Allocation</strong>
        <span className="pill neutral">{classes.length || 0} sleeves</span>
      </div>
      <p className="summary-copy">
        Capital is allocated by class first, then routed to tactical winners inside live sleeves.
      </p>
      <div className="asset-list">
        {classes.length ? classes.map((allocation) => (
          <div className="asset-row" key={allocation.class_id}>
            <div>
              <strong>{allocation.label}</strong>
              <span>
                score {typeof allocation.class_score === "number" ? allocation.class_score.toFixed(3) : "--"} | conf {percent(allocation.class_confidence)} | {allocation.category}
              </span>
            </div>
            <small>
              target {percent(allocation.target_weight)} | {(allocation.selected_symbols || []).join(", ") || (allocation.live_tradeable ? "no tactical pick" : "scaffolded")}
            </small>
          </div>
        )) : <p className="empty-state">Run the engine to populate class-level allocation.</p>}
      </div>
    </article>
  );
}

export default function EnginePanel({
  engineStatus,
  intervalSeconds,
  onIntervalChange,
  onStart,
  onStop,
  onRunOnce,
  onReset,
  pending,
  error,
}) {
  const engine = engineStatus?.engine;
  const latestSignal = engineStatus?.latest_signal;
  const latestSignals = engineStatus?.latest_signals || [];
  const latestRisk = engineStatus?.latest_risk_decision;
  const latestRisks = engineStatus?.latest_risk_decisions || [];
  const latestExecution = engineStatus?.latest_execution;
  const latestExecutions = engineStatus?.latest_executions || [];
  const portfolio = engineStatus?.portfolio;
  const portfolioComposition = engineStatus?.portfolio_composition || [];
  const pnl = engineStatus?.pnl;
  const latestUniverse = engineStatus?.latest_universe;
  const positions = portfolio?.positions || [];
  const selectedCandidates = (latestUniverse?.candidates || []).filter((candidate) => candidate.selected).slice(0, 3);
  const leadPosition = positions[0];

  return (
    <section className="panel engine-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Paper Engine</p>
          <h2>Multi-Asset Loop Control</h2>
        </div>
        <div className="engine-pills">
          <span className={`pill ${engine?.running ? "ok" : "warn"}`}>{engine?.running ? "running" : "stopped"}</span>
          <span className="pill neutral">{engine?.mode || "paper"}</span>
          <span className="pill neutral">{engineStatus?.active_signal_engine_id || engine?.active_signal_engine_id || "gru_packaged"}</span>
        </div>
      </div>

      <div className="engine-toolbar">
        <label className="engine-interval-control">
          <span>Loop interval</span>
          <select value={intervalSeconds} onChange={(event) => onIntervalChange(Number(event.target.value))}>
            <option value={15}>15 sec</option>
            <option value={30}>30 sec</option>
            <option value={60}>1 min</option>
            <option value={120}>2 min</option>
            <option value={300}>5 min</option>
          </select>
        </label>
        <div className="engine-actions">
          <button className="action-button" type="button" onClick={onRunOnce} disabled={pending}>
            {pending ? "Working..." : "Run Once"}
          </button>
          <button className="action-button secondary" type="button" onClick={onStart} disabled={pending || engine?.running}>
            Start
          </button>
          <button className="action-button danger" type="button" onClick={onStop} disabled={pending || !engine?.running}>
            Stop
          </button>
          <button className="action-button ghost" type="button" onClick={onReset} disabled={pending}>
            Reset Experiment
          </button>
        </div>
      </div>

      <div className="engine-note-card">
        {(engineStatus?.operator_notes || []).map((note) => (
          <p key={note}>{note}</p>
        ))}
      </div>

      <div className="engine-meta-grid">
        <div className="status-card">
          <div className="status-card-top">
            <strong>Engine State</strong>
            <span className={`pill ${engine?.running ? "ok" : "warn"}`}>{engine?.last_cycle_status || "idle"}</span>
          </div>
          <dl className="detail-list">
            <DetailRow label="Symbol scope" value={(engine?.symbols || ["BTCUSD"]).join(", ")} />
            <DetailRow label="Interval" value={`${engine?.interval_seconds || intervalSeconds}s`} />
            <DetailRow label="Cycles" value={engine?.cycle_count ?? 0} />
            <DetailRow label="Last cycle" value={timestamp(engine?.last_cycle_completed_ms)} />
            <DetailRow label="Last signal" value={timestamp(engineStatus?.last_signal_timestamp_ms)} />
            <DetailRow label="Last execution" value={timestamp(engineStatus?.last_execution_timestamp_ms)} />
          </dl>
        </div>
        <div className="status-card">
          <div className="status-card-top">
            <strong>Portfolio</strong>
            <span className="pill neutral">paper</span>
          </div>
          <dl className="detail-list">
            <DetailRow label="Portfolio value" value={`$${currency(portfolio?.portfolio_value)}`} />
            <DetailRow label="Initial capital" value={`$${currency(engineStatus?.initial_paper_capital)}`} />
            <DetailRow label="State source" value={engineStatus?.portfolio_source || "--"} />
            <DetailRow label="Reset at" value={timestamp(engineStatus?.portfolio_reset_at_ms)} />
            <DetailRow label="Cash" value={`$${currency(portfolio?.cash_usd)}`} />
            <DetailRow label="Realized pnl" value={`$${currency(pnl?.realized_pnl)}`} />
            <DetailRow label="Unrealized pnl" value={`$${currency(pnl?.unrealized_pnl)}`} />
          </dl>
        </div>
      </div>

      <div className="engine-summary-grid">
        <article className="summary-card">
          <div className="status-card-top">
            <strong>Latest Signal</strong>
            <span className="pill neutral">{latestSignal?.signal || "none"}</span>
          </div>
          <dl className="detail-list">
            <DetailRow label="Confidence" value={percent(latestSignal?.confidence)} />
            <DetailRow label="Regime score" value={latestSignal?.regime_score ?? "--"} />
            <DetailRow label="Normalized score" value={latestSignal?.features_summary?.normalized_score ?? "--"} />
            <DetailRow label="Target weight" value={percent(latestSignal?.target_weight)} />
            <DetailRow label="Policy band" value={latestSignal?.features_summary?.policy_band || "--"} />
            <DetailRow label="Exposure state" value={latestSignal?.exposure_state || "--"} />
            <DetailRow label="Active engine" value={engineStatus?.active_signal_engine_id || latestSignal?.engine_type || engineStatus?.signal_engine_type || "--"} />
            <DetailRow label="Fallback engine" value={engineStatus?.fallback_signal_engine_id || engine?.fallback_signal_engine_id || "--"} />
            <DetailRow label="Model" value={latestSignal?.model_version || engineStatus?.signal_model_version || "--"} />
            <DetailRow label="Artifact" value={latestSignal?.artifact_status || engineStatus?.signal_artifact_status || "--"} />
            <DetailRow label="Loaded" value={String(latestSignal?.artifact_loaded ?? engineStatus?.signal_artifact_loaded ?? false)} />
            <DetailRow label="Artifact path" value={latestSignal?.artifact_path || engineStatus?.signal_artifact_path || "--"} />
            <DetailRow label="Policy reason" value={latestSignal?.action_policy_reason || "none"} />
            <DetailRow label="Runtime note" value={latestSignal?.runtime_note || engineStatus?.signal_runtime_note || "none"} />
          </dl>
        </article>

        <article className="summary-card">
          <div className="status-card-top">
            <strong>Risk Decision</strong>
            <span className={`pill ${toneForDecision(latestRisk?.approved)}`}>{latestRisk?.side || "hold"}</span>
          </div>
          <p className="summary-copy">{latestRisk?.reason || "No risk decision yet."}</p>
          <dl className="detail-list">
            <DetailRow label="Approved" value={String(latestRisk?.approved ?? false)} />
            <DetailRow label="Action policy" value={latestRisk?.action_policy || "--"} />
            <DetailRow label="Target weight" value={percent(latestRisk?.target_weight)} />
            <DetailRow label="Current weight" value={percent(latestRisk?.current_weight)} />
            <DetailRow label="Rebalance gap" value={percent(latestRisk?.rebalance_gap)} />
            <DetailRow label="Exposure state" value={latestRisk?.exposure_state || "--"} />
            <DetailRow label="Trade size" value={percent(latestRisk?.size)} />
            <DetailRow label="Spread bps" value={latestRisk?.checks?.spread_bps ?? "--"} />
          </dl>
        </article>

        <article className="summary-card">
          <div className="status-card-top">
            <strong>Execution</strong>
            <span className="pill neutral">{latestExecution?.status || "none"}</span>
          </div>
          <p className="summary-copy">{latestExecution?.reason || "No execution yet."}</p>
          <dl className="detail-list">
            <DetailRow label="Side" value={latestExecution?.side || "--"} />
            <DetailRow label="Action policy" value={latestExecution?.action_policy || "--"} />
            <DetailRow label="Target weight" value={percent(latestExecution?.target_weight)} />
            <DetailRow label="Before weight" value={percent(latestExecution?.current_weight_before)} />
            <DetailRow label="After weight" value={percent(latestExecution?.current_weight_after)} />
            <DetailRow label="Price" value={`$${currency(latestExecution?.price)}`} />
            <DetailRow label="Notional" value={`$${currency(latestExecution?.notional_usd)}`} />
            <DetailRow label="Outcome" value={engineStatus?.last_cycle_outcome || "--"} />
          </dl>
        </article>

        <article className="summary-card">
          <div className="status-card-top">
            <strong>Universe Selection</strong>
            <span className="pill neutral">{latestUniverse?.selected_symbols?.length || 0} active</span>
          </div>
          <p className="summary-copy">{latestUniverse?.selection_reason || "Universe scan not available yet."}</p>
          <div className="asset-list">
            {selectedCandidates.length ? selectedCandidates.map((candidate) => {
              const signal = latestSignals.find((item) => item.symbol === candidate.symbol);
              const risk = latestRisks.find((item) => item.symbol === candidate.symbol);
              return (
                <div className="asset-row" key={candidate.symbol}>
                  <div>
                    <strong>{candidate.symbol}</strong>
                    <span>{candidate.asset_class_label} | {candidate.category} | score {candidate.combined_universe_score?.toFixed?.(3) ?? "--"}</span>
                  </div>
                  <small>
                    class {percent(candidate.class_target_weight)} | target {percent(candidate.target_weight)} | {signal?.features_summary?.policy_band || "band --"} | {risk?.action_policy || "hold"}
                  </small>
                </div>
              );
            }) : <p className="empty-state">Run the engine to populate the ranked candidate set.</p>}
          </div>
        </article>

        <ClassAllocationCard latestUniverse={latestUniverse} />

        <article className="summary-card">
          <div className="status-card-top">
            <strong>Positions</strong>
            <span className="pill neutral">{positions.length ? `${positions.length} open` : "flat"}</span>
          </div>
          <dl className="detail-list">
            <DetailRow label="Cash reserve" value={percent(latestUniverse?.cash_reserve_weight)} />
            <DetailRow label="Gross target" value={percent(latestUniverse?.gross_target_weight)} />
            <DetailRow label="Lead position" value={leadPosition?.symbol || "--"} />
          </dl>
          <div className="asset-list">
            {positions.length ? positions.map((position) => {
              const execution = latestExecutions.find((item) => item.symbol === position.symbol);
              const composition = portfolioComposition.find((item) => item.symbol === position.symbol);
              return (
                <div className="asset-row" key={position.symbol}>
                  <div>
                    <strong>{position.symbol}</strong>
                    <span>qty {quantity(position.quantity)} | avg ${currency(position.avg_entry_price)}</span>
                  </div>
                  <small>
                    wt {percent(composition?.actual_weight ?? weightForPosition(portfolio?.portfolio_value, position))} | tgt {percent(composition?.target_weight)} | pnl ${currency(position.unrealized_pnl)} | fill {composition?.last_fill_price ? `$${currency(composition.last_fill_price)} / ${bps(composition.mark_vs_last_fill_bps)}` : "n/a"} | {execution?.action_policy || "hold"}
                  </small>
                </div>
              );
            }) : <p className="empty-state">No paper positions are currently open.</p>}
          </div>
        </article>

        <PortfolioCompositionCard entries={portfolioComposition} portfolioValue={portfolio?.portfolio_value} />
        <PnlContributionCard entries={portfolioComposition} />
        <WeightAlignmentCard entries={portfolioComposition} />
      </div>

      <div className="panel-footer">
        <span>market source: {engineStatus?.market_source || "--"}</span>
        <span>
          executions/noops/rejections: {engineStatus?.total_execution_count ?? 0}/
          {engineStatus?.total_noop_count ?? 0}/{engineStatus?.total_risk_rejection_count ?? 0}
        </span>
        <span>{engine?.last_error ? `last error: ${engine.last_error}` : "last error: none"}</span>
        <span>{error ? `engine error: ${error}` : "engine routes healthy"}</span>
      </div>
    </section>
  );
}
