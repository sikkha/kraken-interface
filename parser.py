import time
from errors import DataError

PAIR_MAP = {
    "XXBTZUSD": "BTCUSD",
}

def normalize_pair(raw_pair: str) -> str:
    if raw_pair in PAIR_MAP:
        return PAIR_MAP[raw_pair]

    # fallback (basic cleaning)
    return raw_pair.replace("X", "").replace("Z", "")


def parse_ticker(raw: dict):
    if not raw:
        raise DataError("Empty ticker data")

    raw_pair = list(raw.keys())[0]
    data = raw[raw_pair]

    try:
        bid = float(data["b"][0])
        ask = float(data["a"][0])
        last = float(data["c"][0])
    except (KeyError, IndexError, ValueError):
        raise DataError("Malformed ticker fields")

    mid = (bid + ask) / 2
    spread = ask - bid

    return {
        "pair": normalize_pair(raw_pair),
        "bid": bid,
        "ask": ask,
        "last": last,
        "mid": mid,
        "spread": spread,
        "timestamp": int(time.time() * 1000)
    }
