export default function SystemStatusPanel({ status }) {
  return (
    <section className="panel status-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">System Readiness</p>
          <h2>Backend State</h2>
        </div>
      </div>

      <div className="status-grid">
        {(status?.adapters || []).map((adapter) => (
          <article className="status-card" key={adapter.name}>
            <div className="status-card-top">
              <strong>{adapter.name}</strong>
              <span className={`pill ${adapter.ready ? "ok" : "warn"}`}>
                {adapter.mode}
              </span>
            </div>
            <p>{adapter.role}</p>
            <span>{adapter.notes}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
