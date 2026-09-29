"""Setup ICT de oro en horario de Italia, traducido a reglas mecánicas (config/gold_ict.yaml).

Reglas (todas fijadas antes de ver resultados):
  Sesgo:     largos si el cierre del día anterior > EMA20 diaria Y el último cierre de 4H > EMA20 de 4H;
             cortos si ambos están por debajo; si no coinciden, no se opera.
  Liquidez:  máximo/mínimo de Asia (06:00-08:50 Roma) y máximo/mínimo de la sesión anterior.
  Zona:      cortos solo si el barrido ocurre en premium (> 50 % del rango del día anterior);
             largos solo en discount (< 50 %).
  Barrido:   dentro de una ventana (8:50-9:10 o 10:03-10:30 Roma) el precio supera un nivel de liquidez
             del lado contrario al sesgo (para cortos: máximo de Asia o del día anterior).
  SMT:       (opcional) la plata NO supera su nivel equivalente en la ventana mientras el oro sí.
  Entrada:   IFVG: el FVG más reciente formado en los 60 min previos al extremo del barrido; cuando una vela
             cierra al otro lado del FVG, se entra en la apertura de la siguiente. Si no hubo FVG,
             breaker: cierre al otro lado de la vela que hizo el extremo del barrido.
  Stop:      extremo del barrido +/- margen (1,5 $). Objetivo: 2R o el extremo opuesto de Asia si queda antes.
  Cierre:    11:00 Roma. Máximo 2 operaciones al día; si la primera toca el stop, se acabó el día.

Las sesiones de Globex empiezan a las 18:00 ET: la "sesión" de un día va de las 18:00 ET del día
anterior a las 17:00 ET. La mañana de Italia (6:00-11:00) cae siempre dentro de la sesión del mismo día.
"""
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.strategies.orb_5m import DayResult, _simulate

ROOT = Path(__file__).resolve().parent.parent.parent
ET = "America/New_York"


@dataclass(frozen=True)
class GoldICTConfig:
    symbol: str = "MGC"
    point_value: float = 10.0
    tick: float = 0.10
    tz: str = "Europe/Rome"
    asia_start: str = "06:00"
    asia_end: str = "08:50"
    windows: tuple = (("08:50", "09:10"), ("10:03", "10:30"))
    close: str = "11:00"
    ema_daily: int = 20
    ema_4h: int = 20
    bar_minutes: int = 1
    fvg_lookback_min: int = 60
    smt: bool = False
    stop_margin: float = 1.5
    target_r: float = 2.0
    max_trades_day: int = 2
    risk_usd: float = 250.0
    max_contracts: int = 20
    fixed_contracts: int | None = None
    commission_side: float = 1.0
    slip_entry: int = 1
    slip_stop: int = 1
    slip_time_exit: int = 1
    slip_target: int = 0

    @classmethod
    def from_yaml(cls, path="config/gold_ict.yaml") -> "GoldICTConfig":
        c = yaml.safe_load(open(ROOT / path, encoding="utf-8"))
        h = c["horario"]
        return cls(
            symbol=c["instrumento"]["simbolo"], point_value=c["instrumento"]["valor_punto_usd"],
            tick=c["instrumento"]["tick"], tz=c["zona_horaria"], asia_start=h["asia_inicio"],
            asia_end=h["asia_fin"], windows=tuple(tuple(w) for w in h["ventanas"]), close=h["cierre"],
            ema_daily=c["sesgo"]["ema_diaria"], ema_4h=c["sesgo"]["ema_4h"],
            bar_minutes=c["entrada"]["velas_minutos"], fvg_lookback_min=c["entrada"]["fvg_ventana_minutos"],
            smt=c["entrada"]["smt"], stop_margin=c["gestion"]["margen_stop_usd"],
            target_r=c["gestion"]["objetivo_r"], max_trades_day=c["gestion"]["max_operaciones_dia"],
            risk_usd=c["riesgo"]["riesgo_por_operacion_usd"], max_contracts=c["riesgo"]["contratos_max"],
            fixed_contracts=c["riesgo"]["contratos_fijos"],
            commission_side=c["costes"]["comision_por_contrato_y_lado_usd"],
            slip_entry=c["costes"]["slippage_ticks_entrada"], slip_stop=c["costes"]["slippage_ticks_stop"],
            slip_time_exit=c["costes"]["slippage_ticks_salida_tiempo"],
            slip_target=c["costes"]["slippage_ticks_take_profit"],
        )

    def variant(self, **changes) -> "GoldICTConfig":
        return replace(self, **changes)

    @property
    def label(self) -> str:
        size = f"{self.fixed_contracts}contrato_fijo" if self.fixed_contracts else f"{self.risk_usd:g}$"
        return f"ICT_{self.symbol}_{self.bar_minutes}m_{'conSMT' if self.smt else 'sinSMT'}_{size}"


# ----------------------------------------------------------------------------- contexto
def session_key(idx: pd.DatetimeIndex) -> np.ndarray:
    """Fecha de sesión de Globex (las 18:00 ET abren la sesión del día siguiente)."""
    return (idx.tz_convert(ET) + pd.Timedelta(hours=6)).date


def context(minutes: pd.DataFrame, cfg: GoldICTConfig) -> pd.DataFrame:
    """Por sesión: máximo/mínimo/50 % de la sesión anterior y sesgo diario + 4H a la hora de decidir."""
    m = minutes[["open", "high", "low", "close"]]
    g = m.groupby(session_key(m.index))
    daily = pd.DataFrame({"high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
    ema_d = daily.close.ewm(span=cfg.ema_daily, adjust=False).mean()
    ctx = pd.DataFrame({
        "prev_high": daily.high.shift(), "prev_low": daily.low.shift(),
        "bias_d": np.sign(daily.close - ema_d).shift(),
    }, index=daily.index)
    ctx["mid"] = (ctx.prev_high + ctx.prev_low) / 2

    # 4H alineadas con la apertura de Globex (18:00 ET): se desplaza +6 h, se agrupa y se deshace.
    shifted = m.copy()
    shifted.index = m.index.tz_convert(ET) + pd.Timedelta(hours=6)
    h4 = shifted.close.resample("4h").last().dropna()
    ema4 = h4.ewm(span=cfg.ema_4h, adjust=False).mean()
    h4_end = (h4.index + pd.Timedelta(hours=4) - pd.Timedelta(hours=6))
    h4_df = pd.DataFrame({"end": h4_end.tz_convert(cfg.tz).as_unit("ns"), "bias_4h": np.sign(h4 - ema4).to_numpy()})
    # Decisión a las 8:45 de Roma: último 4H cerrado antes de esa hora.
    decide = pd.DataFrame({"session": ctx.index,
                           "t": pd.DatetimeIndex([pd.Timestamp(f"{d} 08:45", tz=cfg.tz) for d in ctx.index]).as_unit("ns")})
    merged = pd.merge_asof(decide.sort_values("t"), h4_df.sort_values("end"), left_on="t", right_on="end")
    ctx["bias_4h"] = merged.set_index("session").bias_4h
    ctx["bias"] = np.where(ctx.bias_d == ctx.bias_4h, ctx.bias_d, 0)
    return ctx


def morning_bars(minutes: pd.DataFrame, cfg: GoldICTConfig) -> pd.DataFrame:
    """Velas de la mañana de Italia (06:00-11:00) en la zona horaria del setup, de 1 o 5 minutos."""
    rome = minutes.tz_convert(cfg.tz).between_time("06:00", "11:00", inclusive="left")
    if cfg.bar_minutes == 1:
        return rome[["open", "high", "low", "close"]]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    return rome.resample(f"{cfg.bar_minutes}min", label="left", closed="left").agg(agg).dropna()


# ----------------------------------------------------------------------------- backtest
def backtest(minutes: pd.DataFrame, atr, cfg: GoldICTConfig, silver: pd.DataFrame | None = None):
    """(trades, días, recorridos), igual que el resto de estudios. `atr` no se usa."""
    if cfg.smt and silver is None:
        raise ValueError("La variante con SMT necesita datos de plata (SI).")
    ctx = context(minutes, cfg)
    bars = morning_bars(minutes, cfg)
    s_ctx = context(silver, cfg) if cfg.smt else None
    s_bars = morning_bars(silver, cfg.variant(bar_minutes=1)) if cfg.smt else None
    s_groups = dict(tuple(s_bars.groupby(session_key(s_bars.index)))) if cfg.smt else {}
    trades, days, paths = [], [], []
    for date, day in bars.groupby(session_key(bars.index)):
        if date not in ctx.index:
            continue
        silver_day = (s_groups.get(date), s_ctx.loc[date] if date in s_ctx.index else None) if cfg.smt else None
        status, found = run_day(date, day, ctx.loc[date], cfg, silver_day)
        days.append({"date": pd.Timestamp(date), "status": status})
        for trade, path in found:
            trades.append(trade)
            paths.append(path)
    return pd.DataFrame(trades), pd.DataFrame(days), paths


def run_day(date, day: pd.DataFrame, ctx_row, cfg: GoldICTConfig, silver_day=None):
    """Devuelve (estado, [(trade, recorrido), ...])."""
    tz = day.index.tz
    ts = lambda hhmm: pd.Timestamp(f"{date} {hhmm}", tz=tz)  # noqa: E731
    d = int(ctx_row.bias) if not np.isnan(ctx_row.bias) else 0
    if d == 0 or np.isnan(ctx_row.prev_high):
        return "sesgo_contradictorio", []
    idx = day.index
    asia = day[(idx >= ts(cfg.asia_start)) & (idx < ts(cfg.asia_end))]
    if len(asia) < 60 // cfg.bar_minutes:
        return "asia_incompleta", []
    ah, al = asia.high.max(), asia.low.min()
    levels = {"asia": ah if d == -1 else al, "dia_anterior": ctx_row.prev_high if d == -1 else ctx_row.prev_low}
    s_levels = None
    if cfg.smt:
        s_day, s_ctx = silver_day
        if s_day is None or s_ctx is None:
            return "sin_datos_plata", []
        s_asia = s_day[(s_day.index >= ts(cfg.asia_start)) & (s_day.index < ts(cfg.asia_end))]
        if s_asia.empty:
            return "sin_datos_plata", []
        s_levels = {"asia": s_asia.high.max() if d == -1 else s_asia.low.min(),
                    "dia_anterior": s_ctx.prev_high if d == -1 else s_ctx.prev_low}

    found, status, since = [], "sin_setup", None
    t_close = ts(cfg.close)
    for w0, w1 in cfg.windows:
        start = ts(w0) if since is None else max(ts(w0), since)
        while len(found) < cfg.max_trades_day:
            setup = _find_setup(day, d, levels, ctx_row.mid, start, ts(w1), cfg, s_levels, silver_day, ts(w0))
            if setup is None:
                break
            e, ext, kind = setup
            entry = day.open.iloc[e] + d * cfg.slip_entry * cfg.tick
            stop = ext - d * cfg.stop_margin
            dist = (entry - stop) * d
            if dist <= 0:
                start = idx[e]
                continue
            target = entry + d * cfg.target_r * dist
            opp = al if d == -1 else ah
            if (opp - entry) * d > 0 and abs(opp - entry) < abs(target - entry):
                target = opp
            if cfg.fixed_contracts:
                qty = cfg.fixed_contracts
            else:
                qty = min(int(np.floor(cfg.risk_usd / (dist * cfg.point_value) + 1e-9)), cfg.max_contracts)
                if qty < 1:
                    status = "riesgo_de_1_contrato_excede_limite"
                    start = idx[e]
                    continue
            px, t_out, reason, path = _simulate(day.iloc[e:], d, entry, stop, target, qty, t_close, cfg)
            comm = 2 * cfg.commission_side * qty
            gross = (px - entry) * d * cfg.point_value * qty
            found.append(({"date": pd.Timestamp(date), "direction": d, "qty": qty, "entry_time": idx[e],
                           "entry": entry, "stop": stop, "target": target, "exit_time": t_out, "exit": px,
                           "exit_reason": reason, "tipo_entrada": kind, "risk_usd": dist * cfg.point_value * qty,
                           "gross": gross, "commission": comm, "pnl": gross - comm}, path))
            status = "operada"
            if reason == "stop" or t_out >= t_close:
                return status, found               # stop = se acabó el día
            start = since = t_out
    return status, found


def _find_setup(day, d, levels, mid, start, end, cfg, s_levels, silver_day, w_start):
    """Busca barrido + disparador dentro de [start, end). Devuelve (índice de entrada, extremo, tipo) o None."""
    idx = day.index
    H, L, C = day.high.to_numpy(), day.low.to_numpy(), day.close.to_numpy()
    lookback = cfg.fvg_lookback_min // cfg.bar_minutes
    win = np.flatnonzero((idx >= start) & (idx < end))
    ext = ext_i = swept = None
    for j in win:
        if ext is None:
            hit = [k for k, lv in levels.items() if (H[j] > lv if d == -1 else L[j] < lv)]
            in_zone = H[j] > mid if d == -1 else L[j] < mid
            if hit and in_zone:
                ext, ext_i, swept = (H[j] if d == -1 else L[j]), j, hit
            continue
        if (d == -1 and H[j] > ext) or (d == 1 and L[j] < ext):
            ext, ext_i = (H[j] if d == -1 else L[j]), j
            continue
        fvg = _last_fvg(H, L, max(2, ext_i - lookback), ext_i, d)
        if fvg is not None:
            trig, kind = (C[j] < fvg if d == -1 else C[j] > fvg), "IFVG"
        else:
            trig, kind = (C[j] < L[ext_i] if d == -1 else C[j] > H[ext_i]), "breaker"
        if not trig:
            continue
        if cfg.smt and not _smt_ok(silver_day[0], s_levels, swept, d, w_start, idx[j]):
            ext = ext_i = swept = None            # barrido sin divergencia: se descarta y se sigue buscando
            continue
        if j + 1 < len(day):
            return j + 1, ext, kind
        return None
    return None


def _last_fvg(H, L, k0, k1, d):
    """Límite del FVG más reciente con tercera vela en [k0, k1] a favor del barrido.
    Barrido alcista (cortos): FVG alcista L[k] > H[k-2]; se invierte si se cierra por debajo de H[k-2].
    Barrido bajista (largos): FVG bajista H[k] < L[k-2]; se invierte si se cierra por encima de L[k-2]."""
    for k in range(k1, k0 - 1, -1):
        if d == -1 and L[k] > H[k - 2]:
            return H[k - 2]
        if d == 1 and H[k] < L[k - 2]:
            return L[k - 2]
    return None


def _smt_ok(s_day, s_levels, swept, d, t0, t1) -> bool:
    """Divergencia: la plata NO supera ninguno de los niveles equivalentes a los que barrió el oro."""
    part = s_day[(s_day.index >= t0) & (s_day.index <= t1)]
    if part.empty:
        return False
    for k in swept:
        if (d == -1 and part.high.max() > s_levels[k]) or (d == 1 and part.low.min() < s_levels[k]):
            return False
    return True
