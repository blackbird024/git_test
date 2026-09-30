"""Download CME gold futures (GC, volume-based continuous front month) 1-minute OHLCV from Databento
and aggregate to 15M bars. Sub-15M data is used ONLY to build 15M bars; the strategy never sees it.

    DATABENTO_API_KEY=... python scripts/fetch_databento.py --start 2010-06-06 --end 2026-09-29

Writes data/XAUUSD_M15.csv (+ .meta.json). Raw DBN is cached under data/raw/ (git-ignored:
Databento data is licensed and must not be redistributed).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import databento as db
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2010-06-06")
    ap.add_argument("--end", default="2026-09-29")
    ap.add_argument("--symbol", default="GC.v.0")
    a = ap.parse_args()
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    dbn = raw_dir / f"GLBX_{a.symbol}_ohlcv-1m_{a.start}_{a.end}.dbn.zst"
    if not dbn.exists():
        db.Historical().timeseries.get_range(dataset="GLBX.MDP3", symbols=[a.symbol], stype_in="continuous",
                                             schema="ohlcv-1m", start=a.start, end=a.end, path=str(dbn))
    m1 = db.DBNStore.from_file(str(dbn)).to_df().reset_index()  # ts_event = bar OPEN, UTC
    m1 = m1.rename(columns={"ts_event": "ts"})[["ts", "open", "high", "low", "close", "volume", "instrument_id"]]
    g = m1.set_index("ts").resample("15min", label="left", closed="left")
    m15 = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "volume": g["volume"].sum(),
                        "instrument_id": g["instrument_id"].first(),
                        "n_instruments": g["instrument_id"].nunique()}).dropna(subset=["open"]).reset_index()
    # a 15M bucket straddling a roll is flagged as its own contract id (-1) so it never matches either side
    m15.loc[m15["n_instruments"] > 1, "instrument_id"] = -1
    m15["instrument_id"] = m15["instrument_id"].astype("int64")
    out = ROOT / "data" / "XAUUSD_M15.csv"
    m15.drop(columns=["n_instruments"]).assign(timestamp=m15["ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")) \
        .drop(columns=["ts"])[["timestamp", "open", "high", "low", "close", "volume", "instrument_id"]] \
        .to_csv(out, index=False)
    meta = {
        "source": f"Databento GLBX.MDP3 {a.symbol} ohlcv-1m {a.start}..{a.end}, aggregated to 15M",
        "broker": "CME Globex (COMEX GC gold futures, 100 oz) - NOT spot XAUUSD",
        "format": "generic", "timestamp_tz": "UTC", "timestamp_convention": "bar_open",
        "price_side": "trade", "volume_type": "real (exchange-traded contracts)",
        "continuous": "volume-based front month, UNADJUSTED prices; roll handled by instrument_id",
    }
    (ROOT / "data" / "XAUUSD_M15.meta.json").write_text(json.dumps(meta, indent=2))
    print(len(m1), "1m bars ->", len(m15), "15m bars;", m15["ts"].min(), "->", m15["ts"].max())


if __name__ == "__main__":
    main()
