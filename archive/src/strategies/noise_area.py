"""Momentum intradía con "zona de ruido" (Zarattini, Aziz y Barbon, 2024, "Beat the Market").

Reglas del estudio (config/noise_area.yaml):
  - sigma(t): media, en los 14 días anteriores, de |cierre(t) / apertura del día - 1| en ese mismo minuto.
  - Banda superior(t) = max(apertura, cierre anterior) x (1 + mult x sigma(t))
    Banda inferior(t) = min(apertura, cierre anterior) x (1 - mult x sigma(t))
    (anclar en el cierre anterior tiene en cuenta el hueco de la noche).
  - Solo se decide a las HH:00 y HH:30, de 10:00 a 15:30, con el cierre del minuto anterior:
      sin posición: por encima de la banda superior -> largo; por debajo de la inferior -> corto.
      largo: sale si el precio < max(banda superior, VWAP); si además está bajo la banda inferior, gira a corto.
      corto: simétrico con min(banda inferior, VWAP).
  - Todo se cierra al final de la sesión (cierre de la vela de 15:59).
  - Tamaño: capital x min(apalancamiento máx., vol objetivo / vol diaria de 14 días) / valor de 1 contrato.

Ejecución en este backtest: la orden se ejecuta en la APERTURA del minuto del chequeo, con deslizamiento
(el estudio usa el precio del propio minuto). Con `stop_duro` hay además una orden stop real en el nivel del
trailing, que puede saltar entre chequeos.
"""
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class NoiseConfig:
    symbol: str = "MNQ"
    point_value: float = 2.0
    tick: float = 0.25
    first_check: int = 30          # minutos desde las 9:30 (30 = 10:00)
    last_check: int = 360          # 360 = 15:30
    check_every: int = 30
    noise_days: int = 14
    mult: float = 1.0
    capital: float = 50_000
    vol_target: float = 0.02
    max_leverage: float = 4.0
    vol_days: int = 14
    max_contracts: int = 10
    fixed_contracts: int | None = None
    hard_stop: bool = False
    commission_side: float = 1.0
    slip_entry: int = 1
    slip_stop: int = 1
    slip_time_exit: int = 1
    slip_target: int = 0

    @classmethod
    def from_yaml(cls, path="config/noise_area.yaml") -> "NoiseConfig":
        c = yaml.safe_load(open(ROOT / path, encoding="utf-8"))
        h = c["horario_et"]
        mins = lambda hhmm: (pd.Timestamp(hhmm) - pd.Timestamp(h["apertura"])).seconds // 60  # noqa: E731
        t = c["tamano"]
        return cls(
            symbol=c["instrumento"]["simbolo"], point_value=c["instrumento"]["valor_punto_usd"],
            tick=c["instrumento"]["tick"], first_check=mins(h["primer_chequeo"]),
            last_check=mins(h["ultimo_chequeo"]), check_every=h["intervalo_minutos"],
            noise_days=c["zona_ruido"]["dias"], mult=c["zona_ruido"]["multiplicador"],
            capital=t["capital_usd"], vol_target=t["vol_objetivo_diaria"], max_leverage=t["apalancamiento_max"],
            vol_days=t["vol_dias"], max_contracts=t["contratos_max"], fixed_contracts=t["contratos_fijos"],
            hard_stop=c["stop_duro"], commission_side=c["costes"]["comision_por_contrato_y_lado_usd"],
            slip_entry=c["costes"]["slippage_ticks_entrada"], slip_stop=c["costes"]["slippage_ticks_stop"],
            slip_time_exit=c["costes"]["slippage_ticks_salida_tiempo"],
            slip_target=c["costes"]["slippage_ticks_take_profit"],
        )

    def variant(self, **changes) -> "NoiseConfig":
        return replace(self, **changes)

    @property
    def label(self) -> str:
        size = f"{self.fixed_contracts}contrato_fijo" if self.fixed_contracts else "volObjetivo"
        return f"ZonaRuido_{self.symbol}_{'stopDuro' if self.hard_stop else 'comoEstudio'}_{size}"


# ------------------------------------------------------------------------------ preparación
def prepare(minutes: pd.DataFrame, cfg: NoiseConfig):
    """Velas de la sesión regular con el minuto del día, y por día: apertura, cierre anterior,
    sigma por minuto (solo días previos) y volatilidad diaria (solo días previos)."""
    rth = minutes.between_time("09:30", "16:00", inclusive="left").copy()
    rth["date"] = rth.index.date
    rth["minute"] = (rth.index.hour - 9) * 60 + rth.index.minute - 30
    g = rth.groupby("date")
    daily = pd.DataFrame({"open": g.open.first(), "close": g.close.last(),
                          "first_id": g.instrument_id.first(), "last_id": g.instrument_id.last()})
    same = daily.first_id == daily.last_id.shift()
    daily["prev_close"] = daily.close.shift().where(same, daily.open)   # en día de roll, sin hueco
    ret = (daily.close / daily.close.shift() - 1).where(same)
    daily["vol"] = ret.rolling(cfg.vol_days, min_periods=10).std().shift()
    rth["move"] = (rth.close / rth.date.map(daily.open) - 1).abs()
    grid = rth.pivot_table(index="date", columns="minute", values="move")
    sigma = grid.rolling(cfg.noise_days, min_periods=10).mean().shift()
    return rth, daily, sigma


def contracts(cfg: NoiseConfig, open_price: float, vol: float) -> int:
    if cfg.fixed_contracts:
        return cfg.fixed_contracts
    if not vol or np.isnan(vol):
        return 0
    notional = cfg.capital * min(cfg.max_leverage, cfg.vol_target / vol)
    return min(int(notional // (open_price * cfg.point_value)), cfg.max_contracts)


# -------------------------------------------------------------------------------- backtest
def backtest(minutes: pd.DataFrame, atr, cfg: NoiseConfig):
    """(trades, días, recorridos), igual que el resto de estudios. `atr` no se usa."""
    rth, daily, sigma = prepare(minutes, cfg)
    trades, days, paths = [], [], []
    for date, day in rth.groupby("date"):
        d = daily.loc[date]
        if date not in sigma.index or sigma.loc[date].isna().all() or np.isnan(d.vol):
            days.append({"date": pd.Timestamp(date), "status": "sin_historia"})
            continue
        qty = contracts(cfg, d.open, d.vol)
        if qty < 1:
            days.append({"date": pd.Timestamp(date), "status": "capital_insuficiente"})
            continue
        found = run_day(date, day, d.open, d.prev_close, sigma.loc[date], qty, d.vol, cfg)
        days.append({"date": pd.Timestamp(date), "status": "operada" if found else "sin_senal"})
        for t, p in found:
            trades.append(t)
            paths.append(p)
    return pd.DataFrame(trades), pd.DataFrame(days), paths


def run_day(date, day: pd.DataFrame, day_open, prev_close, sigma_row: pd.Series, qty: int, vol: float,
            cfg: NoiseConfig):
    """Simula un día. Devuelve [(trade, recorrido), ...]."""
    O, H, L, C = (day[c].to_numpy() for c in ("open", "high", "low", "close"))
    M = day.minute.to_numpy()
    typical = (day.high + day.low + day.close) / 3
    vwap = ((typical * day.volume).cumsum() / day.volume.cumsum().replace(0, np.nan)).to_numpy()
    sig = sigma_row.reindex(M).to_numpy()
    upper = max(day_open, prev_close) * (1 + cfg.mult * sig)
    lower = min(day_open, prev_close) * (1 - cfg.mult * sig)
    pv, c_side, tick = cfg.point_value * qty, cfg.commission_side * qty, cfg.tick
    one_r = qty * cfg.point_value * day_open * vol           # 1R = una desviación típica diaria de la posición
    checks = set(range(cfg.first_check, cfg.last_check + 1, cfg.check_every))

    out, pos = [], None                                       # pos = dict con la operación abierta

    def open_pos(i, d, stop):
        px = O[i] + d * cfg.slip_entry * tick
        return {"d": d, "entry": px, "i": i, "stop": stop, "path": [-c_side]}

    def close_pos(p, i, px, reason):
        p["path"].append((px - p["entry"]) * p["d"] * pv - 2 * c_side)
        gross = (px - p["entry"]) * p["d"] * pv
        out.append(({"date": pd.Timestamp(date), "direction": p["d"], "qty": qty, "entry_time": day.index[p["i"]],
                     "entry": p["entry"], "exit_time": day.index[i], "exit": px, "exit_reason": reason,
                     "risk_usd": one_r, "gross": gross, "commission": 2 * c_side, "pnl": gross - 2 * c_side},
                    p["path"]))

    for i in range(1, len(day)):
        if M[i] in checks and not np.isnan(sig[i - 1]):
            p_ = C[i - 1]
            up, lo, vw = upper[i - 1], lower[i - 1], vwap[i - 1]
            if pos is not None:
                trail = max(up, vw) if pos["d"] == 1 else min(lo, vw)
                if (pos["d"] == 1 and p_ < trail) or (pos["d"] == -1 and p_ > trail):
                    close_pos(pos, i, O[i] - pos["d"] * cfg.slip_stop * tick, "trailing")
                    pos = None
                else:
                    pos["stop"] = trail
            if pos is None:
                if p_ > up:
                    pos = open_pos(i, 1, max(up, vw))
                elif p_ < lo:
                    pos = open_pos(i, -1, min(lo, vw))
        if pos is None:
            continue
        d = pos["d"]
        best, worst = (H[i], L[i]) if d == 1 else (L[i], H[i])
        pos["path"].append((best - pos["entry"]) * d * pv - c_side)
        if cfg.hard_stop and ((d == 1 and L[i] <= pos["stop"]) or (d == -1 and H[i] >= pos["stop"])):
            base = min(pos["stop"], O[i]) if d == 1 else max(pos["stop"], O[i])
            px = base - d * cfg.slip_stop * tick
            pos["path"].append((px - pos["entry"]) * d * pv - c_side)
            close_pos(pos, i, px, "stop_duro")
            pos = None
            continue
        pos["path"].append((worst - pos["entry"]) * d * pv - c_side)
    if pos is not None:
        close_pos(pos, len(day) - 1, C[-1] - pos["d"] * cfg.slip_time_exit * tick, "cierre")
    return out
