"""Petición: probar el DAX en la mañana europea (el usuario quiere operar Londres). FDAX.c.0 1 min (Eurex, Databento
XEUR.EOBI), SOLO 2025-03-10 → 2026-10-13 (~19 meses: no hay desarrollo/validación; resultados = INDICIOS). Hora de
Italia = hora de Frankfurt. Se excluyen la semana del vencimiento trimestral (+ lunes siguiente),
días con saltos de >0,5 % entre minutos y días con <80 % de minutos 9:00-17:30. Reglas fijadas antes de ver resultados:
A) Volatilidad por tramo: 2:00-9:00, 9:00-14:30, 14:30-15:30, 15:30-17:30, 17:30-22:00 (rango mediano y por hora).
B) Carrera continúa/gira de velas de 5 min (8:00, 8:55, 9:00, 9:05, 10:00, 14:25, 15:25, 15:30) y de 15 min (9:00):
   tras la primera ruptura, ¿llega antes a +1 rango más allá (continúa) o al otro lado (gira)? Plazo 3,5 h.
C) Estrategias (1 op/vela/día): RUPTURA a favor, orden stop OCO 1 tick fuera (doble ruptura en el mismo minuto = no se
   opera); stop S = máx(rango, Smin), Smin ∈ {0, 0,1 % del precio}; objetivo 0,5 S, 0,75 rango o 1 S; plazo 3,5 h.
   GIRO: en la ruptura, en contra a mercado, objetivo el otro lado, stop a 1 rango.
D) HUECO de la apertura (9:00) contra el cierre de Xetra del día anterior (17:30): % de días que lo rellena antes de
   las 17:30 según tamaño; estrategia RELLENO (en contra, objetivo el cierre anterior, stop a la misma distancia).
Probabilidades: gana / pierde = resultado bruto en puntos (1 tick de deslizamiento por lado en entradas/salidas a
mercado o stop). Consistencia: 2025 vs 2026 por separado."""
from pathlib import Path

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import FutCost
from validation.metrics import trades_frame
from validation.runner import new_experiment, write_manifest

N = 1320
RAW = Path(__file__).resolve().parents[1] / "vwap_lab" / "data" / "cache" / "FDAX_c_0_1m.pkl"


def dias():
    df = pd.read_pickle(RAW)
    df.index = df.index.tz_convert("Europe/Rome")
    tick = float(np.round(np.diff(np.unique(df.close.to_numpy()[:20000])).min(), 4))
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    t = df.index
    mins = (t.hour * 60 + t.minute).to_numpy()
    out = []
    for d, idx in pd.Series(np.arange(len(df)), index=pd.Index(t.date)).groupby(level=0):
        d = pd.Timestamp(d)
        ii = idx.to_numpy()
        ii = ii[mins[ii] < N]
        if d.weekday() >= 5 or len(ii) == 0:
            continue
        m = np.full((N, 5), np.nan)
        m[mins[ii]] = arr[ii]
        jump = np.nanmax(np.abs(m[1:, 0] - m[:-1, 3]) / m[:-1, 3]) if (~np.isnan(m[:, 0])).sum() > 1 else 0
        if (~np.isnan(m[540:1050, 0])).mean() >= 0.8 and not (jump > 0.005) and not semana_roll(d):
            out.append((d, m))
    return out, tick


def semana_roll(d):
    """Los identificadores de Eurex no son estables: se excluye la semana del vencimiento trimestral (lunes a viernes
    de la semana del tercer viernes de mar/jun/sep/dic) y el lunes siguiente."""
    if d.month not in (3, 6, 9, 12):
        return False
    f = pd.Timestamp(d.year, d.month, 15)
    f += pd.Timedelta(days=(4 - f.weekday()) % 7)
    return f - pd.Timedelta(days=4) <= d <= f + pd.Timedelta(days=3)


def setup(m, a, dur, tick):
    H, L = m[:, 1], m[:, 2]
    if np.isnan(H[a:a + dur]).sum() > dur / 2:
        return None
    hi, lo = np.nanmax(H[a:a + dur]), np.nanmin(L[a:a + dur])
    R = hi - lo
    if R <= 0:
        return None
    s0 = a + dur
    ex = min(s0 + 210, N - 1)
    eps = tick * 1e-3
    up = np.nonzero(H[s0:ex] >= hi + tick - eps)[0]
    dn = np.nonzero(L[s0:ex] <= lo - tick + eps)[0]
    ku = up[0] + s0 if len(up) else None
    kd = dn[0] + s0 if len(dn) else None
    if ku is None and kd is None:
        return None
    if ku is not None and ku == kd:
        return "mismo"
    side, k = (1, ku) if kd is None or (ku is not None and ku < kd) else (-1, kd)
    return hi, lo, R, side, k, ex


def race(m, st):
    hi, lo, R, side, k, ex = st
    H, L = m[k:ex, 1], m[k:ex, 2]
    c, r = (H >= hi + R, L <= lo) if side == 1 else (L <= lo - R, H >= hi)
    ic = np.argmax(c) if c.any() else 10 ** 6
    ir = np.argmax(r) if r.any() else 10 ** 6
    if ic == ir == 10 ** 6:
        return "nada"
    if ic == ir:
        return "ambos"
    return "continua" if ic < ir else "gira"


def hm(a):
    return f"{a // 60}:{a % 60:02d}"


VELAS = [(5, 480), (5, 535), (5, 540), (5, 545), (5, 600), (5, 865), (5, 925), (5, 930), (15, 540)]


def resumen(t, nombre):
    g = t.gross_pts
    y = t.date.dt.year
    return dict(estrategia=nombre, ops=len(t), gana=(g > 0).mean(), pierde=(g < 0).mean(),
                gana_pts=g[g > 0].mean(), pierde_pts=g[g < 0].mean(), media_pts=g.mean(),
                media_2025=g[y == 2025].mean(), media_2026=g[y == 2026].mean(),
                riesgo_med_pts=t.risk_pts.median() if "risk_pts" in t else np.nan)


def main():
    D, tick = dias()
    c = FutCost(point_value=25.0, tick=tick, fixed_per_side=0.0, slip_ticks=1.0)
    rnd = lambda x: round(x / tick) * tick
    exp = new_experiment("dax_londres")
    print(len(D), "días", D[0][0].date(), "→", D[-1][0].date(), "tick", tick)

    # A) volatilidad
    rows = []
    for a, b in [(120, 540), (540, 870), (870, 930), (930, 1050), (1050, 1320)]:
        r = [np.nanmax(m[a:b, 1]) - np.nanmin(m[a:b, 2]) for _, m in D if (~np.isnan(m[a:b, 0])).mean() > 0.5]
        rows.append(dict(tramo=f"{hm(a)}-{hm(b)}", dias=len(r), rango_mediano=np.median(r),
                         por_hora=np.median(r) / ((b - a) / 60)))
    A = pd.DataFrame(rows)

    # B) carrera
    rows = []
    for dur, a in VELAS:
        res = []
        for d, m in D:
            st = setup(m, a, dur, tick)
            if st is None:
                continue
            res.append((d.year, "ambos_lados_misma_vela" if st == "mismo" else race(m, st), st != "mismo" and st[2]))
        x = pd.DataFrame(res, columns=["año", "r", "R"])
        v = x[x.r.isin(["continua", "gira", "ambos", "nada"])]
        rows.append(dict(vela=f"{dur} min {hm(a)}", dias=len(v), rango_med=v.R.astype(float).median(),
                         continua=(v.r == "continua").astype(float).mean(), gira=(v.r == "gira").astype(float).mean(),
                         cont_2025=(v[v.año == 2025].r == "continua").astype(float).mean(),
                         cont_2026=(v[v.año == 2026].r == "continua").astype(float).mean()))
    B = pd.DataFrame(rows)

    # C) estrategias
    rows = []
    for dur, a in VELAS:
        for smin, tg in [(s, t) for s in (0.0, 0.001) for t in ("0.5S", "0.75R", "1S")] + [(None, "giro")]:
            fills = []
            for d, m in D:
                st = setup(m, a, dur, tick)
                if st is None or st == "mismo":
                    continue
                hi, lo, R, side, k, ex = st
                edge, opp = (hi, lo) if side == 1 else (lo, hi)
                if tg == "giro":
                    o = Order(-side, "market", k + 1, rnd(edge + side * R), opp, ex)
                else:
                    S = max(R, smin * edge)
                    dist = {"0.5S": 0.5 * S, "0.75R": 0.75 * R, "1S": S}[tg]
                    o = Order(side, "stop", k, rnd(edge - side * S - side * tick), rnd(edge + side * dist), ex,
                              level=rnd(edge + side * tick), k_last=k + 1)
                f = simulate(d, m, ex + 1, o, c)
                if f is not None:
                    fills.append(f)
            t = trades_frame(fills, c)
            nombre = (f"vela {dur} min {hm(a)} · GIRO (obj otro lado, stop 1 rango)" if tg == "giro" else
                      f"vela {dur} min {hm(a)} · RUPTURA stop mín {'rango' if smin == 0 else '0,1 %'}, obj {tg}")
            rows.append(resumen(t, nombre))
    C = pd.DataFrame(rows)

    # D) hueco
    rows, fills = [], {g: [] for g in (0.001, 0.002, 0.004)}
    prev = None
    for d, m in D:
        if prev is not None and (d - prev[0]).days <= 4:
            pc = prev[1][1020:1050, 3][~np.isnan(prev[1][1020:1050, 3])]
            o = m[540:545, 0][~np.isnan(m[540:545, 0])]
            if len(pc) and len(o):
                g = o[0] - pc[-1]
                H, L = m[540:1050, 1], m[540:1050, 2]
                rell = (np.nanmin(L) <= pc[-1]) if g > 0 else (np.nanmax(H) >= pc[-1])
                rows.append(dict(año=d.year, hueco_pct=abs(g) / pc[-1], relleno=rell))
                for gmin in fills:
                    if abs(g) >= gmin * pc[-1]:
                        s = -int(np.sign(g))
                        f = simulate(d, m, 1050, Order(s, "market", 540, rnd(o[0] - s * abs(g)), rnd(pc[-1]), 1049), c)
                        if f is not None:
                            fills[gmin].append(f)
        prev = (d, m)
    h = pd.DataFrame(rows)
    h["tam"] = pd.cut(h.hueco_pct * 100, [0, 0.1, 0.2, 0.4, 0.8, 100], labels=["<0,1 %", "0,1-0,2 %", "0,2-0,4 %",
                                                                             "0,4-0,8 %", ">0,8 %"])
    Dh = h.groupby("tam", observed=True).agg(dias=("relleno", "size"), rellena=("relleno", "mean"))
    C = pd.concat([C, pd.DataFrame([resumen(trades_frame(f, c), f"HUECO 9:00 >= {g * 100:.1f} % · RELLENO 1:1, "
                                                                 "cierre 17:30") for g, f in fills.items()])])

    pd.set_option("display.width", 260, "display.max_rows", 200, "display.max_colwidth", 70)
    print("\nA) volatilidad (puntos)\n", A.round(1).to_string(index=False))
    print("\nB) carrera continúa / gira\n", B.round(2).to_string(index=False))
    print("\nC) estrategias (puntos brutos)\n", C.round(2).to_string(index=False))
    print("\nD) relleno del hueco antes de las 17:30\n", Dh.round(2).to_string())
    for n_, x in (("volatilidad", A), ("carrera", B), ("estrategias", C)):
        x.to_csv(exp / f"{n_}.csv", index=False)
    Dh.to_csv(exp / "hueco.csv")
    write_manifest(exp, experimento="DAX (FDAX) en la mañana europea: indicios con 19 meses", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
