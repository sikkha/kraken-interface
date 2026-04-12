import { useState } from "react";

export default function AssistantPanel({ messages, pending, onSend }) {
  const [draft, setDraft] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || pending) {
      return;
    }

    setDraft("");
    await onSend(message);
  }

  return (
    <section className="panel assistant-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">AI Assistant</p>
          <h2>Operator Copilot</h2>
        </div>
      </div>

      <div className="chat-stream">
        {messages.map((message) => (
          <article className={`chat-bubble ${message.role}`} key={message.id}>
            <span>{message.role === "user" ? "Operator" : "Assistant"}</span>
            <p>{message.content}</p>
            {message.meta ? <small>{message.meta}</small> : null}
          </article>
        ))}
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask for a market summary, operational note, or next engineering task."
          rows={4}
        />
        <button className="action-button" type="submit" disabled={pending}>
          {pending ? "Thinking..." : "Send"}
        </button>
      </form>
    </section>
  );
}
