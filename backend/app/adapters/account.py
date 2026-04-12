class AccountAdapter:
    """Placeholder seam for future Kraken account state integration."""

    def status(self) -> dict[str, object]:
        return {
            "name": "account_adapter",
            "role": "account_reader",
            "ready": False,
            "mode": "placeholder",
            "notes": "Account balances and positions are not wired yet.",
        }
