"""Segunda prueba de la estrategia ABC de Voy a Ser Trader, ahora con las reglas EXACTAS del directo (vídeo 2):
"impulso claro con volumen → corrección 38-61 % de Fibonacci sin volumen → nuevo impulso con volumen y absorción",
solo los primeros 90 minutos de NY, velas de 1 minuto, SMA20 y SMA200. Reglas fijadas ANTES de ver resultados:
  Datos: MNQ 1 min, sesión regular. SMA20 / SMA200 / ATR14 de 1 min encadenadas día a día (solo sesión regular: el
  premercado no está en estos datos, aproximación).
  Largo (corto espejo):
  0. Filtro: cierre > SMA200 y cierre > SMA20 en la vela de señal ("del lado correcto de la M200 y de la M20").
  1. Impulso A: swing low L0 → swing high H1 (pivotes 3/3 dentro del día, confirmados 3 velas después),
     H1 − L0 >= k × ATR14, k ∈ {2, 3}. Volumen medio del impulso alto (se compara con B).
  2. Corrección B: el mínimo desde H1 queda entre el 38,2 % y el 61,8 % del impulso, sin superar H1, dura >= 2 velas
     y su volumen medio es MENOR que el del impulso.
  3. Nuevo impulso C ("absorción + aumento de volumen"): vela alcista que cierra por encima del máximo de la anterior
     con volumen > volumen medio de B. Entrada en la apertura siguiente.
  Stop: mínimo de B − 1 tick. Objetivo: 1R, 2R o el máximo del impulso H1 (si está a < 0,5R no se opera).
  Gestión: sin más, o break even (stop a la entrada) cuando el precio avanza 0,7R (como hace él).
  Ventana: entrada entre 9:30 y 11:00 NY (15:30-17:00 Italia), 1 operación al día, cierre forzoso 12:00 NY.
  Las "zonas relevantes" (POI) no se pueden programar sin subjetividad: no se exigen.
Selección: neto > 0 en desarrollo Y validación (coste base), n_val >= 30."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Fill, Order, simulate
from data.loaders import TICK, sessions
from execution_costs.costs import mnq
from rangos_lib import stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

LAST_ENTRY, EXIT_K, P = 90, 150, 3


def indicadores(S):
    c = np.concatenate([s.m[:s.close_min, 3] for s in S])
    h = np.concatenate([s.m[:s.close_min, 1] for s in S])
    l = np.concatenate([s.m[:s.close_min, 2] for s in S])
    cs = pd.Series(c).ffill()
    sma20, sma200 = cs.rolling(20).mean().to_numpy(), cs.rolling(200).mean().to_numpy()
    pc = cs.shift()
    tr = pd.concat([pd.Series(h) - pd.Series(l), (pd.Series(h) - pc).abs(), (pd.Series(l) - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    out, i = [], 0
    for s in S:
        n = s.close_min
        out.append((sma20[i:i + n], sma200[i:i + n], atr[i:i + n]))
        i += n
    return out


def senal(s, ind, kimp, side):
    m = s.m
    O, H, L, C, V = (np.nan_to_num(m[:EXIT_K, j], nan=np.nan) for j in range(5))
    V = np.nan_to_num(V)
    s20, s200, atr = ind
    n = LAST_ENTRY + 1
    if side == -1:                              # espejo: se trabaja en "espacio largo"
        H, L, O, C = -L, -H, -O, -C
        s20, s200 = -s20, -s200
    hp = [i for i in range(P, n + 2) if not np.isnan(H[i]) and H[i] > np.nanmax(H[i - P:i]) and
          H[i] > np.nanmax(H[i + 1:i + 1 + P])]
    lp = [i for i in range(P, n + 2) if not np.isnan(L[i]) and L[i] < np.nanmin(L[i - P:i]) and
          L[i] < np.nanmin(L[i + 1:i + 1 + P])]
    for t in range(P + 2, n):
        if np.isnan(C[t]) or not (C[t] > s200[t] and C[t] > s20[t]):
            continue
        hs = [i for i in hp if i <= t - P]
        if not hs:
            continue
        H1 = hs[-1]
        ls = [i for i in lp if i < H1]
        if not ls:
            continue
        L0 = ls[-1]
        imp = H[H1] - L[L0]
        if imp < kimp * atr[t] or t - H1 < 3:
            continue
        b = np.nanmin(L[H1 + 1:t])
        ret = (H[H1] - b) / imp
        if not (0.382 <= ret <= 0.618) or np.nanmax(H[H1 + 1:t]) > H[H1]:
            continue
        vb, va = V[H1 + 1:t].mean(), V[L0:H1 + 1].mean()
        if not vb < va:
            continue
        if C[t] > O[t] and C[t] > H[t - 1] and V[t] > vb:
            stop = b - TICK
            return t + 1, side * stop, side * H[H1], C[t] - stop
    return None


def con_be(s, f, o, c):
    """Break even: si el precio llega a +0,7R antes que el stop o el objetivo, el stop pasa a la entrada."""
    m, sd = s.m, f.side
    trig = f.entry + sd * 0.7 * f.risk_pts
    H, L, O = m[:, 1], m[:, 2], m[:, 0]
    end = min(EXIT_K, s.close_min)
    for j in range(f.entry_k, f.exit_k + 1 if f.exit_k < end else end):
        if np.isnan(O[j]):
            continue
        if (sd == 1 and L[j] <= f.stop) or (sd == -1 and H[j] >= f.stop):
            return f                              # tocó el stop antes del 0,7R
        if (sd == 1 and H[j] >= trig) or (sd == -1 and L[j] <= trig):
            break
    else:
        return f
    if j >= f.exit_k and f.reason == "objetivo":
        return f
    be = f.entry
    tgt = f.target
    for k in range(j + 1, end):
        if np.isnan(O[k]):
            continue
        if (sd == 1 and L[k] <= be) or (sd == -1 and H[k] >= be):
            xp = (min(O[k], be) if sd == 1 else max(O[k], be)) - sd * c.slip
            return Fill(f.date, sd, f.entry_k, f.entry, be, tgt, k, xp, "break_even", f.risk_pts, sd * (xp - f.entry),
                        f.tag)
        if not np.isnan(tgt) and ((sd == 1 and H[k] >= tgt + c.tick) or (sd == -1 and L[k] <= tgt - c.tick)):
            return Fill(f.date, sd, f.entry_k, f.entry, be, tgt, k, tgt, "objetivo", f.risk_pts, sd * (tgt - f.entry),
                        f.tag)
    k = end - 1
    while np.isnan(m[k, 3]):
        k -= 1
    xp = m[k, 3] - sd * c.slip
    return Fill(f.date, sd, f.entry_k, f.entry, be, tgt, k, xp, "tiempo", f.risk_pts, sd * (xp - f.entry), f.tag)


def run(S, IND, kimp, tgt, be, c):
    fills = []
    for s, ind in zip(S, IND):
        cand = [x + (sd,) for sd in (1, -1) if (x := senal(s, ind, kimp, sd)) is not None]
        if not cand:
            continue
        k, stop, h1, risk, sd = min(cand)
        if tgt == "maximo_impulso":
            if risk <= 0 or sd * (h1 - (stop + sd * risk)) < 0.5 * risk:
                continue
            o = Order(sd, "market", k, stop, h1, EXIT_K, tag="vst2")
        else:
            o = Order(sd, "market", k, stop, None, EXIT_K, target_r=1.0 if tgt == "1R" else 2.0, tag="vst2")
        f = simulate(s.date, s.m, min(s.close_min, EXIT_K + 1), o, c)
        if f is None:
            continue
        fills.append(con_be(s, f, o, c) if be else f)
    return trades_frame(fills, c)


def main():
    S = sessions()
    IND = indicadores(S)
    per = periods("intradia", include_test=True)
    c = mnq("base")
    exp = new_experiment("vst_abc_video2")
    rows = []
    for kimp, tgt, be in itertools.product((2, 3), ("1R", "2R", "maximo_impulso"), (False, True)):
        t = run(S, IND, kimp, tgt, be, c)
        g = t.gross_pts
        name = f"impulso >= {kimp} ATR, objetivo {tgt}, {'break even 0,7R' if be else 'sin break even'}"
        t.to_csv(exp / f"ops_{kimp}_{tgt}_{int(be)}.csv.gz", index=False)
        rows.append(dict(variante=name, ops_año=len(t) / 8.75, gana=(g > 0).mean(), empata=(g == 0).mean(),
                         pierde=(g < 0).mean(), gana_usd=2 * g[g > 0].mean(), pierde_usd=2 * g[g < 0].mean(),
                         stop_pts=t.risk_pts.median(), **stats(t, per, c)))
        print(name, "ok", flush=True)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="VST ABC, reglas exactas del directo (1 min, 90 min, SMA, Fibo 38-61)",
                   reglas=__doc__, seleccionadas=r[r.pasa].variante.tolist())
    pd.set_option("display.width", 300, "display.max_colwidth", 70)
    print(r[["variante", "ops_año", "gana", "empata", "pierde", "gana_usd", "pierde_usd", "stop_pts", "dev", "val",
             "prueba", "ic90_FM", "años_pos", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
