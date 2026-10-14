"""Pregunta del usuario: en Londres, ¿cuántas veces rompe la vela de 5 min de las 8:00 o de las 9:00 (hora de Italia)?
NQ y oro (GC.v.0), 2018-2026, reloj de Italia. Para cada vela (y las que TERMINAN a esa hora: 7:55 y 8:55):
rompe (1 tick fuera) en las 3,5 h siguientes · un lado / los dos · minutos hasta la 1.ª ruptura · tras la 1.ª ruptura,
¿llega antes a +1 rango (continúa) o al otro lado (gira)?"""
import numpy as np
import pandas as pd

from data.loaders import sessions
from run_crt_italia import rome_days
from validation.runner import new_experiment, write_manifest

WINS = {"7:55-8:00": 475, "8:00-8:05": 480, "8:55-9:00": 535, "9:00-9:05": 540}


def gold_rome():
    df = pd.read_pickle("/home/user/git_test/vwap_lab/data/cache/GC_v0_1m.pkl")
    df.index = df.index.tz_convert("Europe/Rome")
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    t = df.index
    mins = (t.hour * 60 + t.minute).to_numpy()
    out = []
    for d, idx in pd.Series(np.arange(len(df)), index=pd.Index(t.date)).groupby(level=0):
        d = pd.Timestamp(d)
        if d.weekday() >= 5:
            continue
        ii = idx.to_numpy()
        m = np.full((1320, 5), np.nan)
        ok = mins[ii] < 1320
        m[mins[ii][ok]] = arr[ii][ok]
        if (~np.isnan(m[420:720, 0])).mean() < 0.8:
            continue
        out.append((d, m))
    return out


def analyze(D, tick):
    rows = []
    for name, a in WINS.items():
        for date, m in D:
            H, L = m[:, 1], m[:, 2]
            if np.isnan(H[a:a + 5]).sum() > 2:
                continue
            hi, lo = np.nanmax(H[a:a + 5]), np.nanmin(L[a:a + 5])
            R = hi - lo
            if R <= 0:
                continue
            s0, ex = a + 5, a + 5 + 210
            up = np.nonzero(H[s0:ex] >= hi + tick - 1e-9)[0]
            dn = np.nonzero(L[s0:ex] <= lo - tick + 1e-9)[0]
            ku = up[0] if len(up) else None
            kd = dn[0] if len(dn) else None
            r = dict(vela=name, date=date, R=R, rompe=ku is not None or kd is not None,
                     dos=ku is not None and kd is not None, min_ruptura=np.nan, res=None)
            if r["rompe"] and not (ku is not None and ku == kd):
                side, k = (1, ku) if kd is None or (ku is not None and ku < kd) else (-1, kd)
                r["min_ruptura"] = k + 1
                h, l = H[s0 + k:ex], L[s0 + k:ex]
                c, g = (h >= hi + R, l <= lo) if side == 1 else (l <= lo - R, h >= hi)
                ic = np.argmax(c) if c.any() else 10 ** 6
                ig = np.argmax(g) if g.any() else 10 ** 6
                r["res"] = "nada" if ic == ig == 10 ** 6 else "ambos" if ic == ig else "continua" if ic < ig else "gira"
            rows.append(r)
    df = pd.DataFrame(rows)
    out = []
    for name, g in df.groupby("vela", sort=False):
        b = g[g.res.notna()]
        out.append(dict(vela=name, dias=len(g), rango_med=g.R.median(), rompe=g.rompe.mean() * 100,
                        un_lado=(g.rompe & ~g.dos).mean() * 100, dos_lados=g.dos.mean() * 100,
                        min_hasta_ruptura=g.min_ruptura.median(),
                        rompe_en_15min=(g.min_ruptura <= 15).mean() * 100,
                        continua=(b.res == "continua").mean() * 100, gira=(b.res == "gira").mean() * 100))
    return pd.DataFrame(out)


def main():
    exp = new_experiment("londres_vela5")
    pd.set_option("display.width", 220)
    S = sessions()
    nq = [(d, m) for d, m, _ in rome_days(S)]
    for lab_, D, tk in (("NASDAQ (MNQ)", nq, 0.25), ("ORO (MGC)", gold_rome(), 0.1)):
        o = analyze(D, tk)
        o.to_csv(exp / f"{lab_.split()[0]}.csv", index=False)
        print(f"\n=== {lab_} · velas de 5 min (hora de Italia), ventana de 3,5 h tras la vela ===")
        print(o.round(1).to_string(index=False))
    write_manifest(exp, experimento="ruptura de la vela de 5 min de las 8:00 y 9:00 Italia", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
