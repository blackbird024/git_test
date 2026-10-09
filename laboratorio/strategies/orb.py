"""A1 · ORB de 5 minutos en MNQ (precios de NQ). Tres variantes que se evalúan por separado.

Rango: velas de 1 min de 9:30 a 9:34 ET (ORH, ORL). Entradas solo antes de las 11:00 ET.
  immediate  órdenes stop en ORH + 1 tick y ORL − 1 tick desde las 9:35 (OCO: la primera que se activa).
  close      primera vela de 5 min (desde la de 9:35) que cierra fuera del rango → entrada a mercado en la apertura siguiente.
  retest     ruptura con cierre; en las 3 velas de 5 min siguientes (sin contar la de ruptura) una vela toca el nivel
             (a 2 ticks o menos) y cierra de nuevo fuera → entrada en la apertura siguiente. Un cierre dentro del rango
             invalida; un cierre al otro lado cancela el día.

Stops:   "rango" = lado opuesto del rango ∓ 1 tick (immediate/close); en retest, extremo de la vela de retesteo ∓ 1 tick.
         "vol"   = 0,10 × ATR14 diario (del día anterior) desde el nivel de entrada de referencia.
Salidas: "2R_1130" = objetivo 2R desde la entrada efectiva, cierre forzoso 11:30 ET.
         "eod"     = sin objetivo, cierre a las 15:55 ET.
Filtros opcionales (se evalúan aparte, nunca por defecto):
  trend = solo a favor del cierre de ayer respecto a su EMA50 diaria; vol = no operar en el quintil superior de volatilidad.
"""
import numpy as np

from backtests.intraday import Order
from data.loaders import TICK, bars5

ENTRY_LAST_K = 90           # 11:00 ET
EXITS = {"2R_1130": (2.0, 120), "eod": (None, 385)}


def _range(s, n=5):
    x = s.m[:n]
    if np.isnan(x[:, 0]).all():
        return None
    return np.nanmax(x[:, 1]), np.nanmin(x[:, 2])


def _filters_ok(side, ctx_day, trend, vol):
    if trend:
        if ctx_day is None or np.isnan(ctx_day["ema50"]):
            return False
        if side * (ctx_day["prev_close"] - ctx_day["ema50"]) <= 0:
            return False
    if vol:
        if ctx_day is None or np.isnan(ctx_day["vol_rank"]) or ctx_day["vol_rank"] > 0.8:
            return False
    return True


def _stop(side, ref, orh, orl, stop_mode, ctx_day, mult=0.10):
    if stop_mode == "rango":
        return orl - TICK if side == 1 else orh + TICK
    a = ctx_day["atr14"] if ctx_day else np.nan
    if a is None or np.isnan(a):
        return None
    d = max(round(mult * a / TICK) * TICK, TICK)
    return ref - side * d


def orb(s, ctx, variant="close", stop_mode="rango", exit="2R_1130", trend=False, vol=False,
        range_min=5, entry_last_k=ENTRY_LAST_K, exit_k=None, vol_mult=0.10, target="R", min_r=0.0):
    """target="R": objetivo en múltiplos de R (según `exit`); target="pdhl": objetivo en el máximo (largos) o mínimo
    (cortos) de la sesión regular de ayer, solo en la variante retest; se descarta si está a menos de `min_r` R."""
    """`range_min`, `exit_k` y `vol_mult` solo se usan en las pruebas de perturbación (range_min solo en immediate)."""
    r = _range(s, range_min)
    if r is None:
        return None
    orh, orl = r
    cd = ctx.get(s.date)
    tr, xk = EXITS[exit]
    xk = exit_k or xk
    ENTRY_LAST = entry_last_k
    if variant == "immediate":
        up, dn = orh + TICK, orl - TICK
        H, L, O = s.m[:, 1], s.m[:, 2], s.m[:, 0]
        for k in range(range_min, ENTRY_LAST):
            if np.isnan(O[k]):
                continue
            hu, hd = H[k] >= up, L[k] <= dn
            if hu and hd:                                  # ambas en el mismo minuto: la más cercana a la apertura
                side = 1 if abs(O[k] - up) <= abs(O[k] - dn) else -1
            elif hu or hd:
                side = 1 if hu else -1
            else:
                continue
            lvl = up if side == 1 else dn
            if not _filters_ok(side, cd, trend, vol):
                return None
            st = _stop(side, lvl, orh, orl, stop_mode, cd, vol_mult)
            if st is None:
                return None
            return Order(side, "stop", k, st, None, xk, level=lvl, k_last=k + 1, target_r=tr, tag="immediate")
        return None
    b = bars5(s)
    nb = len(b)
    if variant == "close":
        for i in range(1, min(nb, ENTRY_LAST // 5)):
            c = b[i, 3]
            if np.isnan(c):
                continue
            side = 1 if c > orh else (-1 if c < orl else 0)
            if not side:
                continue
            if 5 * (i + 1) >= ENTRY_LAST or not _filters_ok(side, cd, trend, vol):
                return None
            st = _stop(side, c, orh, orl, stop_mode, cd, vol_mult)
            if st is None:
                return None
            return Order(side, "market", 5 * (i + 1), st, None, xk, target_r=tr, tag="close")
        return None
    if variant == "retest":
        side, ib = 0, None
        for i in range(1, min(nb, ENTRY_LAST // 5)):
            o, h, l, c = b[i]
            if np.isnan(c):
                continue
            if not side:
                side = 1 if c > orh else (-1 if c < orl else 0)
                ib = i if side else None
                continue
            if i > ib + 3:
                return None                                # ventana agotada
            if orl <= c <= orh:
                return None                                # cierre dentro del rango: invalidada
            if (side == 1 and c < orl) or (side == -1 and c > orh):
                return None                                # cierre al otro lado: día cancelado
            lvl = orh if side == 1 else orl
            touched = (l <= lvl + 2 * TICK) if side == 1 else (h >= lvl - 2 * TICK)
            beyond = c > lvl if side == 1 else c < lvl
            if touched and beyond:
                if 5 * (i + 1) >= ENTRY_LAST or not _filters_ok(side, cd, trend, vol):
                    return None
                st = (l - TICK) if side == 1 else (h + TICK)
                if stop_mode == "vol":
                    st = _stop(side, c, orh, orl, "vol", cd, vol_mult)
                    if st is None:
                        return None
                if target == "pdhl":
                    if cd is None:
                        return None
                    tgt = cd["prev_high"] if side == 1 else cd["prev_low"]
                    if tgt is None or np.isnan(tgt) or side * (tgt - c) < min_r * side * (c - st) or side * (tgt - c) <= 0:
                        return None
                    return Order(side, "market", 5 * (i + 1), st, tgt, xk, tag="retest_pdhl")
                return Order(side, "market", 5 * (i + 1), st, None, xk, target_r=tr, tag="retest")
        return None
    raise ValueError(variant)
