# GRU Algorithm Verification

This pass verifies the algorithmic meaning of the current notebook -> artifact -> runtime path without changing behavior.

## Executive answer

- The notebook model is trained to predict **current MACD**, not future return, not future allocation, and not an execution label.
- `sequence_length = 1` is **algorithmically correct relative to the notebook implementation**.
- The packaged artifact is a **faithful packaging of the notebook model core**, but it is **not** a faithful packaging of the entire notebook strategy.
- The current live behavior `buy / 1.0 / 0.25` is caused mostly by the **downstream signal/confidence/target-weight mapping**, with an important upstream contributor from the notebook target design itself.

## A. Notebook algorithm semantics

Source inspected:

- [trading_strategy_asset/autocoda_cross_asset_vs_spy_multi_horizon.ipynb](/Users/kan/code/kraken-interface/trading_strategy_asset/autocoda_cross_asset_vs_spy_multi_horizon.ipynb)

### What the notebook model is trained to predict

In `fit_autocoda_asset_model`:

- features = `["Lagged_MACD", "Lagged_Signal", "MACD_diff"]`
- target = `df["MACD"]`

So the notebook GRU is trained to predict **MACD at the same row**, not:

- future MACD return
- future price return
- future MACD diff
- trade action
- portfolio allocation

### What the training target means operationally

Operationally, the notebook model is predicting a **momentum/regime state variable** rather than a trade label.

That prediction is later transformed into a confidence-like score:

- `Predicted_MACD`
- `ForwardMeanPred` = forward-looking rolling mean over predicted MACD
- `ConfidenceRaw = ForwardMeanPred`
- positive-only clipping
- persistence multiplier
- optional inverse-volatility scaling

Then the notebook converts those confidence values into **cross-asset relative weights** using `normalize_weights`.

So the notebook should be interpreted as:

- **not** a direct active trading model
- **not** a direct allocation-label model
- closer to a **regime / allocation bias model**

### Sequence structure in the notebook

The notebook does:

- `X = torch.tensor(X, dtype=torch.float32).unsqueeze(1)`

That turns feature rows into shape:

- `[num_samples, 1, 3]`

So the notebook GRU already uses an effective sequence length of **1**.

That means:

- the notebook does **not** train on a longer temporal sequence
- it does **not** unroll across multiple timesteps
- it uses a GRU cell architecture, but each sample is a single-step input

### Feature set in the notebook

Notebook indicators are:

- `EMA12`
- `EMA26`
- `MACD`
- `Signal Line`
- `MACD_diff`
- `Lagged_MACD`
- `Lagged_Signal`
- `Return`
- `RollingVol`
- `Price`

Model input features are only:

- `Lagged_MACD`
- `Lagged_Signal`
- `MACD_diff`

### Scaling assumptions

The notebook uses:

- `MinMaxScaler()` fit on the feature matrix

The target `MACD` is **not** normalized.

### Important target-design observation

The target is close to being algebraically recoverable from the features.

Because:

- `Signal_t = alpha * MACD_t + (1 - alpha) * Signal_{t-1}` with `alpha = 2 / (9 + 1) = 0.2`
- `MACD_diff_t = MACD_t - Signal_t`

Then:

- `MACD_diff_t = (1 - alpha) * (MACD_t - Signal_{t-1})`
- `MACD_t = Signal_{t-1} + MACD_diff_t / (1 - alpha)`
- `MACD_t = Lagged_Signal_t + MACD_diff_t / 0.8`

So the notebook target is not strongly future-looking; it is very close to a transformed current-state reconstruction.

## B. Exported artifact semantics

Sources inspected:

- [artifacts/signal_engine/btcusd_gru_packaged.json](/Users/kan/code/kraken-interface/artifacts/signal_engine/btcusd_gru_packaged.json)
- [scripts/export_btcusd_gru_artifact.py](/Users/kan/code/kraken-interface/scripts/export_btcusd_gru_artifact.py)

### Whether the artifact faithfully encodes the notebook model structure

Yes, for the **model core**:

- `input_size = 3`
- `hidden_size = 50`
- `output_size = 1`
- `sequence_length = 1`
- feature order = `["lagged_macd", "lagged_signal", "macd_diff"]`
- `MinMaxScaler` min/max state included
- GRU and linear weights included

### Why `sequence_length = 1`

Because the notebook itself trained with `unsqueeze(1)`, which yields one timestep per sample.

So `sequence_length = 1` is not an accidental packaging loss. It matches the notebook implementation.

### Whether artifact output meaning matches notebook target

Yes.

The export script trains on:

- features from `feature_matrix_from_rows(rows)`
- target = `[row.macd for row in rows]`

So the artifact output still means:

- **predicted current MACD**

### Whether model meaning was narrowed during export

Yes, but not inside the core model structure.

The narrowing happens because the export is **not** packaging the full notebook strategy:

- notebook original context is multi-asset cross-sectional allocation
- notebook uses forward-looking `ForwardMeanPred`
- notebook normalizes relative weights across assets
- export script retrains only for single-asset BTCUSD
- export script uses Kraken BTCUSD hourly candles instead of notebook `yfinance` universe/horizons

So the artifact is:

- a faithful packaging of the notebook **GRU predictor form**
- but a narrowed approximation of the notebook **full strategy**

### Feature names/order and scaler state

These do match the notebook assumptions:

- same three features
- same order
- same MinMaxScaler concept

## C. Runtime inference path

Sources inspected:

- [backend/app/signal_engine/artifact_loader.py](/Users/kan/code/kraken-interface/backend/app/signal_engine/artifact_loader.py)
- [backend/app/signal_engine/gru_runtime.py](/Users/kan/code/kraken-interface/backend/app/signal_engine/gru_runtime.py)
- [backend/app/services/feature_service.py](/Users/kan/code/kraken-interface/backend/app/services/feature_service.py)
- [backend/app/services/signal_service.py](/Users/kan/code/kraken-interface/backend/app/services/signal_service.py)

### Exact runtime input shape

Runtime builds:

- `feature_matrix` shape `[N, 3]`

Then for `sequence_length = 1`, the GRU runtime evaluates each row as:

- `row.reshape(1, -1)` -> shape `[1, 3]`

with hidden state reset per row.

That is the correct runtime analog of notebook training on `[N, 1, 3]`.

### Whether runtime feature generation matches notebook/export expectations

Largely yes:

- same EMA12 / EMA26 / MACD / signal line family
- same `lagged_macd`
- same `lagged_signal`
- same `macd_diff`
- same rolling volatility concept with lookback 20

The runtime feature path is reasonably faithful to the notebook feature family.

### Whether sequence semantics are preserved or collapsed

Sequence semantics are preserved **as implemented by the notebook**, which is one-step.

There is no lost longer temporal sequence, because the notebook did not train one.

### What the raw runtime output numerically represents

The raw model output numerically represents:

- a predicted **MACD value in target units**

It is not directly:

- a probability
- a confidence score
- an allocation
- a buy/sell label

### How raw model output becomes signal / confidence / target weight

In [signal_service.py](/Users/kan/code/kraken-interface/backend/app/services/signal_service.py):

1. `predicted_macd_series` is produced by the GRU runtime
2. `confidence_raw` = trailing mean over the last `lookahead_bars`
3. `confidence` = positive-only raw value times persistence and volatility scaling
4. `confidence` is then clamped to `[0, 1]`
5. signal mapping:
   - `predicted_macd > 0` and `confidence >= threshold` -> `buy`
   - `predicted_macd < 0` -> `sell`
   - else -> `hold`
6. target weight mapping:
   - `min(max_position_weight, confidence * max_position_weight)`

Given `max_position_weight = 0.25`, any saturated confidence becomes target weight `0.25`.

### Where the current degeneracy comes from

Evidence from [runtime_state/latest_signal.json](/Users/kan/code/kraken-interface/runtime_state/latest_signal.json):

- `predicted_macd = 6.393237`
- `confidence_raw = 7.001667`
- `persistence_ratio = 0.9583`
- final `confidence = 1.0`
- final `target_weight = 0.25`

So the current degeneracy comes from a combination:

1. **model output sign**
   - current packaged model output is positive, which keeps producing `buy`
2. **confidence calibration**
   - raw predicted MACD is treated like a confidence precursor even though it is not normalized
   - that value is large enough to saturate the clamp to `1.0`
3. **target-weight mapping**
   - once confidence is `1.0`, target weight becomes fixed at `0.25`
4. **risk layer**
   - then correctly prevents repeated buying once the portfolio is already near the target allocation

So the current behavior is **not** caused only by the model. The main degeneracy is introduced in the downstream signal policy.

## D. Notebook intent vs runtime behavior

| Layer | Meaning |
|---|---|
| Notebook training target | Current MACD |
| Exported artifact target | Current MACD |
| Runtime interpreted raw output | Predicted current MACD |
| Runtime signal policy meaning | Positive MACD regime -> buy bias, scaled into capped BTC allocation |
| Actual live behavior | Repeated buy bias, saturated confidence, fixed 25% target, then mostly noop because allocation is already satisfied |

## E. Is `sequence_length = 1` correct?

### Short answer

Yes, relative to the notebook implementation.

### Why it is still called a GRU

It is still technically a GRU because the architecture is a GRU cell followed by a linear head.

But with sequence length 1, it behaves more like:

- a gated one-step nonlinear regressor

than:

- a richer temporal sequence model

So `GRU` is architecturally true, but the temporal meaning is limited.

## F. Best interpretation of the current model

The current packaged model is best interpreted as a:

- **trend / regime confirmation model**
- used as an **allocation bias model**

It is **not** best interpreted as:

- a direct active trading engine
- a future-return predictor
- a sell/buy policy by itself

## G. Recommendation for the next fix layer

Recommended next fix priority:

1. **signal mapping / policy layer**
   - this is where `buy / 1.0 / 0.25` is currently being manufactured
2. **notebook/model design**
   - the current target is contemporaneous MACD, which is not a strong forward trading objective
3. **timing / horizon assumptions**
   - the notebook’s `ForwardMeanPred` logic and cross-asset relative weighting were not fully preserved in the single-asset runtime

Not recommended as the first fix:

- changing sequence length alone

Because `sequence_length = 1` matches the notebook as written. The larger issue is what the model is predicting and how that prediction is converted into action.

