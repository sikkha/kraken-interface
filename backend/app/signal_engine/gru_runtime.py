from __future__ import annotations

import numpy as np

from backend.app.signal_engine.artifact_loader import LoadedSignalArtifact


def run_gru_series(feature_matrix: np.ndarray, artifact: LoadedSignalArtifact) -> np.ndarray:
    scaled = _scale_features(feature_matrix, artifact.scaler_min, artifact.scaler_max)
    sequence_length = artifact.status.sequence_length or 1
    if sequence_length <= 1:
        return np.asarray([_run_gru_window(row.reshape(1, -1), artifact) for row in scaled], dtype=float)

    outputs: list[float] = []
    for index in range(len(scaled)):
        start = max(0, index - sequence_length + 1)
        window = scaled[start : index + 1]
        outputs.append(_run_gru_window(window, artifact))
    return np.asarray(outputs, dtype=float)


def _run_gru_window(window: np.ndarray, artifact: LoadedSignalArtifact) -> float:
    hidden_size = artifact.status.hidden_size or 0
    hidden_state = np.zeros(hidden_size, dtype=float)

    weight_ih = artifact.weight_ih_l0
    weight_hh = artifact.weight_hh_l0
    bias_ih = artifact.bias_ih_l0
    bias_hh = artifact.bias_hh_l0

    for features in window:
        gates_x = weight_ih @ features + bias_ih
        gates_h = weight_hh @ hidden_state + bias_hh
        gate_size = hidden_size

        reset_gate = _sigmoid(gates_x[0:gate_size] + gates_h[0:gate_size])
        update_gate = _sigmoid(gates_x[gate_size : gate_size * 2] + gates_h[gate_size : gate_size * 2])
        new_gate = np.tanh(
            gates_x[gate_size * 2 : gate_size * 3]
            + reset_gate * gates_h[gate_size * 2 : gate_size * 3]
        )
        hidden_state = (1 - update_gate) * new_gate + update_gate * hidden_state
    return float((artifact.linear_weight @ hidden_state + artifact.linear_bias).squeeze())


def _scale_features(feature_matrix: np.ndarray, data_min: np.ndarray, data_max: np.ndarray) -> np.ndarray:
    denom = np.where(np.abs(data_max - data_min) < 1e-9, 1.0, data_max - data_min)
    scaled = (feature_matrix - data_min) / denom
    return np.clip(scaled, 0.0, 1.0)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))
