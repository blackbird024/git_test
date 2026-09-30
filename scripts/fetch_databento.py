"""Download CME gold futures (GC, volume-based continuous front month) 1-minute OHLCV from Databento
and aggregate to 15M bars. Sub-15M data is used ONLY to build 15M bars; the strategy never sees it.

    python scripts/fetch_databento.py chunk START END      # one resumable chunk (run several in parallel)
    python scripts/fetch_databento.py plan                 # print the chunk list still missing
    python scripts/fetch_databento.py build                # merge chunks -> data/XAUUSD_M15.csv (+ .meta.json)

Chunks are written as data/raw/GC_<start>_<end>.dbn.zst (``.part`` while downloading), so a killed
download never re-bills finished chunks. Databento data is licensed: data/raw and the CSV are git-ignored.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import databento as db
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SYMBOL, DATASET = "GC.v.0", "GLBX.MDP3"
START, END = "2010-06-06", "2026-09-29"
# first request was streamed as one range and stopped by a time limit; its complete records end at
# 2012-08-07 19:57 UTC, so the chunk plan resumes at 19:58 (no overlap, nothing billed twice)
RESUME = "2012-08-07T19:58"


def plan() -> list[tuple[str, str]]:
    edges = [RESUME] + [f"{y}-01-01" for y in range(2013, 2027)] + [END]
    return [(a, b) for a, b in zip(edges[:-1], edges[1:])]


def chunk_path(a: str, b: str) -> Path:
    return RAW / f"GC_{a.replace(':', '')}_{b}.dbn.zst"


def fetch(a: str, b: str) -> None:
    out = chunk_path(a, b)
    if out.exists():
        return
    part = out.with_suffix(".part")
    db.Historical().timeseries.get_range(dataset=DATASET, symbols=[SYMBOL], stype_in="continuous",
                                         schema="ohlcv-1m", start=a, end=b, path=str(part))
    part.rename(out)


def build() -> None:
    frames = []
    first = RAW / f"GLBX_{SYMBOL}_ohlcv-1m_{START}_{END}.dbn.zst"  # truncated first stream (2010-06 .. 2012-08-07)
    files = [first] + [chunk_path(a, b) for a, b in plan()]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        sys.exit(f"missing chunks: {missing}")
    for f in files:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # the first file ends with one incomplete record, which is dropped
            d = db.DBNStore.from_file(str(f)).to_df().reset_index()
        frames.append(d)
    m1 = pd.concat(frames).rename(columns={"ts_event": "ts"})
    m1 = m1.drop_duplicates("ts").sort_values("ts")[["ts", "open", "high", "low", "close", "volume", "instrument_id"]]
    g = m1.set_index("ts").resample("15min", label="left", closed="left")
    m15 = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "volume": g["volume"].sum(),
                        "instrument_id": g["instrument_id"].first(),
                        "n_instruments": g["instrument_id"].nunique()}).dropna(subset=["open"]).reset_index()
    # a 15M bucket straddling a roll gets contract id -1, so it never matches either neighbour
    m15.loc[m15["n_instruments"] > 1, "instrument_id"] = -1
    m15["instrument_id"] = m15["instrument_id"].astype("int64")
    m15["timestamp"] = m15["ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    m15[["timestamp", "open", "high", "low", "close", "volume", "instrument_id"]].to_csv(
        ROOT / "data" / "XAUUSD_M15.csv", index=False)
    meta = {
        "source": f"Databento {DATASET} {SYMBOL} ohlcv-1m {START}..{END}, aggregated to 15M",
        "broker": "CME Globex (COMEX GC gold futures, 100 oz) - NOT spot XAUUSD",
        "format": "generic", "timestamp_tz": "UTC", "timestamp_convention": "bar_open",
        "price_side": "trade", "volume_type": "real (exchange-traded contracts)",
        "continuous": "volume-based front month, UNADJUSTED prices; rolls handled via instrument_id",
    }
    (ROOT / "data" / "XAUUSD_M15.meta.json").write_text(json.dumps(meta, indent=2))
    print(f"{len(m1)} 1m bars -> {len(m15)} 15m bars; {m15['ts'].min()} -> {m15['ts'].max()}")


if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1]
    if cmd == "plan":
        for a, b in plan():
            if not chunk_path(a, b).exists():
                print(a, b)
    elif cmd == "chunk":
        fetch(sys.argv[2], sys.argv[3])
    elif cmd == "build":
        build()
