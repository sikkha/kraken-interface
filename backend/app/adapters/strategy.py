from backend.app.signal_engine import load_signal_artifact


class StrategyAdapter:
    """Hierarchical strategy seam: class allocator plus packaged GRU tactical selector."""

    def status(self) -> dict[str, object]:
        artifact_status, _ = load_signal_artifact()
        active_mode = artifact_status.engine_type
        note_suffix = (
            f"Active tactical engine: {artifact_status.engine_type} ({artifact_status.status}). "
            f"Fallback tactical path remains notebook_proxy."
        )
        return {
            "name": "strategy_adapter",
            "role": "strategy_integration",
            "ready": True,
            "mode": active_mode,
            "notes": (
                "Class-level allocation is now handled by the hierarchical portfolio policy, while live "
                "crypto intra-class selection uses the packaged GRU tactical runtime when the artifact is available. "
                f"{note_suffix}"
            ),
        }
