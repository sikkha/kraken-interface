from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    system_mode: str
    host: str
    port: int
    default_pair: str
    kraken_market_source: str
    default_llm_model: str
    allowed_origins: list[str]
    allowed_origin_regex: str
    signal_candle_interval: int
    signal_candle_limit: int
    signal_feature_window: int
    signal_lookahead_bars: int
    signal_artifact_path: str
    signal_confidence_threshold: float
    signal_flat_score_threshold: float
    signal_buy_score_threshold: float
    signal_full_score_threshold: float
    max_position_weight: float
    portfolio_max_gross_weight: float
    portfolio_max_selected_assets: int
    rebalance_deadband_weight: float
    trade_cooldown_seconds: int
    max_spread_bps: float
    abnormal_volatility_threshold: float
    paper_starting_cash_usd: float
    paper_min_trade_notional_usd: float
    runtime_state_dir: str
    runtime_ledger_path: str
    engine_default_interval_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = os.getenv("ALLOWED_ORIGINS", "")
    default_origin_regex = ""
    return Settings(
        app_name=os.getenv("APP_NAME", "Kraken Interface Workstation API"),
        app_env=os.getenv("APP_ENV", "development"),
        system_mode=os.getenv("SYSTEM_MODE", "scaffold"),
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        default_pair=os.getenv("DEFAULT_MARKET_PAIR", "BTCUSD"),
        kraken_market_source=os.getenv("KRAKEN_MARKET_SOURCE", "mock"),
        default_llm_model=os.getenv("DEFAULT_LLM_MODEL", "gpt-5.1"),
        allowed_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
        allowed_origin_regex=os.getenv("ALLOWED_ORIGIN_REGEX", default_origin_regex) or "",
        signal_candle_interval=int(os.getenv("SIGNAL_CANDLE_INTERVAL", "60")),
        signal_candle_limit=int(os.getenv("SIGNAL_CANDLE_LIMIT", "240")),
        signal_feature_window=int(os.getenv("SIGNAL_FEATURE_WINDOW", "12")),
        signal_lookahead_bars=int(os.getenv("SIGNAL_LOOKAHEAD_BARS", "5")),
        signal_artifact_path=os.getenv("SIGNAL_ARTIFACT_PATH", "artifacts/signal_engine/btcusd_gru_packaged.json"),
        signal_confidence_threshold=float(os.getenv("SIGNAL_CONFIDENCE_THRESHOLD", "0.18")),
        signal_flat_score_threshold=float(os.getenv("SIGNAL_FLAT_SCORE_THRESHOLD", "-0.40")),
        signal_buy_score_threshold=float(os.getenv("SIGNAL_BUY_SCORE_THRESHOLD", "0.12")),
        signal_full_score_threshold=float(os.getenv("SIGNAL_FULL_SCORE_THRESHOLD", "0.72")),
        max_position_weight=float(os.getenv("MAX_POSITION_WEIGHT", "0.25")),
        portfolio_max_gross_weight=float(os.getenv("PORTFOLIO_MAX_GROSS_WEIGHT", "0.55")),
        portfolio_max_selected_assets=int(os.getenv("PORTFOLIO_MAX_SELECTED_ASSETS", "3")),
        rebalance_deadband_weight=float(os.getenv("REBALANCE_DEADBAND_WEIGHT", "0.03")),
        trade_cooldown_seconds=int(os.getenv("TRADE_COOLDOWN_SECONDS", "3600")),
        max_spread_bps=float(os.getenv("MAX_SPREAD_BPS", "35")),
        abnormal_volatility_threshold=float(os.getenv("ABNORMAL_VOLATILITY_THRESHOLD", "0.03")),
        paper_starting_cash_usd=float(os.getenv("PAPER_STARTING_CASH_USD", "10000")),
        paper_min_trade_notional_usd=float(os.getenv("PAPER_MIN_TRADE_NOTIONAL_USD", "25")),
        runtime_state_dir=os.getenv("RUNTIME_STATE_DIR", "runtime_state"),
        runtime_ledger_path=os.getenv("RUNTIME_LEDGER_PATH", "runtime_state/experiment_ledger.sqlite3"),
        engine_default_interval_seconds=int(os.getenv("ENGINE_DEFAULT_INTERVAL_SECONDS", "60")),
    )
