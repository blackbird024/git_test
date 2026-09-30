"""CRT setup detection (pre-registration v2).

Sequence (and nothing else):
    reference 4H extreme -> FIRST 15M bar of the execution 4H that strictly penetrates it (sweep)
    -> the IMMEDIATELY NEXT 15M bar must be a body engulfing in the opposite direction with
       volume >= k * SMA20(previous 20 bars) -> signal at its close -> entry at next bar open.

If the next bar fails any condition the setup direction is INVALIDATED. There is no waiting
window, no later candle, no second sweep.

Every decision uses only bars that are closed at decision time (bar i is closed at ts[i] + 15min).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import BAR, volume_passes

H4 = pd.Timedelta(hours=4)


def confirm_engulfing(sweep_bar: dict, confirm_bar: dict, direction: str) -> tuple[bool, list[str], dict]:
    """Pure body-engulfing rule on two consecutive closed 15M bars (volume checked separately).

    LONG : Close_s < Open_s, Close_c > Open_c, Open_c <= Close_s, Close_c >= Open_s
    SHORT: Close_s > Open_s, Close_c < Open_c, Open_c >= Close_s, Close_c <= Open_s
    """
    os_, cs = sweep_bar["open"], sweep_bar["close"]
    oc, cc, hc, lc = confirm_bar["open"], confirm_bar["close"], confirm_bar["high"], confirm_bar["low"]
    reasons = []
    if direction == "long":
        if not cs < os_:
            reasons.append("sweep_bar_not_bearish")
        if not cc > oc:
            reasons.append("confirm_bar_not_bullish")
        if not oc <= cs:
            reasons.append("confirm_open_above_sweep_close")
        if not cc >= os_:
            reasons.append("confirm_close_below_sweep_open")
        margin = cc - os_
    elif direction == "short":
        if not cs > os_:
            reasons.append("sweep_bar_not_bullish")
        if not cc < oc:
            reasons.append("confirm_bar_not_bearish")
        if not oc >= cs:
            reasons.append("confirm_open_below_sweep_close")
        if not cc <= os_:
            reasons.append("confirm_close_above_sweep_open")
        margin = os_ - cc
    else:
        raise ValueError(direction)
    body_s, body_c, rng_c = abs(cs - os_), abs(cc - oc), hc - lc
    rec = {
        "sweep_body": body_s, "confirm_body": body_c, "confirm_range": rng_c,
        "confirm_wick": rng_c - body_c, "confirm_body_ratio": body_c / rng_c if rng_c > 0 else np.nan,
        "engulf_body_ratio": body_c / body_s if body_s > 0 else np.nan, "engulf_close_margin": margin,
    }
    return not reasons, reasons, rec


# ------------------------------------------------------------------ setups
def enumerate_setups(h4: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One setup = (execution 4H bucket, kill zone) with a non-empty time overlap.

    London 02-05 NY -> exec bucket 01-05 (ref 21-01).
    NY 07-10 NY     -> exec 05-09 (KZ part 07-09, ref 01-05) and exec 09-13 (KZ part 09-10, ref 05-09).
    """
    rows = []
    starts = set(h4.index)
    for ex in h4.index:
        for kz_name, kz in cfg["kill_zones"].items():
            for day in (ex.normalize(), ex.normalize() + pd.Timedelta(days=1)):
                ks = day + pd.Timedelta(kz["start"] + ":00")
                ke = day + pd.Timedelta(kz["end"] + ":00")
                s, e = max(ks, ex), min(ke, ex + H4)
                if s < e:
                    ref = ex - H4
                    rows.append({"setup_id": f"{ex:%Y%m%d_%H%M}_{kz_name}", "kz": kz_name, "exec_start": ex,
                                 "ref_start": ref, "kz_start": s, "kz_end": e, "ref_exists": ref in starts})
    return pd.DataFrame(rows)


class Detector:
    def __init__(self, df: pd.DataFrame, h4: pd.DataFrame, cfg: dict):
        self.df, self.h4, self.cfg = df, h4, cfg
        self.o, self.h, self.l, self.c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.ts = df["ts"].to_numpy()
        self.wall = df["ny"].dt.tz_localize(None).to_numpy()
        self.abn = df["abnormal_bar"].to_numpy(bool)
        self.xsp = df["extreme_spread"].to_numpy(bool)
        self.bar = np.timedelta64(15, "m")

    def _bar(self, i):
        return {"open": self.o[i], "high": self.h[i], "low": self.l[i], "close": self.c[i]}

    def scan_direction(self, setup, direction: str, variant: dict, require_sweep: bool = True):
        """Returns (signal | None, event dict). ``require_sweep=False`` is the falsification ablation:
        the first bar in the KZ whose NEXT bar forms a qualifying engulfing is used, no sweep needed."""
        ref = self.h4.loc[setup.ref_start]
        ex = self.h4.loc[setup.exec_start]
        a, b = int(ex.first_idx), int(ex.last_idx)
        level = ref.low if direction == "long" else ref.high
        ks, ke = np.datetime64(setup.kz_start), np.datetime64(setup.kz_end)
        ev = {"direction": direction, "event": None, "reasons": []}

        s = None
        for i in range(a, b + 1):
            if self.wall[i] >= ke:
                break
            if i > a and self.ts[i] - self.ts[i - 1] != self.bar:
                ev.update(event="invalid", reasons=["data_gap_before_sweep"], i=i)
                return None, ev
            if require_sweep:
                pen = self.l[i] < level if direction == "long" else self.h[i] > level
                if pen:
                    s = i
                    break
            else:
                j = i + 1
                if j <= b and self.ts[j] - self.ts[i] == self.bar and ks <= self.wall[j] and self.wall[j] + self.bar <= ke:
                    ok, _, _ = confirm_engulfing(self._bar(i), self._bar(j), direction)
                    if ok and volume_passes(self.df.iloc[j], variant)[0]:
                        s = i
                        break
        if s is None:
            ev.update(event="no_sweep" if require_sweep else "no_pattern")
            return None, ev

        j = s + 1
        reasons = []
        if j > b:
            reasons.append("confirm_bar_outside_exec_4h")
        elif self.ts[j] - self.ts[s] != self.bar:
            reasons.append("confirm_bar_missing_gap")
        if reasons:
            ev.update(event="invalid", reasons=reasons, i=s)
            return None, ev
        if not (ks <= self.wall[j] and self.wall[j] + self.bar <= ke):
            reasons.append("confirm_bar_outside_kill_zone")
        ok, eng_reasons, rec = confirm_engulfing(self._bar(s), self._bar(j), direction)
        reasons += eng_reasons
        vok, vmeas = volume_passes(self.df.iloc[j], variant)
        if not vok:
            reasons.append("volume_below_threshold")
        if self.abn[s] or self.abn[j]:
            reasons.append("abnormal_bar")
        if self.xsp[j]:
            reasons.append("extreme_spread")
        ev.update(event="rejected" if reasons else "signal", reasons=reasons, i=s)
        if reasons:
            return None, ev
        return self._record(setup, ref, direction, s, j, a, rec, vmeas), ev

    def _record(self, setup, ref, direction, s, j, a, rec, vmeas):
        rng = ref.high - ref.low
        level = ref.low if direction == "long" else ref.high
        # stop anchor: extreme of sweep + confirmation bars (both closed before entry)
        ext = min(self.l[s], self.l[j]) if direction == "long" else max(self.h[s], self.h[j])
        depth = (level - self.l[s]) if direction == "long" else (self.h[s] - level)
        r = self.df.iloc[j]
        back_inside = self.c[j] > ref.low if direction == "long" else self.c[j] < ref.high
        return {
            "setup_id": setup.setup_id, "kz": setup.kz, "direction": direction,
            "ref_start_ny": setup.ref_start, "exec_start_ny": setup.exec_start,
            "ref_high": ref.high, "ref_low": ref.low, "ref_range": rng,
            "sweep_i": s, "sweep_time": pd.Timestamp(self.ts[s]),
            "sweep_open": self.o[s], "sweep_high": self.h[s], "sweep_low": self.l[s], "sweep_close": self.c[s],
            "sweep_price": ext, "sweep_depth": depth, "sweep_depth_pct_range": depth / rng if rng > 0 else np.nan,
            "minutes_exec_start_to_sweep": (s - a) * 15,
            "sweep_in_kz": bool(np.datetime64(setup.kz_start) <= self.wall[s]),
            "conf_i": j, "conf_bar_time": pd.Timestamp(self.ts[j]),
            "confirm_open": self.o[j], "confirm_high": self.h[j], "confirm_low": self.l[j], "confirm_close": self.c[j],
            "confirm_volume": r["volume"], "volume_sma20_prev": r["vol_sma_prev"], "volume_ratio": r["volume_ratio"],
            "volume_pctrank_prev": r["volume_pctrank_prev"], "volume_measure": vmeas,
            "confirm_close_back_inside_ref_range": bool(back_inside),
            "signal_time": pd.Timestamp(self.ts[j]) + BAR, "signal_price": self.c[j], **rec,
        }

    def scan_setup(self, setup, variant: dict, require_sweep: bool = True):
        """Returns (signal | None, skip_reason | None, events)."""
        if not setup.ref_exists or setup.exec_start not in self.h4.index:
            return None, "reference_4h_missing", []
        ref = self.h4.loc[setup.ref_start]
        if not (ref.complete and ref.contiguous):
            return None, "reference_4h_incomplete", []
        sigs, events = [], []
        for d in ("long", "short"):
            sig, ev = self.scan_direction(setup, d, variant, require_sweep)
            events.append(ev)
            if sig is not None:
                sigs.append(sig)
        if not sigs:
            return None, "no_signal", events
        sigs.sort(key=lambda z: z["conf_i"])
        if len(sigs) == 2:  # both extremes swept, each with its own valid confirmation: earliest wins
            sigs[0]["other_direction_also_signalled"] = True
        return sigs[0], None, events


def detect_all(df, h4, cfg, variant: dict, require_sweep: bool = True, keep_events: bool = False):
    setups = enumerate_setups(h4, cfg)
    det = Detector(df, h4, cfg)
    sigs, skips, evs = [], [], []
    for s in setups.itertuples(index=False):
        sig, skip, ev = det.scan_setup(s, variant, require_sweep)
        if sig is not None:
            sigs.append(sig)
        else:
            skips.append({"setup_id": s.setup_id, "kz": s.kz, "reason": skip})
        if keep_events:
            for e in ev:
                evs.append({"setup_id": s.setup_id, "kz": s.kz,
                            "sweep_bar_time": df["ts"].iloc[e["i"]] if "i" in e else pd.NaT,
                            "direction": e["direction"], "event": e["event"], "reasons": ";".join(e["reasons"])})
    sig_df = pd.DataFrame(sigs) if sigs else pd.DataFrame(columns=["setup_id", "kz", "direction", "conf_i",
                                                                   "signal_time"])
    if len(sig_df):
        sig_df = sig_df.sort_values("conf_i").reset_index(drop=True)
    return sig_df, pd.DataFrame(skips), pd.DataFrame(evs), setups
