export default function EventLogPanel({ events }) {
  return (
    <section className="panel event-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Observability</p>
          <h2>Event Log</h2>
        </div>
      </div>

      <div className="event-list">
        {(events || []).length === 0 ? (
          <p className="empty-state">No backend events yet. Query the API or send an AI message to populate this panel.</p>
        ) : (
          events.map((event, index) => (
            <article className="event-item" key={`${event.timestamp_ms}-${index}`}>
              <div>
                <strong>{event.component}</strong>
                <span>{event.level}</span>
              </div>
              <p>{event.message}</p>
              <small>{JSON.stringify(event.data || {})}</small>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
