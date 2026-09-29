"""GOLD_MA_TREND_v1.0: cruce de medias simples en el oro (GC, diario). Reglas en edges/gold_ma_trend.md.

Señal confirmada al CIERRE de la vela D; ejecución en la APERTURA de la vela D+1. Sin stop ni objetivo.
Solo simula; nunca ejecuta órdenes.
"""
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.strategies.gold_swing_simple import ajustar_rolls

VERSION = "GOLD_MA_TREND_v1.0"
RAIZ = Path(__file__).resolve().parent.parent.parent
ONZAS = 100                                           # 1 contrato GC


@dataclass(frozen=True)
class Costes:
    """$ por contrato y lado."""
    comision: float = 2.50
    ticks: int = 1
    tick_usd: float = 10.0

    @property
    def lado(self) -> float:
        return self.comision + self.ticks * self.tick_usd


ESCENARIOS = {0: Costes(0.0, 0), 1: Costes(2.50, 1), 2: Costes(5.00, 3)}


@dataclass(frozen=True)
class Config:
    rapida: int = 50
    lenta: int = 200
    solo_largos: bool = False
    atr_n: int = 20
    costes: Costes = ESCENARIOS[1]

    def con(self, **c) -> "Config":
        return replace(self, **c)


HIPOTESIS = {"A": Config(50, 200, False), "B": Config(50, 200, True), "C": Config(20, 100, False)}


# ------------------------------------------------------------------------------------------- datos
def unir_domingos(df: pd.DataFrame) -> pd.DataFrame:
    """La vela del domingo (reapertura) se une a la del lunes siguiente; un domingo final sin lunes se elimina."""
    df = df.sort_index()
    filas, pendiente = [], None
    for t, r in df.iterrows():
        if t.dayofweek == 6:
            pendiente = r
            continue
        r = r.copy()
        if pendiente is not None:
            r["open"] = pendiente.open
            r["high"] = max(r.high, pendiente.high)
            r["low"] = min(r.low, pendiente.low)
            r["volume"] = r.volume + pendiente.volume
            pendiente = None
        filas.append((t, r))
    out = pd.DataFrame([r for _, r in filas], index=pd.DatetimeIndex([t for t, _ in filas], name="dia"))
    out["instrument_id"] = out.instrument_id.astype(int)
    return out


def cargar(raiz: str = "GC", hasta=None) -> pd.DataFrame:
    """Velas diarias unidas y ajustadas. Con `hasta`, se cortan ANTES de ajustar (el desarrollo no ve nada posterior)."""
    df = pd.read_parquet(RAIZ / "data" / "raw" / "daily" / f"{raiz}.parquet")
    df = df[~df.index.duplicated(keep="last")]
    if hasta is not None:
        h = pd.Timestamp(hasta)
        df = df[df.index < (h if h.tzinfo else h.tz_localize("UTC"))]
    return ajustar_rolls(unir_domingos(df))            # añade 'ajuste' (precio real = ajustado - ajuste) y attrs


# ------------------------------------------------------------------------------------------ reglas
def regimen(close: pd.Series, rapida: int, lenta: int) -> np.ndarray:
    """+1 si SMA rápida > lenta, -1 si <; si son iguales se mantiene el anterior; 0 antes de tener la lenta.
    Cada SMA en D usa las N últimas velas hasta D incluida (solo pasado)."""
    f = close.rolling(rapida).mean().to_numpy()
    s = close.rolling(lenta).mean().to_numpy()
    reg = np.zeros(len(close), int)
    for i in range(len(close)):
        if np.isnan(s[i]):
            continue
        reg[i] = 1 if f[i] > s[i] else (-1 if f[i] < s[i] else reg[i - 1])
    return reg


def objetivo(reg: np.ndarray, solo_largos: bool) -> np.ndarray:
    """Posición deseada al cierre de cada vela D (se ejecuta en la apertura de D+1). Plana hasta el primer cruce."""
    obj = np.zeros(len(reg), int)
    visto_cruce = False
    for i in range(1, len(reg)):
        if reg[i] != 0 and reg[i - 1] != 0 and reg[i] != reg[i - 1]:
            visto_cruce = True
        if visto_cruce:
            obj[i] = (1 if reg[i] == 1 else 0) if solo_largos else reg[i]
    return obj


def atr(d: pd.DataFrame, n: int) -> np.ndarray:
    pc = d.close.shift()
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().to_numpy()


# ----------------------------------------------------------------------------------------- simulación
def simular(d: pd.DataFrame, cfg: Config):
    """Devuelve (operaciones, diario). `diario`: posición y P&L en $ de 1 contrato por día, y rendimiento sobre el
    nocional real del día anterior. La última operación abierta se cierra (a efectos del informe) al último cierre."""
    O, C = d.open.to_numpy(), d.close.to_numpy()
    real_c = C - d.ajuste.to_numpy()
    ids = d.instrument_id.to_numpy()
    roll = np.r_[False, ids[1:] != ids[:-1]]
    a = atr(d, cfg.atr_n)
    obj = objetivo(regimen(d.close, cfg.rapida, cfg.lenta), cfg.solo_largos)
    n, lado = len(d), cfg.costes.lado
    pos_open = np.zeros(n, int)                        # posición mantenida DESPUÉS de la apertura de cada día
    pnl = np.zeros(n)
    coste = np.zeros(n)
    ops, abierta = [], None
    pos = 0
    for t in range(1, n):
        antes = pos
        nueva = obj[t - 1]                              # decisión al cierre de t-1 → ejecución en la apertura de t
        pnl[t] += antes * (O[t] - C[t - 1]) * ONZAS    # hueco desde el cierre anterior con la posición vieja
        if roll[t] and antes != 0 and nueva == antes:
            coste[t] += 2 * lado                        # rodar la posición abierta: cerrar viejo + abrir nuevo
            abierta["rolls"] += 1
        if nueva != antes:
            if antes != 0:
                coste[t] += lado
                abierta.update(salida_i=t, salida=O[t])
                ops.append(abierta)
                abierta = None
            if nueva != 0:
                coste[t] += lado
                abierta = {"d": nueva, "senal_i": t - 1, "entrada_i": t, "entrada": O[t], "rolls": 0,
                           "atr": a[t - 1]}
            pos = nueva
        pnl[t] += pos * (C[t] - O[t]) * ONZAS
        pos_open[t] = pos
    if abierta is not None:
        abierta.update(salida_i=n - 1, salida=C[-1], abierta_al_final=True)
        ops.append(abierta)
    idx = d.index
    diario = pd.DataFrame({"pos": pos_open, "pnl_bruto": pnl, "coste": coste, "pnl": pnl - coste}, index=idx)
    nocional = np.r_[np.nan, real_c[:-1]] * ONZAS
    diario["ret"] = diario.pnl / nocional
    diario["ret_bruto"] = diario.pnl_bruto / nocional
    filas = []
    for o in ops:
        i, j = o["entrada_i"], o["salida_i"]
        bruto = (o["salida"] - o["entrada"]) * o["d"] * ONZAS
        c = 2 * lado * (1 if o.get("abierta_al_final") is None else 0.5) + 2 * lado * o["rolls"]
        filas.append({"direccion": o["d"], "lado": "LONG" if o["d"] == 1 else "SHORT",
                      "dia_senal": idx[o["senal_i"]], "dia_entrada": idx[i], "dia_salida": idx[j],
                      "entrada": o["entrada"], "salida": o["salida"], "entrada_real": o["entrada"] - d.ajuste.iloc[i],
                      "dias": int(j - i), "dias_naturales": (idx[j] - idx[i]).days, "rolls": o["rolls"],
                      "bruto_usd": bruto, "costes_usd": c, "neto_usd": bruto - c, "atr_entrada": o["atr"],
                      "r": (bruto - c) / (o["atr"] * ONZAS), "ret_pct": (o["salida"] - o["entrada"]) * o["d"]
                      / (o["entrada"] - d.ajuste.iloc[i]) * 100, "abierta_al_final": bool(o.get("abierta_al_final"))})
    return pd.DataFrame(filas), diario


def comprar_y_mantener(d: pd.DataFrame, costes: Costes, desde: int) -> pd.DataFrame:
    """Referencia: siempre largo 1 contrato desde la vela `desde` (con coste de entrada y de cada cambio de contrato)."""
    O, C = d.open.to_numpy(), d.close.to_numpy()
    ids = d.instrument_id.to_numpy()
    real_c = C - d.ajuste.to_numpy()
    pnl = np.zeros(len(d))
    coste = np.zeros(len(d))
    pnl[desde] = (C[desde] - O[desde]) * ONZAS
    coste[desde] = costes.lado
    for t in range(desde + 1, len(d)):
        pnl[t] = (C[t] - C[t - 1]) * ONZAS
        if ids[t] != ids[t - 1]:
            coste[t] = 2 * costes.lado
    out = pd.DataFrame({"pos": (np.arange(len(d)) >= desde).astype(int), "pnl_bruto": pnl, "coste": coste,
                        "pnl": pnl - coste}, index=d.index)
    nocional = np.r_[np.nan, real_c[:-1]] * ONZAS
    out["ret"] = out.pnl / nocional
    out.loc[out.index[desde], "ret"] = out.pnl.iloc[desde] / (real_c[desde] * ONZAS)
    return out


def senales(d: pd.DataFrame, cfg: Config = HIPOTESIS["A"]) -> pd.DataFrame:
    """Para la auditoría de look-ahead: día de ejecución y dirección de cada entrada."""
    ops, _ = simular(d, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": ops.dia_entrada, "direccion": ops.direccion}).reset_index(drop=True)
