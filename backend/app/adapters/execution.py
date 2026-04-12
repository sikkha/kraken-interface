class ExecutionAdapter:
    """Paper execution seam for the BTCUSD trading loop foundation."""

    def status(self) -> dict[str, object]:
        return {
            "name": "execution_adapter",
            "role": "execution_writer",
            "ready": True,
            "mode": "paper",
            "notes": "Paper execution contracts are live. Real order placement remains intentionally disabled.",
        }
