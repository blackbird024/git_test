"""GOLD_SWING_SIMPLE_v1.0: 4H dirección → 1H barrido + confirmación + FVG → entrada en 15m al 50 % del FVG.

Reglas en edges/gold_swing_simple.md. Este módulo SOLO genera señales y simula; nunca ejecuta órdenes.
La estrategia solo ve velas de 15m, 1H y 4H (construidas desde 1M). Cada vela se usa desde su cierre nominal.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.data.marcos import remuestrear
from src.risk.position_sizing import contratos

VERSION = "GOLD_SWING_SIMPLE_v1.0"
INF = pd.Timestamp.max.tz_localize("UTC")


@dataclass(frozen=True)
class CostesOro:
    """Costes en $ por onza. Spread y comisión: ida y vuelta. El objetivo (límite) nunca lleva deslizamiento."""
    spread: float = 0.30
    comision: float = 0.07
    desliz_entrada: float = 0.0
    desliz_stop: float = 0.0

    def por_onza(self, motivo: str) -> float:
        return self.spread + self.comision + self.desliz_entrada + (self.desliz_stop if motivo == "SL" else 0.0)


ESCENARIOS = {
    "A": CostesOro(0.0, 0.0, 0.0, 0.0),
    "B": CostesOro(0.30, 0.07, 0.0, 0.0),
    "C": CostesOro(0.30, 0.07, 0.10, 0.30),
}


@dataclass(frozen=True)
class Config:
    version: str = VERSION
    swing_n: int = 2                 # velas a cada lado para un swing
    tp_r: float = 2.0
    entrada: str = "mitad"           # "mitad" (50 %), "cercano" (borde que toca primero), "lejano"
    buffer_atr: float = 0.10         # SL_BUFFER = buffer_atr x ATR(14) de 1H
    atr_n: int = 14
    caducidad: int = 24              # velas 1H después de la de confirmación
    riesgo_pct: float = 0.005
    saldo_inicial: float = 50_000.0
    costes: CostesOro = ESCENARIOS["B"]

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


# ------------------------------------------------------------------------------------------- datos
def ajustar_rolls(m1: pd.DataFrame) -> pd.DataFrame:
    """Ajuste hacia atrás por cambios de contrato: a todos los precios anteriores a cada cambio se les suma el salto
    (apertura del contrato nuevo − cierre del anterior). Un desplazamiento constante del pasado no cambia ninguna
    diferencia de precio, así que no introduce información futura en las reglas."""
    m = m1.copy()
    ids = m.instrument_id.to_numpy()
    p = np.flatnonzero(ids[1:] != ids[:-1]) + 1
    salto = m.open.to_numpy()[p] - m.close.to_numpy()[p - 1]
    delta = np.zeros(len(m))
    delta[p] = salto
    offset = salto.sum() - np.cumsum(delta)          # suma de los saltos de los cambios POSTERIORES a cada fila
    for c in ("open", "high", "low", "close"):
        m[c] = m[c].to_numpy() + offset
    m["ajuste"] = offset                              # precio real del contrato = precio ajustado - ajuste
    m.attrs["rolls"] = list(m.index[p])
    return m


def velas_reloj(m1: pd.DataFrame, minutos: int) -> pd.DataFrame:
    clave = m1.index.floor(f"{minutos}min")
    agg = dict(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    if "ajuste" in m1:
        agg["ajuste"] = ("ajuste", "last")
    v = m1.groupby(clave).agg(**agg)
    v["fin"] = v.index + pd.Timedelta(minutes=minutos)
    return v


def velas_4h(m1: pd.DataFrame) -> pd.DataFrame:
    v = remuestrear(m1, "4H")[["open", "high", "low", "close"]]
    v["fin"] = v.index + pd.Timedelta(hours=4)
    return v


def atr_wilder(v: pd.DataFrame, n: int) -> np.ndarray:
    pc = v.close.shift()
    tr = pd.concat([v.high - v.low, (v.high - pc).abs(), (v.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean().to_numpy()


# ------------------------------------------------------------------------------------------ reglas
def swings(high: np.ndarray, low: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Swing high en i: high[i] estrictamente mayor que las n velas a cada lado (swing low: simétrico).
    El swing de la vela i solo se conoce al CIERRE de la vela i+n."""
    L = len(high)
    sh, sl = np.zeros(L, bool), np.zeros(L, bool)
    if L < 2 * n + 1:
        return sh, sl
    sh[n:L - n] = True
    sl[n:L - n] = True
    for k in range(1, n + 1):
        sh[n:L - n] &= (high[n:L - n] > high[n - k:L - n - k]) & (high[n:L - n] > high[n + k:L - n + k])
        sl[n:L - n] &= (low[n:L - n] < low[n - k:L - n - k]) & (low[n:L - n] < low[n + k:L - n + k])
    return sh, sl


def direccion_4h(v4: pd.DataFrame, n: int) -> np.ndarray:
    """Dirección vigente tras el cierre de cada vela 4H j, con los swings confirmados hasta ese cierre (i + n <= j).
    +1 alcista (HH y HL), -1 bajista (LH y LL), 0 neutral."""
    h, l = v4.high.to_numpy(), v4.low.to_numpy()
    sh, sl = swings(h, l, n)
    altos, bajos, out = [], [], np.zeros(len(v4), int)
    for j in range(len(v4)):
        i = j - n
        if i >= 0:
            if sh[i]:
                altos.append(h[i])
            if sl[i]:
                bajos.append(l[i])
        if len(altos) >= 2 and len(bajos) >= 2:
            if altos[-1] > altos[-2] and bajos[-1] > bajos[-2]:
                out[j] = 1
            elif altos[-1] < altos[-2] and bajos[-1] < bajos[-2]:
                out[j] = -1
    return out


def barridos(v1: pd.DataFrame, n: int) -> list[dict]:
    """Todos los barridos 1H (los dos lados). Nivel vigente = último swing confirmado ANTES de que empiece la vela
    (i + n <= b - 1) y todavía no operado más allá. La primera vela que lo supera lo gasta: si cierra de vuelta
    dentro es un barrido; si no, es una ruptura (sin setup)."""
    h, l, c = v1.high.to_numpy(), v1.low.to_numpy(), v1.close.to_numpy()
    sh, sl = swings(h, l, n)
    nivel_bajo = nivel_alto = None
    sw_bajo = sw_alto = -1
    ev = []
    for b in range(len(v1)):
        i = b - 1 - n
        if i >= 0 and sl[i]:
            nivel_bajo, sw_bajo = l[i], i
        if i >= 0 and sh[i]:
            nivel_alto, sw_alto = h[i], i
        if nivel_bajo is not None and l[b] < nivel_bajo:
            if c[b] > nivel_bajo:
                ev.append({"b": b, "d": 1, "nivel": nivel_bajo, "i_swing": sw_bajo})
            nivel_bajo = None
        if nivel_alto is not None and h[b] > nivel_alto:
            if c[b] < nivel_alto:
                ev.append({"b": b, "d": -1, "nivel": nivel_alto, "i_swing": sw_alto})
            nivel_alto = None
    return ev


def precio_entrada(d: int, bajo: float, alto: float, modo: str) -> float:
    if modo == "mitad":
        return (bajo + alto) / 2
    cercano = alto if d == 1 else bajo            # el borde que el precio toca primero al volver
    lejano = bajo if d == 1 else alto
    return cercano if modo == "cercano" else lejano


def buscar_entrada(o, h, l, ini, t_desde, t_cancel, d, bajo, alto, px):
    """Orden límite en `px` sobre velas de 15m que empiezan en [t_desde, t_cancel) (instantes en ns, enteros).
    Devuelve (k, precio_llenado, None) o (None, None, motivo) con motivo 'CANCEL_TRAVERSED' o None (sin retest)."""
    k = int(np.searchsorted(ini, t_desde))
    while k < len(ini) and ini[k] < t_cancel:
        if d == 1:
            if o[k] < bajo:
                return None, None, "CANCEL_TRAVERSED"
            if l[k] <= px:
                return k, min(o[k], px), None
        else:
            if o[k] > alto:
                return None, None, "CANCEL_TRAVERSED"
            if h[k] >= px:
                return k, max(o[k], px), None
        k += 1
    return None, None, None if k < len(ini) else "NO_DATA"


def gestionar(o, h, l, c, k, d, E, SL, TP):
    """Gestión en 15m desde la vela del llenado k. En esa vela solo cuenta el stop. Stop y objetivo en la misma vela:
    pérdida. Hueco más allá del stop: salida en la apertura. Devuelve (m, salida, motivo, mae, mfe) en precio."""
    mae, mfe = 0.0, 0.0
    for m in range(k, len(o)):
        peor = l[m] if d == 1 else h[m]
        mejor = h[m] if d == 1 else l[m]
        toca_sl = (peor <= SL) if d == 1 else (peor >= SL)
        toca_tp = m > k and ((mejor >= TP) if d == 1 else (mejor <= TP))
        if m > k:
            mfe = max(mfe, min((mejor - E) * d, (TP - E) * d))
        if toca_sl:
            salida = SL if m == k else (min(SL, o[m]) if d == 1 else max(SL, o[m]))
            return m, salida, "SL", min(mae, (salida - E) * d), mfe      # MAE hasta el precio de salida
        mae = min(mae, (peor - E) * d)
        if toca_tp:
            return m, TP, "TP", mae, mfe
    return len(o) - 1, c[-1], "END_OF_DATA", mae, mfe


# ---------------------------------------------------------------------------------------- backtest
def preparar(m1: pd.DataFrame, cfg: Config) -> dict:
    m = ajustar_rolls(m1)
    v15, v1, v4 = velas_reloj(m, 15), velas_reloj(m, 60), velas_4h(m)
    return {"v15": v15, "v1": v1, "v4": v4, "rolls": m.attrs["rolls"],
            "atr": atr_wilder(v1, cfg.atr_n), "dir4": direccion_4h(v4, cfg.swing_n), "ev": barridos(v1, cfg.swing_n)}


def backtest(m1: pd.DataFrame, cfg: Config = Config(), prep: dict | None = None):
    """Devuelve (operaciones, setups). `setups` tiene una fila por barrido 1H con su destino."""
    P = prep or preparar(m1, cfg)
    v15, v1, v4, atr, dir4, ev = P["v15"], P["v1"], P["v4"], P["atr"], P["dir4"], P["ev"]
    o15, h15, l15, c15 = (v15[x].to_numpy() for x in ("open", "high", "low", "close"))
    ini15, fin15 = v15.index, pd.DatetimeIndex(v15.fin)
    ini15_ns = ini15.asi8
    aj15 = v15.ajuste.to_numpy() if "ajuste" in v15 else np.zeros(len(v15))
    h1, l1, c1 = v1.high.to_numpy(), v1.low.to_numpy(), v1.close.to_numpy()
    ini1, fin1 = v1.index, pd.DatetimeIndex(v1.fin)
    fin4 = pd.DatetimeIndex(v4.fin)
    rolls = pd.DatetimeIndex(P["rolls"])
    ev_b = np.array([e["b"] for e in ev])

    def dir_en(t):
        j = int(np.searchsorted(fin4, t, side="right")) - 1
        return dir4[j] if j >= 0 else 0

    def cambio_4h(t, d):
        """Primer cierre 4H posterior a t en que la dirección deja de ser d."""
        j = int(np.searchsorted(fin4, t, side="right"))
        otros = np.flatnonzero(dir4[j:] != d)
        return fin4[j + otros[0]] if len(otros) else INF

    saldo, libre_desde = cfg.saldo_inicial, ini15[0]
    ops, setups = [], []
    for e in ev:
        b, d = e["b"], e["d"]
        t_b = fin1[b]
        fila = {"t_barrido_fin": t_b, "lado": "LONG" if d == 1 else "SHORT", "nivel_swing": e["nivel"],
                "t_swing": ini1[e["i_swing"]], "precio_barrido": l1[b] if d == 1 else h1[b], "dir_4h": dir_en(t_b)}
        setups.append(fila)
        if fila["dir_4h"] != d:
            fila["estado"] = "NOT_ALIGNED"
            continue
        if t_b < libre_desde:
            fila["estado"] = "TRADE_OPEN"
            continue
        if b + 2 >= len(v1):
            fila["estado"] = "NO_DATA"
            continue
        if not (c1[b + 1] > h1[b] if d == 1 else c1[b + 1] < l1[b]):
            fila["estado"] = "NO_CONFIRMATION"
            continue
        fila["confirmado"] = True
        if not (l1[b + 2] > h1[b] if d == 1 else h1[b + 2] < l1[b]):
            fila["estado"] = "NO_FVG"
            continue
        bajo, alto = (h1[b], l1[b + 2]) if d == 1 else (h1[b + 2], l1[b])
        px = precio_entrada(d, bajo, alto, cfg.entrada)
        t_fvg = fin1[b + 2]
        fila.update(fvg=True, fvg_bajo=bajo, fvg_alto=alto, fvg_mitad=(bajo + alto) / 2, precio_orden=px, t_fvg=t_fvg)
        # Cancelaciones (todas se conocen al CIERRE de la vela 1H/4H en que ocurren)
        sig = np.flatnonzero(ev_b > b)
        t_nuevo = fin1[ev_b[sig[0]]] if len(sig) else INF
        fin_cad = b + 1 + cfg.caducidad
        t_cad = fin1[fin_cad] if fin_cad < len(v1) else INF
        tramo = slice(b + 1, min(fin_cad, len(v1) - 1) + 1)
        contra = np.flatnonzero(c1[tramo] < l1[b]) if d == 1 else np.flatnonzero(c1[tramo] > h1[b])
        t_contra = fin1[b + 1 + contra[0]] if len(contra) else INF
        t_4h = cambio_4h(t_b, d)
        causas = {"CANCEL_NEW_SWEEP": t_nuevo, "EXPIRED_24H": t_cad, "CANCEL_COUNTER_STRUCTURE": t_contra,
                  "CANCEL_4H_CHANGED": t_4h}
        causa, t_cancel = min(causas.items(), key=lambda x: x[1])
        # Retest (diagnóstico del embudo): ¿toca el precio de la orden dentro de la ventana de 24 velas?
        k0, k1 = int(np.searchsorted(ini15, t_fvg)), int(np.searchsorted(ini15, t_cad))
        fila["retest"] = bool((l15[k0:k1] <= px).any() if d == 1 else (h15[k0:k1] >= px).any())
        if t_cancel <= t_fvg:
            fila["estado"] = causa
            continue
        k, E, motivo = buscar_entrada(o15, h15, l15, ini15_ns, t_fvg.value, t_cancel.value, d, bajo, alto, px)
        if k is None:
            fila["estado"] = motivo or causa
            continue
        SL = (l1[b] - cfg.buffer_atr * atr[b]) if d == 1 else (h1[b] + cfg.buffer_atr * atr[b])
        R = (E - SL) * d
        TP = E + d * cfg.tp_r * R
        oz = contratos(saldo, cfg.riesgo_pct, R, 1.0)
        if oz < 1:
            fila["estado"] = "POSITION_SIZE_BELOW_MINIMUM"
            continue
        m, X, mot, mae, mfe = gestionar(o15, h15, l15, c15, k, d, E, SL, TP)
        bruto_oz = (X - E) * d
        neto_oz = bruto_oz - cfg.costes.por_onza(mot)
        t_ent, t_sal = ini15[k], fin15[m]
        op = {"t_entrada": t_ent, "t_salida": t_sal, "direccion": d, "lado": fila["lado"], "entrada": E, "sl": SL,
              "tp": TP, "salida": X, "resultado": mot, "onzas": oz, "riesgo_pts": R,
              "riesgo_usd": R * oz, "bruto_usd": bruto_oz * oz, "costes_usd": (bruto_oz - neto_oz) * oz,
              "neto_usd": neto_oz * oz, "r": neto_oz / R, "r_bruto": bruto_oz / R, "mae_r": mae / R, "mfe_r": mfe / R,
              "duracion_h": (t_sal - t_ent).total_seconds() / 3600, "saldo_antes": saldo,
              "t_swing": fila["t_swing"], "nivel_swing": e["nivel"], "precio_barrido": fila["precio_barrido"],
              "t_barrido_fin": t_b, "t_confirmacion_fin": fin1[b + 1], "t_fvg": t_fvg, "fvg_alto": alto,
              "fvg_bajo": bajo, "fvg_mitad": (bajo + alto) / 2, "atr_1h": atr[b],
              "cruza_roll": bool(((rolls > t_ent) & (rolls < t_sal)).any()),
              "ajuste_roll": aj15[k], "entrada_real": E - aj15[k], "sl_real": SL - aj15[k], "tp_real": TP - aj15[k]}
        ops.append(op)
        fila["estado"] = "ENTERED"
        saldo += op["neto_usd"]
        libre_desde = t_sal
    return pd.DataFrame(ops), pd.DataFrame(setups)


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Señales para la auditoría de look-ahead. Solo instantes y DISTANCIAS de precio (el ajuste hacia atrás desplaza
    el nivel absoluto cuando se añaden cambios de contrato posteriores, pero no las distancias)."""
    ops, _ = backtest(m1, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": ops.t_entrada, "direccion": ops.direccion,
                         "riesgo": ops.riesgo_pts.round(6), "fvg": (ops.fvg_alto - ops.fvg_bajo).round(6),
                         "t_barrido": ops.t_barrido_fin}).reset_index(drop=True)


def alerta(op: dict | pd.Series) -> str:
    """Texto de la señal (el sistema NUNCA ejecuta órdenes). Precios REALES del contrato GC de ese momento
    (sin ajuste por cambios de contrato). En XAUUSD al contado hay que aplicar la diferencia de base del momento;
    las distancias (riesgo y objetivo en $) son las mismas."""
    op = dict(op)
    if "entrada_real" in op:
        op.update(entrada=op["entrada_real"], sl=op["sl_real"], tp=op["tp_real"])
    largo = op["direccion"] == 1
    razon = ("4H bullish → 1H sell-side sweep → 1H bullish confirmation → FVG retest" if largo else
             "4H bearish → 1H buy-side sweep → 1H bearish confirmation → FVG retest")
    rr = abs(op["tp"] - op["entrada"]) / abs(op["entrada"] - op["sl"])
    return (f"{'LONG' if largo else 'SHORT'} SIGNAL — {VERSION}\n"
            f"Time (UTC): {pd.Timestamp(op['t_entrada']):%Y-%m-%d %H:%M}\n"
            f"Entry (GC): {op['entrada']:.2f}\nSL: {op['sl']:.2f}\nTP: {op['tp']:.2f}\nRR: {rr:.1f}\nReason: {razon}")
