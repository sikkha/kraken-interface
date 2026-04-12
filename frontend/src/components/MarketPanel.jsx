function numberOrPlaceholder(value) {
  return typeof value === "number" ? value.toLocaleString() : "--";
}

const CHART_STYLES = [
  { id: "candlestick", label: "candlestick" },
  { id: "line", label: "line" },
  { id: "area", label: "area" },
  { id: "trend", label: "trend" },
];

function formatTimestamp(timestampMs) {
  if (!timestampMs) {
    return "--";
  }
  return new Date(timestampMs).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function buildChartGeometry(candles = []) {
  if (!candles.length) {
    return { candles: [], minPrice: 0, maxPrice: 0, linePath: "", areaPath: "", trendPath: "" };
  }

  const width = 1000;
  const height = 320;
  const paddingX = 18;
  const paddingY = 18;
  const chartWidth = width - paddingX * 2;
  const chartHeight = height - paddingY * 2;
  const minPrice = Math.min(...candles.map((candle) => candle.low));
  const maxPrice = Math.max(...candles.map((candle) => candle.high));
  const priceRange = Math.max(maxPrice - minPrice, 1);
  const step = chartWidth / Math.max(candles.length, 1);
  const candleWidth = Math.max(Math.min(step * 0.65, 10), 2);

  const normalized = candles.map((candle, index) => {
    const x = paddingX + (index * step) + (step / 2);
    const toY = (price) => paddingY + ((maxPrice - price) / priceRange) * chartHeight;
    const openY = toY(candle.open);
    const closeY = toY(candle.close);
    const highY = toY(candle.high);
    const lowY = toY(candle.low);
    const bodyTop = Math.min(openY, closeY);
    const bodyHeight = Math.max(Math.abs(closeY - openY), 1.5);

    return {
      ...candle,
      x,
      highY,
      lowY,
      bodyTop,
      bodyHeight,
      bodyLeft: x - candleWidth / 2,
      bodyWidth: candleWidth,
      isUp: candle.close >= candle.open,
    };
  });

  const linePoints = normalized.map((candle) => `${candle.x},${paddingY + ((maxPrice - candle.close) / priceRange) * chartHeight}`);
  const linePath = linePoints
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point}`)
    .join(" ");
  const areaPath = normalized.length
    ? `${linePath} L ${normalized[normalized.length - 1].x},${height - paddingY} L ${normalized[0].x},${height - paddingY} Z`
    : "";
  const smoothed = normalized.map((candle, index, all) => {
    const window = all.slice(Math.max(0, index - 3), Math.min(all.length, index + 4));
    const average = window.reduce((total, item) => total + item.close, 0) / window.length;
    return `${index === 0 ? "M" : "L"} ${candle.x},${paddingY + ((maxPrice - average) / priceRange) * chartHeight}`;
  });

  return { candles: normalized, minPrice, maxPrice, linePath, areaPath, trendPath: smoothed.join(" ") };
}

function ChartRenderer({ candles, chartStyle, rangeLabel, intervalLabel }) {
  const chart = buildChartGeometry(candles);

  if (!candles?.length) {
    return (
      <div className="chart-empty">
        <p>No candle data available.</p>
      </div>
    );
  }

  const latest = candles[candles.length - 1];

  return (
    <div className="chart-panel">
      <div className="chart-meta">
        <span>{rangeLabel}</span>
        <span>{intervalLabel} bars</span>
        <span>{candles.length} candles</span>
        <span>last close: {numberOrPlaceholder(latest.close)}</span>
        <span>latest candle: {formatTimestamp(latest.timestamp_ms)}</span>
      </div>
      <svg className="market-chart" viewBox="0 0 1000 320" preserveAspectRatio="none" role="img">
        <defs>
          <linearGradient id="chart-surface" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(96, 165, 250, 0.16)" />
            <stop offset="100%" stopColor="rgba(15, 23, 42, 0.1)" />
          </linearGradient>
          <linearGradient id="area-fill" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(96, 165, 250, 0.42)" />
            <stop offset="100%" stopColor="rgba(96, 165, 250, 0.02)" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="1000" height="320" fill="url(#chart-surface)" />
        {[0, 1, 2, 3, 4].map((line) => (
          <line
            key={line}
            x1="18"
            x2="982"
            y1={18 + (line * 71)}
            y2={18 + (line * 71)}
            className="chart-grid-line"
          />
        ))}
        {chartStyle === "candlestick"
          ? chart.candles.map((candle) => (
              <g key={candle.timestamp_ms}>
                <line
                  x1={candle.x}
                  x2={candle.x}
                  y1={candle.highY}
                  y2={candle.lowY}
                  className={`chart-wick ${candle.isUp ? "up" : "down"}`}
                />
                <rect
                  x={candle.bodyLeft}
                  y={candle.bodyTop}
                  width={candle.bodyWidth}
                  height={candle.bodyHeight}
                  rx="1.5"
                  className={`chart-body ${candle.isUp ? "up" : "down"}`}
                />
              </g>
            ))
          : null}
        {chartStyle === "line" ? <path d={chart.linePath} className="chart-line-path" /> : null}
        {chartStyle === "area" ? (
          <>
            <path d={chart.areaPath} className="chart-area-fill" />
            <path d={chart.linePath} className="chart-line-path" />
          </>
        ) : null}
        {chartStyle === "trend" ? <path d={chart.trendPath} className="chart-trend-path" /> : null}
      </svg>
      <div className="chart-scale">
        <span>high: {numberOrPlaceholder(chart.maxPrice)}</span>
        <span>low: {numberOrPlaceholder(chart.minPrice)}</span>
      </div>
    </div>
  );
}

export default function MarketPanel({
  snapshot,
  candles,
  selectedSymbol,
  availableSymbols,
  onSelectedSymbolChange,
  chartStyle,
  onChartStyleChange,
  selectedRange,
  onRangeChange,
  rangePresets,
  onRefresh,
  error,
}) {
  const selectedRangeMeta = rangePresets[selectedRange];
  const symbolTabs = availableSymbols?.length ? availableSymbols : [selectedSymbol || snapshot?.pair || "BTCUSD"];

  return (
    <section className="panel market-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Market Screen</p>
          <h2>{selectedSymbol || snapshot?.pair || "BTCUSD"}</h2>
        </div>
        <button className="action-button" onClick={onRefresh} type="button">
          Refresh Snapshot
        </button>
      </div>

      <div className="price-strip">
        <div>
          <span>Last</span>
          <strong>{numberOrPlaceholder(snapshot?.last)}</strong>
        </div>
        <div>
          <span>Bid</span>
          <strong>{numberOrPlaceholder(snapshot?.bid)}</strong>
        </div>
        <div>
          <span>Ask</span>
          <strong>{numberOrPlaceholder(snapshot?.ask)}</strong>
        </div>
        <div>
          <span>Spread</span>
          <strong>{numberOrPlaceholder(snapshot?.spread)}</strong>
        </div>
      </div>

      <div className="chart-shell">
        <div className="chart-toolbar">
          <div className="chart-control-group">
            {symbolTabs.map((symbol) => (
              <button
                key={symbol}
                type="button"
                className={`chart-chip ${selectedSymbol === symbol ? "active" : ""}`}
                onClick={() => onSelectedSymbolChange(symbol)}
              >
                {symbol}
              </button>
            ))}
          </div>
          <div className="chart-control-group">
            {Object.entries(rangePresets).map(([preset, meta]) => (
              <button
                key={preset}
                type="button"
                className={`chart-chip ${selectedRange === preset ? "active" : ""}`}
                onClick={() => onRangeChange(preset)}
                title={`${meta.label} at ${meta.intervalLabel} resolution`}
              >
                {preset}
              </button>
            ))}
          </div>
          <div className="chart-control-group">
            {CHART_STYLES.map((style) => (
              <button
                key={style.id}
                type="button"
                className={`chart-chip ${chartStyle === style.id ? "active" : ""}`}
                onClick={() => onChartStyleChange(style.id)}
              >
                {style.label}
              </button>
            ))}
          </div>
        </div>
        <div className="chart-copy">
          <p>{selectedSymbol || snapshot?.pair || "BTCUSD"} Market Chart</p>
          <span>Viewing: {selectedSymbol || snapshot?.pair || "BTCUSD"}</span>
          <br />
          <span>
            Read-only OHLC polling from the backend candle route. Time presets map to operator-friendly history windows instead of raw exchange settings.
          </span>
        </div>
        <ChartRenderer
          candles={candles}
          chartStyle={chartStyle}
          rangeLabel={selectedRangeMeta?.label || selectedRange}
          intervalLabel={selectedRangeMeta?.intervalLabel || "--"}
        />
      </div>

      <div className="panel-footer">
        <span>source: {snapshot?.source || "unknown"}</span>
        <span>live-compatible: {String(snapshot?.live_compatible ?? false)}</span>
        <span>{error ? `error: ${error}` : "snapshot route healthy"}</span>
      </div>
    </section>
  );
}
