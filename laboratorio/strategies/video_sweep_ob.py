"""Estrategia del vídeo de la "academia" (barrida de punto estructural + liquidity sweep H1/H4 + vela envolvente, 1:1),
traducida a reglas mecánicas para NQ. Interpretación fijada ANTES de ver resultados:

1. Punto estructural barrido (cortos; largos simétrico): desde las 18:00 ET de ayer hasta la vela de señal, el precio
   ha superado alguno de: máximo de la sesión regular de ayer (PDH), máximo de Asia (20:00-00:00 ET, barrido después de
   las 00:00) o máximo de Londres (02:00-05:00 ET, barrido después de las 05:00).
2. Liquidity sweep H1 y H4 alineados: las velas de 1 h y 4 h EN CURSO (rejilla de futuros desde las 18:00 ET) han
   superado el máximo de su vela anterior y el cierre de la vela de señal está de nuevo por debajo de ese máximo.
   (Variante sin este filtro para medir lo que aporta.)
3. Timing: solo después de la apertura (9:30 ET = 15:30 España/Italia) y hasta las 11:30 ET.
4. Vela envolvente / order block: la última vela alcista anterior (la "última vela con intención" en contra) es el
   order block; la señal es una vela bajista que CIERRA por debajo del mínimo de ese order block (velas de 3 o 5 min).
5. Entrada en la apertura de la vela siguiente. Stop: máximo desde el order block hasta la señal + 1 tick.
   Objetivo 1R (el del vídeo; 2R como comparación). Cierre forzoso 15:55 ET. Una operación al día.

Partes del vídeo NO mecanizables y por tanto excluidas: elegir M3 o M5 "según se vea más bonita", usar la SMT de otro
gráfico (CFD/futuros, índice del dólar) cuando el H4 no está alineado, y operar varios mercados a discreción.
"""
import numpy as np

from backtests.intraday import Order
from data.loaders import TICK

OPEN, LAST = 930, 1050                     # minutos desde las 18:00 ET: 9:30 y 11:30


def _bars(m, tf, a, b):
    """Velas de tf minutos entre los minutos a y b (alineadas a a)."""
    out = []
    for s in range(a, b, tf):
        x = m[s:s + tf]
        ok = ~np.isnan(x[:, 0])
        if ok.any():
            y = x[ok]
            out.append((s, s + tf, y[0, 0], y[:, 1].max(), y[:, 2].min(), y[-1, 3]))
    return out


def signal(day, ctx, tf=3, htf=True, target_r=1.0):
    """`day`: dict con m24 (matriz 1 min desde las 18:00 ET de ayer), date. Devuelve Order en minutos de sesión regular."""
    m = day["m24"]
    cd = ctx.get(day["date"])
    if cd is None or np.isnan(cd.get("prev_high", np.nan)):
        return None
    H, L = m[:, 1], m[:, 2]
    asia_h, asia_l = np.nanmax(H[120:360]), np.nanmin(L[120:360])
    ldn_h, ldn_l = np.nanmax(H[480:660]), np.nanmin(L[480:660])
    bars = _bars(m, tf, 600, LAST)                       # desde las 4:00 ET para tener order blocks previos
    for j, (s, e, o, h, l, c) in enumerate(bars):
        if e <= OPEN or e > LAST:
            continue
        for side in (-1, 1):
            # 1. punto estructural barrido antes del cierre de esta vela
            if side == -1:
                swept = (np.nanmax(H[0:e]) > cd["prev_high"]) or (np.nanmax(H[360:e]) > asia_h) or \
                        (e > 660 and np.nanmax(H[660:e]) > ldn_h)
            else:
                swept = (np.nanmin(L[0:e]) < cd["prev_low"]) or (np.nanmin(L[360:e]) < asia_l) or \
                        (e > 660 and np.nanmin(L[660:e]) < ldn_l)
            if not swept:
                continue
            # 2. liquidity sweep H1 y H4 en curso
            if htf:
                ok = True
                for p in (60, 240):
                    st = (e - 1) // p * p
                    if st - p < 0:
                        ok = False; break
                    if side == -1:
                        prev = np.nanmax(H[st - p:st]); ok &= np.nanmax(H[st:e]) > prev and c < prev
                    else:
                        prev = np.nanmin(L[st - p:st]); ok &= np.nanmin(L[st:e]) < prev and c > prev
                if not ok:
                    continue
            # 4. order block: última vela en contra y cierre que la envuelve
            ob = None
            for q in range(j - 1, max(j - 11, -1), -1):
                bo, bc = bars[q][2], bars[q][5]
                if (side == -1 and bc > bo) or (side == 1 and bc < bo):
                    ob = q; break
            if ob is None:
                continue
            if side == -1 and not (c < o and c < bars[ob][4]):
                continue
            if side == 1 and not (c > o and c > bars[ob][3]):
                continue
            ext = max(b[3] for b in bars[ob:j + 1]) if side == -1 else min(b[4] for b in bars[ob:j + 1])
            stop = ext + TICK if side == -1 else ext - TICK
            return Order(side, "market", e - OPEN, stop, None, 385, target_r=target_r, tag=f"video_m{tf}")
    return None
