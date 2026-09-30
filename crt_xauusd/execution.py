"""Trade simulation on 15M bars (no intrabar data is used or assumed).

Rules (pre-registered):
- Entry: OPEN of the 15M bar right after the confirmation bar (+delay bars for robustness).
- SL: sweep extreme -/+ fixed buffer. TP: fixed R multiple (BASE 1R).
- If SL and TP are both inside the same 15M bar -> SL is assumed first (conservative).
- Gap through SL -> filled at the bar OPEN (worse). Gap through TP -> filled at TP (no gap bonus).
- Forced exit at CLOSE of the last 15M bar that ends at/before 17:00 New York (daily close /
  rollover), so no trade is held through the maintenance break or a weekend.
- Costs are charged in price units per ounce: cost_mult * (spread + commission) + 2 * slippage_per_side.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import BAR


class Market:
    def __init__(self, df: pd.DataFrame, cfg: dict):
        self.o, self.h, self.l, self.c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.ts = df["ts"].to_numpy()
        wall = df["ny"].dt.tz_localize(None)
        close_hour = pd.Timedelta(hours=cfg["time"]["session_close_hour_ny"])
        close_wall = wall.dt.normalize() + close_hour
        close_wall = close_wall.where(wall < close_wall, close_wall + pd.Timedelta(days=1))
        close_utc = close_wall.dt.tz_localize(cfg["time"]["canonical_tz"], ambiguous="NaT",
                                              nonexistent="shift_forward").dt.tz_convert("UTC")
        target = (close_utc - BAR).to_numpy().astype(self.ts.dtype)
        # last bar whose open <= session_close - 15min
        self.last_idx = np.searchsorted(self.ts, target, side="right") - 1
        self.n = len(self.o)
        self.instr = df["instrument_id"].to_numpy() if "instrument_id" in df else None

    def same_contract(self, a: int, b: int) -> bool:
        return self.instr is None or bool((self.instr[a:b + 1] == self.instr[a]).all())


def simulate(m: Market, entry_i: int, direction: str, entry: float, sl: float, tp: float | None, last_i: int) -> dict:
    sgn = 1.0 if direction == "long" else -1.0
    seg = slice(entry_i, last_i + 1)
    lo, hi, op = m.l[seg], m.h[seg], m.o[seg]
    if direction == "long":
        sl_hit = lo <= sl
        tp_hit = hi >= tp if tp is not None else np.zeros_like(sl_hit)
    else:
        sl_hit = hi >= sl
        tp_hit = lo <= tp if tp is not None else np.zeros_like(sl_hit)
    k_sl = int(np.argmax(sl_hit)) if sl_hit.any() else None
    k_tp = int(np.argmax(tp_hit)) if tp_hit.any() else None
    if k_sl is not None and (k_tp is None or k_sl <= k_tp):
        k, reason = k_sl, "stop"
        gapped = (op[k] <= sl) if direction == "long" else (op[k] >= sl)
        exit_price = op[k] if (gapped and k > 0) else sl
    elif k_tp is not None:
        k, reason, exit_price = k_tp, "target", tp
    else:
        k, reason, exit_price = len(lo) - 1, "session_close", m.c[last_i]
    # excursions (price units, favourable positive). Exit bar handled conservatively.
    fav = (hi - entry) if direction == "long" else (entry - lo)
    adv = (entry - lo) if direction == "long" else (hi - entry)
    fav_path = fav[:k + 1].copy()
    if reason == "stop":
        fav_path[k] = 0.0  # stop-first assumption: exit-bar favourable extreme is not credited
    elif reason == "target":
        fav_path[k] = min(fav_path[k], sgn * (tp - entry))
    adv_path = adv[:k + 1]
    mfe = max(0.0, float(fav_path.max()))
    mae = max(0.0, float(adv_path.max()))
    return {
        "exit_i": entry_i + k, "exit_price": float(exit_price), "exit_reason": reason,
        "mfe_price": mfe, "mae_price": mae,
        "bars_to_mfe": int(np.argmax(fav_path)) + 1 if mfe > 0 else 0,
        "bars_to_mae": int(np.argmax(adv_path)) + 1 if mae > 0 else 0,
        "bars_held": k + 1,
    }


def all_take_profits(cfg: dict) -> dict:
    return {**cfg["execution"]["take_profits"], **cfg["execution"].get("sensitivity_take_profits", {})}


def cost_price(cfg: dict, cost_mult: float = 1.0, slippage_per_side: float | None = None) -> float:
    c = cfg["costs"]
    slip = c["slippage_price_per_side"] * cost_mult if slippage_per_side is None else slippage_per_side
    return cost_mult * (c["spread_price"] + c["commission_price_roundtrip"]) + 2 * slip


def build_trades(signals: pd.DataFrame, m: Market, cfg: dict, tp_key: str, delay: int = 0,
                 cost_mult: float = 1.0, slippage_per_side: float | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    tp_def = all_take_profits(cfg)[tp_key]
    buf = cfg["execution"]["stop_buffer_price"]
    cost = cost_price(cfg, cost_mult, slippage_per_side)
    trades, skipped = [], []
    busy_until = {}  # per kill zone: no stacking
    for s in (signals.to_dict("records") if len(signals) else []):
        ci = int(s["conf_i"])
        ei = ci + 1 + delay
        base = {"setup_id": s["setup_id"], "kz": s["kz"], "direction": s["direction"]}
        if ei >= m.n or m.ts[ei] - m.ts[ci] != np.timedelta64(15 * (1 + delay), "m"):
            skipped.append({**base, "reason": "entry_bar_missing_gap"})
            continue
        last_i = int(m.last_idx[ci])
        if ei > last_i:
            skipped.append({**base, "reason": "entry_after_session_close"})
            continue
        entry_time = pd.Timestamp(m.ts[ei])
        if s["kz"] in busy_until and entry_time < busy_until[s["kz"]]:
            skipped.append({**base, "reason": "position_already_open_same_kz"})
            continue
        long_ = s["direction"] == "long"
        entry = m.o[ei]
        sl = s["sweep_price"] - buf if long_ else s["sweep_price"] + buf
        risk = entry - sl if long_ else sl - entry
        if risk <= 0:
            skipped.append({**base, "reason": "entry_beyond_stop"})
            continue
        tp = entry + tp_def["value"] * risk if long_ else entry - tp_def["value"] * risk
        sim = simulate(m, ei, s["direction"], entry, sl, tp, last_i)
        if not m.same_contract(ci, sim["exit_i"]):
            skipped.append({**base, "reason": "contract_roll_during_trade"})
            continue
        sgn = 1 if long_ else -1
        gross = sgn * (sim["exit_price"] - entry)
        exit_time = pd.Timestamp(m.ts[sim["exit_i"]]) + BAR
        busy_until[s["kz"]] = exit_time
        trades.append({
            **s, "tp_key": tp_key, "entry_delay_bars": delay, "entry_time": entry_time, "entry_price": entry,
            "stop_price": sl, "stop_distance": risk, "target_price": tp, "target_R": abs(tp - entry) / risk,
            "exit_time": exit_time, "cost_price": cost, "gross_pnl_price": gross, "net_pnl_price": gross - cost,
            "gross_R": gross / risk, "R": (gross - cost) / risk,
            "MFE_R": sim["mfe_price"] / risk, "MAE_R": sim["mae_price"] / risk,
            "minutes_held": sim["bars_held"] * 15, "minutes_to_MFE": sim["bars_to_mfe"] * 15,
            "minutes_to_MAE": sim["bars_to_mae"] * 15, **sim,
        })
    return pd.DataFrame(trades), pd.DataFrame(skipped)


def combine_groups(trades: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """LONDON, NY and LONDON+NY (independent setups; overlap flagged, not removed)."""
    out = {"LONDON": trades[trades["kz"] == "london"] if len(trades) else trades,
           "NY": trades[trades["kz"] == "ny"] if len(trades) else trades}
    if len(trades):
        t = trades.sort_values("entry_time").copy()
        ov = np.zeros(len(t), bool)
        ent, ext, kz = t["entry_time"].to_numpy(), t["exit_time"].to_numpy(), t["kz"].to_numpy()
        for i in range(len(t)):
            j = (kz != kz[i]) & (ent < ext[i]) & (ext > ent[i])
            ov[i] = j.any()
        t["overlaps_other_kz_trade"] = ov
        out["LONDON+NY"] = t
    else:
        out["LONDON+NY"] = trades
    return out
