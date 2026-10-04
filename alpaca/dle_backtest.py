"""Backtest de "Direction, Location, Execution" (price action en 3 temporalidades).

Reglas mecánicas (interpretación del vídeo):
  1. Dirección (4H): estructura con máximos/mínimos de swing (pivotes de 2 velas a cada lado).
     Un cierre por encima del último swing alto = tendencia alcista (BOS); el rango de swing va
     del último swing bajo al máximo alcanzado. Simétrico para la bajista.
  2. Ubicación: solo compras en zona de descuento (por debajo del 50% del rango) sin perder el
     swing bajo; solo ventas en zona premium sin superar el swing alto.
  3. Ejecución (15m), las tres confluencias en la vela que cierra:
       - Rechazo fuerte: vela envolvente, o pin bar seguida de vela de desplazamiento.
       - Barrido de liquidez y fallo: el mínimo del rechazo es el más bajo de las últimas 12 velas.
       - Ruptura y cierre a favor: cierra por encima del máximo de las 2 velas anteriores.
     Entrada al cierre, stop bajo el mínimo del rechazo, objetivo 3R. Una posición a la vez.

Uso:
    python dle_backtest.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m


def resample(df, rule):
    return df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def structure_4h(h4, pivot=2):
    """Para cada vela de 4H cerrada: sesgo (+1/-1/0), mínimo y máximo del rango de swing."""
    hi, lo, cl = h4["high"].to_numpy(), h4["low"].to_numpy(), h4["close"].to_numpy()
    n = len(h4)
    bias = np.zeros(n); r_lo = np.full(n, np.nan); r_hi = np.full(n, np.nan)
    last_sh = last_sl = np.nan
    b, a, z = 0, np.nan, np.nan
    for i in range(n):
        j = i - pivot                       # pivote confirmado con 'pivot' velas después
        if j >= pivot:
            if hi[j] == hi[j - pivot:i + 1].max():
                last_sh = hi[j]
            if lo[j] == lo[j - pivot:i + 1].min():
                last_sl = lo[j]
        if not np.isnan(last_sh) and cl[i] > last_sh and b != 1:
            b, a, z = 1, last_sl, hi[i]     # BOS alcista: rango desde el último swing bajo
        elif not np.isnan(last_sl) and cl[i] < last_sl and b != -1:
            b, a, z = -1, last_sh, lo[i]    # BOS bajista: rango desde el último swing alto
        elif b == 1:
            z = max(z, hi[i])
            if cl[i] < a:                   # pierde el swing bajo: estructura rota
                b = 0
        elif b == -1:
            z = min(z, lo[i])
            if cl[i] > a:
                b = 0
        bias[i] = b
        r_lo[i], r_hi[i] = (a, z) if b == 1 else (z, a) if b == -1 else (np.nan, np.nan)
    out = pd.DataFrame({"bias": bias, "r_lo": r_lo, "r_hi": r_hi}, index=h4.index)
    out.index = out.index + pd.Timedelta(hours=4)       # se conoce al cerrar la vela
    return out


def backtest(df5, cost, target_r=3.0, max_bars=4 * 24 * 5, sweep_n=12):
    m15 = resample(df5, "15min")
    h4 = resample(df5, "4h")
    st = structure_4h(h4).reindex(m15.index, method="ffill")
    o, h, l, c = (m15[k].to_numpy() for k in ("open", "high", "low", "close"))
    bias, rlo, rhi = (st[k].to_numpy() for k in ("bias", "r_lo", "r_hi"))
    body = np.abs(c - o)
    avg_body = pd.Series(body).rolling(20).mean().to_numpy()
    results, i = [], 13
    while i < len(m15) - 1:
        d = bias[i]
        if d == 0 or np.isnan(rlo[i]):
            i += 1
            continue
        eq = (rlo[i] + rhi[i]) / 2
        if d == 1:
            in_loc = l[i] <= eq and l[i] > rlo[i]
            engulf = c[i] > o[i] and c[i - 1] < o[i - 1] and c[i] >= o[i - 1] and o[i] <= c[i - 1]
            pin = (min(o[i - 1], c[i - 1]) - l[i - 1]) >= 2 * body[i - 1] and c[i] > o[i] and body[i] >= 1.5 * avg_body[i]
            rej_low = min(l[i - 1], l[i])
            sweep = sweep_n == 0 or rej_low <= l[i - sweep_n:i + 1].min()
            brk = c[i] > max(h[i - 1], h[i - 2])
            ok = in_loc and (engulf or pin) and sweep and brk
            stop = rej_low
        else:
            in_loc = h[i] >= eq and h[i] < rhi[i]
            engulf = c[i] < o[i] and c[i - 1] > o[i - 1] and c[i] <= o[i - 1] and o[i] >= c[i - 1]
            pin = (h[i - 1] - max(o[i - 1], c[i - 1])) >= 2 * body[i - 1] and c[i] < o[i] and body[i] >= 1.5 * avg_body[i]
            rej_high = max(h[i - 1], h[i])
            sweep = sweep_n == 0 or rej_high >= h[i - sweep_n:i + 1].max()
            brk = c[i] < min(l[i - 1], l[i - 2])
            ok = in_loc and (engulf or pin) and sweep and brk
            stop = rej_high
        if not ok:
            i += 1
            continue
        entry = c[i]
        risk = abs(entry - stop)
        if risk <= 0:
            i += 1
            continue
        target = entry + d * target_r * risk
        exit_px = None
        for j in range(i + 1, min(i + max_bars, len(m15))):
            if (d == 1 and l[j] <= stop) or (d == -1 and h[j] >= stop):
                exit_px = min(stop, o[j]) if d == 1 else max(stop, o[j])   # huecos: peor precio
                break
            if (d == 1 and h[j] >= target) or (d == -1 and l[j] <= target):
                exit_px = max(target, o[j]) if d == 1 else min(target, o[j])
                break
        else:
            j = min(i + max_bars, len(m15)) - 1
            exit_px = c[j]
        r = d * (exit_px - entry) / risk - 2 * cost * entry / risk
        results.append((m15.index[i], d, r))
        i = j + 1
    return pd.DataFrame(results, columns=["time", "dir", "r"])


def report(name, t):
    if t.empty:
        print(f"  {name:40} sin operaciones")
        return
    r = t["r"]
    curve = r.cumsum()
    half = len(r) // 2
    pf = r[r > 0].sum() / -r[r < 0].sum()
    longs = t[t["dir"] == 1]["r"]
    shorts = t[t["dir"] == -1]["r"]
    print(f"  {name:40}{len(r):>5}{(r > 0).mean():>7.0%}{r.mean():>+8.2f}{r.sum():>+8.1f}{pf:>7.2f}"
          f"{(curve - curve.cummax()).min():>8.1f}{r.iloc[:half].sum():>+8.1f}{r.iloc[half:].sum():>+8.1f}"
          f"{longs.sum():>+9.1f}{shorts.sum():>+9.1f}")


def main():
    print(f"\n  {'Mercado':40}{'Ops':>5}{'Gan.':>7}{'R med':>8}{'R tot':>8}{'F.ben':>7}{'DD (R)':>8}"
          f"{'1ª mit':>8}{'2ª mit':>8}{'Compras':>9}{'Ventas':>9}")
    for name, symbol, cost, rth in (("Nasdaq (QQQ)", "QQQ", 0.00005, True),
                                    ("Oro (GLD)", "GLD", 0.00005, True),
                                    ("BTC (24h)", "BTC/USD", 0.0005, False),
                                    ("ETH (24h)", "ETH/USD", 0.0005, False)):
        df = load_5m(symbol)
        if rth:   # sesión regular de bolsa
            t = df.index.hour + df.index.minute / 60
            df = df[(t >= 9.5) & (t < 16)]
        for sweep_n, label in ((12, "estricta"), (6, "barrido 6 velas"), (0, "sin barrido")):
            for tr in (3.0, 2.0):
                report(f"{name}, {label}, {tr:.0f}R", backtest(df, cost, target_r=tr, sweep_n=sweep_n))
    print("\n  Con objetivo 3R hace falta acertar más del 25% para no perder; con 2R, más del 33%.")


if __name__ == "__main__":
    main()
