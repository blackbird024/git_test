"""Módulo CRT (Candle Range Theory) de 4 horas como filtro direccional del Confirmation Model B+.

Velas de 4H de CME tal como las dibuja TradingView en NQ/ES: empiezan a las 18:00 NY (apertura de la sesión
Globex) → 18-22, 22-02, 02-06, 06-10, 10-14, 14-17. Un CRT solo existe al CIERRE de la vela que lo confirma.

CRT alcista: una vela posterior a la de referencia perfora su mínimo y una vela (la misma u otra, hasta
`confirm_bars` velas después de la referencia) cierra de nuevo DENTRO del rango (mínimo < cierre < máximo).
Bajista: simétrico con el máximo.

Referencia:
  previous    la vela de 4H anterior a la que barre.
  pre_london  la última vela de 4H cerrada antes de Londres (22:00-02:00 NY); el CRT se confirma como pronto
              al cierre de 02:00-06:00, es decir a las 6:00 NY (después de la killzone de London).

Sesgo: empieza en la confirmación y dura según `validity`; deja de valer si se invalida (un cierre de 5m más allá
del extremo del barrido) o según `on_contrary` cuando aparece un CRT contrario.

Uso:
    python cm_crt.py
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

import cm_bplus_engine as E

H = 3600 * 10**9


@dataclass
class CRTConfig:
    name: str = "anterior · hasta el siguiente cierre de 4H"
    reference: str = "previous"          # previous | pre_london
    confirm_bars: int = 1                # velas de 4H tras la referencia para barrer y cerrar dentro
    validity: str = "next_close"         # next_close | hours | london | until_contrary
    hours: float = 4.0
    on_contrary: str = "replace"         # replace | wait_close | invalidate
    invalidate_on_close: bool = True     # un cierre de 5m más allá del extremo del barrido anula el sesgo


def bars_4h(m):
    b = m.df.resample("4h", offset="2h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return b


def crt_events(m, cfg):
    b = bars_4h(m)
    st = b.index
    # cierre de cada vela: 4 h después, salvo la de 14:00 NY, que termina a las 17:00 (cierre diario de CME)
    end = st.asi8 + 4 * H - np.where(st.hour == 14, H, 0)
    hi, lo, cl = b["high"].to_numpy(), b["low"].to_numpy(), b["close"].to_numpy()
    hrs = st.hour.to_numpy()
    ev = []
    refs = range(len(b) - 1) if cfg.reference == "previous" else [i for i in range(len(b) - 1) if hrs[i] == 22]
    for r in refs:
        swept_lo, swept_hi = np.inf, -np.inf
        for k in range(r + 1, min(r + 1 + cfg.confirm_bars, len(b))):
            swept_lo, swept_hi = min(swept_lo, lo[k]), max(swept_hi, hi[k])
            bull = swept_lo < lo[r] and lo[r] < cl[k] < hi[r]
            bear = swept_hi > hi[r] and lo[r] < cl[k] < hi[r]
            if bull and bear:                       # barrió los dos lados: ambiguo, se descarta
                break
            if bull or bear:
                d = 1 if bull else -1
                ev.append(dict(t=end[k], d=d, ref_hi=hi[r], ref_lo=lo[r], ext=swept_lo if bull else swept_hi,
                               close=cl[k], ref=cfg.reference))
                break
    return pd.DataFrame(ev).sort_values("t").reset_index(drop=True)


def bias_intervals(m, cfg, ev):
    """Lista de intervalos [inicio, fin) con dirección y datos del CRT, sin solaparse."""
    out = []
    t5, c5 = m.t, m.c
    for i, e in ev.iterrows():
        start = int(e.t)
        if cfg.validity == "next_close" or cfg.validity == "hours":
            stop = start + int((4 if cfg.validity == "next_close" else cfg.hours) * H)
        elif cfg.validity == "london":
            day = pd.Timestamp(start, tz="America/New_York").normalize()
            s_end = day + pd.Timedelta(hours=5)
            if s_end.value <= start:
                s_end += pd.Timedelta(days=1)
            stop = s_end.value
        else:
            stop = start + 7 * 24 * H
        # CRT siguiente: el contrario corta este sesgo; uno igual lo renueva (se trata como nuevo intervalo)
        nxt = ev.iloc[i + 1:]
        if len(nxt):
            n = nxt.iloc[0]
            if n.t < stop:
                stop = int(n.t)
        # invalidación por cierre de 5m más allá del extremo barrido
        if cfg.invalidate_on_close:
            a, z = np.searchsorted(t5, start), np.searchsorted(t5, stop)
            seg = c5[a:z]
            bad = np.nonzero(seg < e.ext)[0] if e.d == 1 else np.nonzero(seg > e.ext)[0]
            if len(bad):
                stop = int(t5[a + bad[0]] + 5 * 60 * 10**9)
        out.append([start, stop, int(e.d), float(e.ext)])
    # CRT contrario
    if cfg.on_contrary != "replace":
        adj = []
        for j, (s, f, d, x) in enumerate(out):
            if j and out[j - 1][2] == -d and out[j - 1][1] >= s:
                if cfg.on_contrary == "wait_close":
                    s = s + 4 * H                      # el nuevo sesgo empieza al cierre de la siguiente vela de 4H
                else:
                    continue                           # se anulan ambos: hay que esperar otra confirmación
            if s < f:
                adj.append([s, f, d, x])
        out = adj
    return np.array([o[:3] for o in out], dtype=np.int64)


def bias_at(iv, times):
    """Dirección del sesgo vigente en cada instante (0 = sin CRT) y antigüedad en horas."""
    times = np.asarray(times, dtype=np.int64)
    k = np.searchsorted(iv[:, 0], times, side="right") - 1
    ok = (k >= 0) & (times < iv[np.maximum(k, 0), 1])
    d = np.where(ok, iv[np.maximum(k, 0), 2], 0)
    age = np.where(ok, (times - iv[np.maximum(k, 0), 0]) / H, np.nan)
    return d, age


def stats(r):
    r = np.asarray(r)
    if len(r) == 0:
        return dict(ops=0)
    eq = np.cumsum(r)
    g, ls = r[r > 0].sum(), -r[r < 0].sum()
    return {"ops": len(r), "ganadoras": int((r > 0).sum()), "perdedoras": int((r <= 0).sum()),
            "acierto": f"{(r > 0).mean():.0%}", "R/op": round(r.mean(), 3), "PF": round(g / ls, 2) if ls else np.inf,
            "R neto": round(r.sum(), 1), "DD máx R": round((np.maximum.accumulate(eq) - eq).max(), 1)}


def compare(tr, crt_d, months, label):
    tr = tr.copy()
    tr["crt"] = crt_d
    tr["al"] = np.where(tr["crt"] == 0, "sin CRT", np.where(tr["crt"] == tr["d"], "alineada", "contraria"))
    dev = tr["t"].dt.year < 2023
    rows = []
    for name, sel in (("A · B+ original", np.ones(len(tr), bool)), ("B · CRT obligatorio", (tr.al == "alineada").to_numpy()),
                      ("C · alineadas", (tr.al == "alineada").to_numpy()), ("C · contrarias", (tr.al == "contraria").to_numpy()),
                      ("C · sin CRT", (tr.al == "sin CRT").to_numpy()), ("descartadas por B", (tr.al != "alineada").to_numpy())):
        s = stats(tr.r[sel])
        s.update({"al mes": round(sel.sum() / months, 1),
                  "desarrollo R/op": round(tr.r[sel & dev.to_numpy()].mean(), 3) if (sel & dev.to_numpy()).any() else np.nan,
                  "validación R/op": round(tr.r[sel & ~dev.to_numpy()].mean(), 3) if (sel & ~dev.to_numpy()).any() else np.nan,
                  "largos R": round(tr.r[sel & (tr.d == 1).to_numpy()].sum(), 1),
                  "cortos R": round(tr.r[sel & (tr.d == -1).to_numpy()].sum(), 1)})
        rows.append({"CRT": label, "grupo": name, **s})
    return pd.DataFrame(rows), tr


CRT_CONFIGS = [
    CRTConfig(),
    CRTConfig(name="anterior · 8 h", validity="hours", hours=8),
    CRTConfig(name="anterior · hasta CRT contrario", validity="until_contrary"),
    CRTConfig(name="anterior · hasta fin de London", validity="london"),
    CRTConfig(name="anterior · 2 velas para confirmar", confirm_bars=2),
    CRTConfig(name="anterior · contrario espera cierre 4H", on_contrary="wait_close"),
    CRTConfig(name="anterior · contrario anula ambos", on_contrary="invalidate"),
    CRTConfig(name="anterior · sin invalidación 5m", invalidate_on_close=False),
    CRTConfig(name="pre-London · hasta CRT contrario", reference="pre_london", validity="until_contrary"),
]


def main():
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    m = E.Market("NQ")
    months = (m.idx[-1] - m.idx[0]).days / 30.44
    for ses_name, ses in (("London 2:00-5:00", E.LONDON), ("NY 9:30-11:00", E.NYOPEN)):
        cfg = replace(E.Config(), sessions=ses)
        _, tr = E.run(m, cfg)
        tr["t"] = pd.to_datetime(tr["t"])
        times = tr["t"].astype("int64").to_numpy()
        all_rows, keep = [], None
        for c in CRT_CONFIGS:
            ev = crt_events(m, c)
            iv = bias_intervals(m, c, ev)
            d, age = bias_at(iv, times)
            df, trc = compare(tr, d, months, c.name)
            all_rows.append(df)
            if c is CRT_CONFIGS[0]:
                keep = trc.assign(age=age)
                n_ev = len(ev)
                cover = (iv[:, 1] - iv[:, 0]).sum() / (m.t[-1] - m.t[0])
        print(f"\n=== NQ · {ses_name} · modo A estricto · {len(tr)} señales B+ · CRT por defecto: {n_ev} eventos, "
              f"sesgo vigente el {cover:.0%} del tiempo ===")
        res = pd.concat(all_rows)
        print(res.to_string(index=False))
        k = keep
        print("\nCRT por defecto · resultado por antigüedad del sesgo (horas desde la confirmación):")
        k["edad"] = pd.cut(k["age"], [0, 1, 2, 4, 1e9], labels=["<1 h", "1-2 h", "2-4 h", ">4 h"], right=False)
        print(k[k.al != "sin CRT"].groupby(["al", "edad"], observed=True)["r"].agg(["count", "mean", "sum"]).round(2).to_string())
        print("\nCRT por defecto · por dirección del CRT y del setup:")
        print(k.groupby(["crt", "d"])["r"].agg(["count", "mean", "sum"]).round(2).to_string())
        print("\nCRT por defecto · por año (alineadas vs resto):")
        k["año"] = k["t"].dt.year
        print(k.assign(g=np.where(k.al == "alineada", "alineada", "resto")).pivot_table(
            index="g", columns="año", values="r", aggfunc="sum").round(1).to_string())


if __name__ == "__main__":
    main()
