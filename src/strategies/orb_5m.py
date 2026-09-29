"""ORB con velas de 5 minutos en MNQ, con su propio backtest (una operación al día como máximo).

Todos los parámetros vienen de config/orb_5m.yaml (clase ORB5Config).

Supuestos de ejecución (conservadores):
  - Entrada en la APERTURA de la vela siguiente a la señal, con deslizamiento.
  - Si en una misma vela se tocan el stop y el objetivo, se asume que saltó el stop.
  - Si la vela abre ya más allá del stop (hueco), se ejecuta en la apertura, con deslizamiento.
  - El objetivo es una orden límite: se ejecuta exactamente al precio del objetivo.
  - Para el drawdown de Apex, dentro de cada vela se asume que primero llega el precio FAVORABLE
    (sube el máximo de la cuenta) y después el DESFAVORABLE. Es el orden que más perjudica con
    un trailing drawdown.
"""
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent


# --------------------------------------------------------------------------- configuración
@dataclass(frozen=True)
class ORB5Config:
    point_value: float = 2.0
    tick: float = 0.25
    bar_minutes: int = 5
    session_open: str = "09:30"
    last_entry: str = "11:30"
    time_exit: str = "15:45"
    or_minutes: int = 15
    atr_days: int = 14
    range_filter: bool = True       # False = sin filtro de ancho del rango
    max_range_atr: float = 0.25
    min_range_atr: float = 0.05
    stop_mode: str = "range"        # "range" = lado opuesto del rango; "atr" = % fijo del ATR
    stop_atr_pct: float = 0.10
    target_r: float | None = 2.0
    news_filter: bool = False
    news_events: tuple = ("FOMC", "CPI", "NFP")
    news_file: str = "config/eventos_macro.csv"
    risk_usd: float = 150.0
    max_contracts: int = 10
    commission_side: float = 1.0
    slip_entry: int = 1
    slip_stop: int = 1
    slip_time_exit: int = 0
    slip_target: int = 0

    @classmethod
    def from_yaml(cls, path: str | Path = ROOT / "config" / "orb_5m.yaml") -> "ORB5Config":
        path = ROOT / path if not Path(path).is_absolute() else path
        with open(path, encoding="utf-8") as f:
            c = yaml.safe_load(f)
        return cls(
            point_value=c["instrumento"]["valor_punto_usd"],
            tick=c["instrumento"]["tick"],
            bar_minutes=c["velas_minutos"],
            session_open=c["horario_et"]["apertura"],
            last_entry=c["horario_et"]["ultima_entrada"],
            time_exit=c["horario_et"]["salida_tiempo"],
            or_minutes=c["rango_apertura_minutos"],
            atr_days=c["filtro_rango_atr"]["atr_dias"],
            range_filter=c["filtro_rango_atr"].get("activo", True),
            max_range_atr=c["filtro_rango_atr"]["max_pct"],
            min_range_atr=c["filtro_rango_atr"]["min_pct"],
            stop_mode=c.get("stop", {}).get("tipo", "range"),
            stop_atr_pct=c.get("stop", {}).get("pct_atr", 0.10),
            target_r=c["take_profit_r"],
            news_filter=c["noticias"]["filtrar"],
            news_events=tuple(c["noticias"]["eventos"]),
            news_file=c["noticias"]["archivo"],
            risk_usd=c["riesgo"]["riesgo_por_operacion_usd"],
            max_contracts=c["riesgo"]["contratos_max"],
            commission_side=c["costes"]["comision_por_contrato_y_lado_usd"],
            slip_entry=c["costes"]["slippage_ticks_entrada"],
            slip_stop=c["costes"]["slippage_ticks_stop"],
            slip_time_exit=c["costes"]["slippage_ticks_salida_tiempo"],
            slip_target=c["costes"]["slippage_ticks_take_profit"],
        )

    def variant(self, **changes) -> "ORB5Config":
        return replace(self, **changes)

    @property
    def label(self) -> str:
        tgt = "tiempo" if self.target_r is None else f"{self.target_r:g}R"
        stop = "" if self.stop_mode == "range" else f"_stop{self.stop_atr_pct:g}ATR"
        return f"OR{self.or_minutes}_{tgt}{stop}_{self.risk_usd:g}$" + ("_sinNoticias" if self.news_filter else "")


# ------------------------------------------------------------------------------ datos
def to_bars(minutes_df: pd.DataFrame, bar_minutes: int, start: str = "09:30", end: str = "16:00") -> pd.DataFrame:
    """Agrupa velas de 1 minuto en velas de `bar_minutes` minutos de la sesión regular.
    La marca de tiempo es el INICIO de la vela (9:30 = de 9:30:00 a 9:34:59)."""
    rth = minutes_df.between_time(start, end, inclusive="left")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
           "instrument_id": "last"}
    out = rth.resample(f"{bar_minutes}min", label="left", closed="left").agg(agg)
    return out.dropna(subset=["open"])


def daily_atr(minutes_df: pd.DataFrame, days: int, start: str = "09:30", end: str = "16:00") -> pd.Series:
    """ATR diario (media simple del rango verdadero) de la sesión regular, conocido ANTES de cada día.

    Rango verdadero = max(máximo - mínimo, |máximo - cierre anterior|, |mínimo - cierre anterior|).
    El día del cambio de contrato (roll) el cierre anterior es de otro vencimiento; ese día se usa
    solo máximo - mínimo para no meter un salto de precio artificial.
    """
    rth = minutes_df.between_time(start, end, inclusive="left")
    g = rth.groupby(rth.index.date)
    d = pd.DataFrame({"high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                      "first_id": g.instrument_id.first(), "last_id": g.instrument_id.last()})
    prev_close = d.close.shift(1)
    same_contract = d.first_id == d.last_id.shift(1)
    tr_full = pd.concat([d.high - d.low, (d.high - prev_close).abs(), (d.low - prev_close).abs()], axis=1).max(axis=1)
    tr = tr_full.where(same_contract, d.high - d.low)
    return tr.rolling(days).mean().shift(1).rename("atr")


def load_news_dates(cfg: ORB5Config) -> set:
    ev = pd.read_csv(ROOT / cfg.news_file, comment="#")
    ev = ev[ev.evento.isin(cfg.news_events)]
    return set(pd.to_datetime(ev.fecha).dt.date)


# -------------------------------------------------------------------------- backtest
@dataclass
class DayResult:
    date: object
    status: str                 # "operada", o el motivo de no operar
    trade: dict | None = None
    path: list = field(default_factory=list)   # recorrido del P&L de la operación (ver _simulate)


def backtest(bars: pd.DataFrame, atr: pd.Series, cfg: ORB5Config, news: set | None = None):
    """Devuelve (trades, dias, recorridos). `recorridos[i]` es la lista de P&L en dólares de la
    operación i, punto a punto, empezando tras pagar la comisión de entrada."""
    news = news or set()
    trades, days, paths = [], [], []
    for date, day in bars.groupby(bars.index.date):
        res = _run_day(date, day, atr.get(date), cfg, news)
        days.append({"date": pd.Timestamp(date), "status": res.status})
        if res.trade:
            trades.append(res.trade)
            paths.append(res.path)
    return pd.DataFrame(trades), pd.DataFrame(days), paths


def _run_day(date, day: pd.DataFrame, atr, cfg: ORB5Config, news: set) -> DayResult:
    if atr is None or np.isnan(atr):
        return DayResult(date, "sin_atr")
    if cfg.news_filter and date in news:
        return DayResult(date, "dia_de_noticias")

    tz = day.index.tz
    t_open = pd.Timestamp(f"{date} {cfg.session_open}", tz=tz)
    t_or_end = t_open + pd.Timedelta(minutes=cfg.or_minutes)
    t_last_entry = pd.Timestamp(f"{date} {cfg.last_entry}", tz=tz)
    t_exit = pd.Timestamp(f"{date} {cfg.time_exit}", tz=tz)

    opening = day[(day.index >= t_open) & (day.index < t_or_end)]
    if len(opening) < cfg.or_minutes // cfg.bar_minutes:
        return DayResult(date, "rango_incompleto")
    hi, lo = opening.high.max(), opening.low.min()
    width = hi - lo
    if cfg.range_filter and width > cfg.max_range_atr * atr:
        return DayResult(date, "rango_demasiado_ancho")
    if cfg.range_filter and width < cfg.min_range_atr * atr:
        return DayResult(date, "rango_demasiado_estrecho")

    after = day[day.index >= t_or_end]
    breaks = np.flatnonzero((after.close.to_numpy() > hi) | (after.close.to_numpy() < lo))
    if len(breaks) == 0:
        return DayResult(date, "sin_ruptura")
    i = breaks[0]
    if i + 1 >= len(after):
        return DayResult(date, "sin_vela_de_entrada")
    entry_bar = after.iloc[i + 1]
    entry_time = after.index[i + 1]
    if entry_time > t_last_entry or entry_time >= t_exit:
        return DayResult(date, "ruptura_despues_de_hora_limite")

    d = 1 if after.close.iloc[i] > hi else -1
    entry = entry_bar.open + d * cfg.slip_entry * cfg.tick
    if cfg.stop_mode == "range":
        stop = lo if d == 1 else hi
    else:  # stop fijo a un % del ATR diario, medido desde el precio de entrada
        stop = entry - d * cfg.stop_atr_pct * atr
    dist = (entry - stop) * d
    if dist <= 0:
        return DayResult(date, "entrada_mas_alla_del_stop")
    qty = int(np.floor(cfg.risk_usd / (dist * cfg.point_value) + 1e-9))
    if qty < 1:
        return DayResult(date, "riesgo_de_1_contrato_excede_limite")
    qty = min(qty, cfg.max_contracts)
    target = None if cfg.target_r is None else entry + d * cfg.target_r * dist

    trade_bars = after.iloc[i + 1:]
    exit_price, exit_time, reason, path = _simulate(trade_bars, d, entry, stop, target, qty, t_exit, cfg)
    comm = 2 * cfg.commission_side * qty
    gross = (exit_price - entry) * d * cfg.point_value * qty
    trade = {
        "date": pd.Timestamp(date), "direction": d, "qty": qty, "entry_time": entry_time,
        "entry": entry, "stop": stop, "target": target, "exit_time": exit_time, "exit": exit_price,
        "exit_reason": reason, "range_width": width, "atr": atr,
        "risk_usd": dist * cfg.point_value * qty, "gross": gross, "commission": comm,
        "pnl": gross - comm,
    }
    return DayResult(date, "operada", trade, path)


def _simulate(bars, d, entry, stop, target, qty, t_exit, cfg):
    """Recorre las velas de la operación. Devuelve precio, hora y motivo de salida, y el recorrido
    del P&L (en dólares, neto de la comisión de entrada) para el simulador de Apex."""
    pv, c_side = cfg.point_value * qty, cfg.commission_side * qty
    pnl_at = lambda px: (px - entry) * d * pv - c_side  # noqa: E731  (P&L abierto, ya pagada la entrada)
    path = [-c_side]
    for ts, b in zip(bars.index, bars.itertuples()):
        if ts >= t_exit:
            px = b.open - d * cfg.slip_time_exit * cfg.tick
            path.append(pnl_at(px) - c_side)
            return px, ts, "tiempo", path
        best, worst = (b.high, b.low) if d == 1 else (b.low, b.high)
        hit_stop = worst <= stop if d == 1 else worst >= stop
        hit_target = target is not None and (best >= target if d == 1 else best <= target)
        if hit_stop:
            base = min(stop, b.open) if d == 1 else max(stop, b.open)
            px = base - d * cfg.slip_stop * cfg.tick
            # Orden conservador: primero lo favorable de la vela (sin pasar del objetivo), luego el stop.
            if target is None:
                fav = best
            else:
                fav = min(best, target) if d == 1 else max(best, target)
            path.append(pnl_at(fav))
            path.append(pnl_at(px) - c_side)
            return px, ts, "stop", path
        if hit_target:
            px = target - d * cfg.slip_target * cfg.tick
            path.append(pnl_at(worst))  # la vela pudo bajar antes de subir al objetivo
            path.append(pnl_at(px) - c_side)
            return px, ts, "objetivo", path
        path.append(pnl_at(best))
        path.append(pnl_at(worst))
    # Sin vela de las 15:45 (día corto): cerrar al último cierre disponible.
    last = bars.iloc[-1]
    px = last.close - d * cfg.slip_time_exit * cfg.tick
    path.append(pnl_at(px) - c_side)
    return px, bars.index[-1], "tiempo", path
