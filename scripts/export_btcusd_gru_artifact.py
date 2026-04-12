#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path


SEED = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a packaged BTCUSD GRU artifact for runtime inference.")
    parser.add_argument("--pair", default="BTCUSD")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--limit", type=int, default=720)
    parser.add_argument("--epochs", type=int, default=250)
    parser.add_argument("--output", default="artifacts/signal_engine/btcusd_gru_packaged.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        import numpy as np
        import torch
        import torch.nn as nn
        from sklearn.preprocessing import MinMaxScaler
    except Exception as exc:
        print(
            "Artifact export requires optional dependencies that are not installed in this runtime:",
            exc,
            file=sys.stderr,
        )
        return 1

    os.environ["SIGNAL_ARTIFACT_PATH"] = args.output

    from backend.app.services.feature_service import build_feature_bundle, feature_matrix_from_rows
    from backend.app.services.market_service import get_market_candles
    from backend.app.signal_engine import load_signal_artifact, run_gru_series

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)

    class GRUModel(nn.Module):
        def __init__(self, input_size: int = 3, hidden_size: int = 50, output_size: int = 1) -> None:
            super().__init__()
            self.gru = nn.GRU(input_size, hidden_size, batch_first=True)
            self.linear = nn.Linear(hidden_size, output_size)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            out, _ = self.gru(x)
            return self.linear(out[:, -1, :])

    candles = get_market_candles(pair=args.pair, interval=args.interval, limit=args.limit)
    bundle = build_feature_bundle(candles)
    requested_source = os.getenv("KRAKEN_MARKET_SOURCE", "mock")
    if requested_source == "live" and bundle.source != "live":
        print(
            f"Requested live export, but candle source resolved to {bundle.source}. Refusing to package a fallback artifact.",
            file=sys.stderr,
        )
        return 1
    rows = bundle.rows
    if len(rows) < 80:
        print(f"Not enough candle history to export an artifact for {args.pair}.", file=sys.stderr)
        return 1

    features = np.asarray(feature_matrix_from_rows(rows), dtype=np.float32)
    target = np.asarray([row.macd for row in rows], dtype=np.float32)
    scaler = MinMaxScaler()
    x_scaled = scaler.fit_transform(features)
    x_tensor = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(1)
    y_tensor = torch.tensor(target, dtype=torch.float32)

    train_size = int(0.8 * len(x_tensor))
    x_train = x_tensor[:train_size]
    y_train = y_tensor[:train_size]

    model = GRUModel(input_size=3, hidden_size=50, output_size=1)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    losses: list[float] = []

    for _ in range(args.epochs):
        optimizer.zero_grad()
        prediction = model(x_train).squeeze()
        loss = criterion(prediction, y_train)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.item()))

    model.eval()
    with torch.no_grad():
        full_prediction = model(x_tensor).squeeze().cpu().numpy()
        train_rmse = float(np.sqrt(np.mean((full_prediction[:train_size] - target[:train_size]) ** 2)))
        eval_rmse = float(np.sqrt(np.mean((full_prediction[train_size:] - target[train_size:]) ** 2)))

    created_at_ms = int(time.time() * 1000)
    output_path = Path(args.output)
    artifact = {
        "artifact_format": "autocoda_gru_v1",
        "model_version": f"btcusd-gru-packaged-{created_at_ms}",
        "engine_type": "gru_packaged",
        "created_at_ms": created_at_ms,
        "symbol": args.pair,
        "sequence_length": 1,
        "input_size": 3,
        "hidden_size": 50,
        "output_size": 1,
        "lookahead_bars": 5,
        "feature_names": ["lagged_macd", "lagged_signal", "macd_diff"],
        "training": {
            "epochs": args.epochs,
            "seed": SEED,
            "train_size": train_size,
            "total_rows": len(rows),
            "interval_minutes": args.interval,
            "candle_limit": args.limit,
            "source": bundle.source,
            "final_loss": losses[-1] if losses else None,
            "train_rmse": train_rmse,
            "eval_rmse": eval_rmse,
        },
        "training_notes": (
            "Generated from a notebook-aligned BTCUSD packaging script. "
            "This is a single-asset runtime artifact, not the original cross-asset notebook portfolio."
        ),
        "scaler": {
            "kind": "MinMaxScaler",
            "data_min": scaler.data_min_.tolist(),
            "data_max": scaler.data_max_.tolist(),
        },
        "weights": {
            "weight_ih_l0": model.gru.weight_ih_l0.detach().cpu().tolist(),
            "weight_hh_l0": model.gru.weight_hh_l0.detach().cpu().tolist(),
            "bias_ih_l0": model.gru.bias_ih_l0.detach().cpu().tolist(),
            "bias_hh_l0": model.gru.bias_hh_l0.detach().cpu().tolist(),
            "linear_weight": model.linear.weight.detach().cpu().tolist(),
            "linear_bias": model.linear.bias.detach().cpu().tolist(),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2))

    artifact_status, loaded_artifact = load_signal_artifact()
    if loaded_artifact is None:
        print(f"Artifact wrote to {output_path}, but reload failed: {artifact_status.reason}", file=sys.stderr)
        return 1

    numpy_prediction = run_gru_series(feature_matrix=features.astype(float), artifact=loaded_artifact)
    max_abs_diff = float(np.max(np.abs(full_prediction - numpy_prediction)))
    mean_abs_diff = float(np.mean(np.abs(full_prediction - numpy_prediction)))

    if max_abs_diff > 1e-4:
        print(
            f"Artifact wrote to {output_path}, but validation drift is too high: max_abs_diff={max_abs_diff}",
            file=sys.stderr,
        )
        return 1

    output_path.write_text(
        json.dumps(
            artifact
            | {
                "validation": {
                    "numpy_runtime_max_abs_diff": max_abs_diff,
                    "numpy_runtime_mean_abs_diff": mean_abs_diff,
                    "validated": True,
                    "validated_at_ms": int(time.time() * 1000),
                }
            },
            indent=2,
        )
    )
    print(f"Wrote validated artifact to {output_path}")
    print(f"train_rmse={train_rmse:.6f}")
    print(f"eval_rmse={eval_rmse:.6f}")
    print(f"numpy_runtime_max_abs_diff={max_abs_diff:.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
