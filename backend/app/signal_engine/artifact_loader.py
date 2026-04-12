from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from backend.app.core.config import get_settings


@dataclass(frozen=True)
class SignalArtifactStatus:
    engine_type: str
    status: str
    loaded: bool
    path: str
    model_version: str
    hidden_size: int | None
    sequence_length: int | None
    reason: str | None = None


@dataclass(frozen=True)
class LoadedSignalArtifact:
    status: SignalArtifactStatus
    feature_names: tuple[str, ...]
    lookahead_bars: int
    scaler_min: np.ndarray
    scaler_max: np.ndarray
    weight_ih_l0: np.ndarray
    weight_hh_l0: np.ndarray
    bias_ih_l0: np.ndarray
    bias_hh_l0: np.ndarray
    linear_weight: np.ndarray
    linear_bias: np.ndarray


def load_signal_artifact() -> tuple[SignalArtifactStatus, LoadedSignalArtifact | None]:
    settings = get_settings()
    path = Path(settings.signal_artifact_path)
    if not path.exists():
        return (
            SignalArtifactStatus(
                engine_type="notebook_proxy",
                status="missing",
                loaded=False,
                path=str(path),
                model_version="notebook-proxy-online-v2",
                hidden_size=None,
                sequence_length=None,
                reason="Signal artifact file is not present in the repository runtime.",
            ),
            None,
        )

    try:
        payload = json.loads(path.read_text())
        _validate_payload(payload)
        artifact = LoadedSignalArtifact(
            status=SignalArtifactStatus(
                engine_type="gru_packaged",
                status="loaded",
                loaded=True,
                path=str(path),
                model_version=str(payload["model_version"]),
                hidden_size=int(payload["hidden_size"]),
                sequence_length=int(payload.get("sequence_length", 1)),
                reason=None,
            ),
            feature_names=tuple(str(name) for name in payload["feature_names"]),
            lookahead_bars=int(payload.get("lookahead_bars", settings.signal_lookahead_bars)),
            scaler_min=np.asarray(payload["scaler"]["data_min"], dtype=float),
            scaler_max=np.asarray(payload["scaler"]["data_max"], dtype=float),
            weight_ih_l0=np.asarray(payload["weights"]["weight_ih_l0"], dtype=float),
            weight_hh_l0=np.asarray(payload["weights"]["weight_hh_l0"], dtype=float),
            bias_ih_l0=np.asarray(payload["weights"]["bias_ih_l0"], dtype=float),
            bias_hh_l0=np.asarray(payload["weights"]["bias_hh_l0"], dtype=float),
            linear_weight=np.asarray(payload["weights"]["linear_weight"], dtype=float),
            linear_bias=np.asarray(payload["weights"]["linear_bias"], dtype=float),
        )
        return artifact.status, artifact
    except Exception as exc:
        return (
            SignalArtifactStatus(
                engine_type="notebook_proxy",
                status="invalid",
                loaded=False,
                path=str(path),
                model_version="notebook-proxy-online-v2",
                hidden_size=None,
                sequence_length=None,
                reason=f"Signal artifact could not be loaded: {exc}",
            ),
            None,
        )


def _validate_payload(payload: dict[str, Any]) -> None:
    required_top = {
        "artifact_format",
        "model_version",
        "hidden_size",
        "feature_names",
        "scaler",
        "weights",
    }
    missing_top = required_top.difference(payload)
    if missing_top:
        raise ValueError(f"Missing artifact keys: {sorted(missing_top)}")

    if str(payload["artifact_format"]) != "autocoda_gru_v1":
        raise ValueError("Unsupported artifact format.")

    feature_names = payload["feature_names"]
    if not isinstance(feature_names, list) or len(feature_names) != 3:
        raise ValueError("Artifact must declare exactly three feature names.")

    weights = payload["weights"]
    for key in [
        "weight_ih_l0",
        "weight_hh_l0",
        "bias_ih_l0",
        "bias_hh_l0",
        "linear_weight",
        "linear_bias",
    ]:
        if key not in weights:
            raise ValueError(f"Missing weight tensor: {key}")

    hidden_size = int(payload["hidden_size"])
    if hidden_size <= 0:
        raise ValueError("Hidden size must be positive.")

    scaler = payload["scaler"]
    if "data_min" not in scaler or "data_max" not in scaler:
        raise ValueError("Scaler metadata is incomplete.")
    if len(scaler["data_min"]) != len(feature_names) or len(scaler["data_max"]) != len(feature_names):
        raise ValueError("Scaler dimensions do not match feature count.")
