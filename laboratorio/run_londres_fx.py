"""Petición del usuario ("me gusta operar Londres" → opción c):
PARTE A · Londres (9:00 Italia) en NQ, oro, EUR/USD y GBP/USD: entrada en la ruptura frente a entrada en el PULLBACK
          (orden límite en el nivel roto tras la ruptura; se cancela si antes llega al objetivo). Velas de 5 min 8:55
          y 9:00 Italia, 15 min, 30 min y 1 h desde las 9:00 Italia (2:55/3:00 ET). Stop: otro lado del rango o mitad
          del rango. Objetivo: 0,75 o 1 rango desde el nivel roto.
PARTE B · Estudio completo (mismas fases que el NQ y el oro) en EUR/USD y GBP/USD: gira o continúa en velas de
          5/15/30/60/240 min de 0:00 a 14:00 ET; estrategia a favor (+1 rango) en las candidatas (>= 8/9 años, dif >= 5);
          objetivos 0,5/0,75/1 en las velas de 15 min.
Reglas fijadas antes de ver resultados. Selección: dev>0 y val>0 (coste base), n_val >= 30. Costes M6E/M6B provisionales.
Datos FX comprados con autorización del usuario (≈ 21,55 USD). Rejilla ET; 3:00 ET = 9:00 Italia salvo ~3 semanas al año."""
import itertools

import pandas as pd

from execution_costs.costs import fut
from rangos_lib import lab, load_days, race, run_strategy, setup, stats
from validation.runner import new_experiment, periods, write_manifest

SYMS = ["MNQ", "MGC", "M6E", "M6B"]
LONDON = [(5, 175), (5, 180), (15, 180), (30, 180), (60, 180)]
TFS = {5: list(range(0, 841, 5)), 15: list(range(0, 841, 15)), 30: list(range(0, 841, 30)),
       60: list(range(0, 781, 60)), 240: [120, 360, 600]}


def main():
    per = periods("intradia", include_test=True)
    exp = new_experiment("londres_fx")
    pd.set_option("display.width", 300, "display.max_rows", 500, "display.max_colwidth", 60)
    days = {}
    for s in SYMS:
        days[s], excl = load_days(s)
        print(f"{s}: {len(days[s])} días · excluidos {excl}", flush=True)

    # PARTE A
    ra = []
    for s in SYMS:
        cb, ca = fut(s, "base"), fut(s, "alto")
        for (dur, a), mode, sm, frac in itertools.product(LONDON, ("favor", "pullback"), ("opuesto", "mitad"), (0.75, 1.0)):
            for cn, c in (("base", cb), ("alto", ca)):
                t = run_strategy(days[s], dur, a, c, mode, frac, sm)
                ra.append(dict(mercado=s, ventana=lab(dur, a), entrada=mode, stop=sm, objetivo=frac, coste=cn,
                               **stats(t, per, c)))
        print("A", s, "ok", flush=True)
    ra = pd.DataFrame(ra)
    ra["pasa"] = (ra.dev > 0) & (ra.val > 0) & (ra.n_val >= 30)
    ra.to_csv(exp / "parteA_londres.csv", index=False)
    b = ra[ra.coste == "base"]
    print("\n=== PARTE A · Londres: resumen por mercado y entrada (coste base) ===")
    print(b.groupby(["mercado", "entrada"]).agg(variantes=("n", "size"), pasan=("pasa", "sum"),
                                                tres_pos=("prueba", lambda x: int(((x > 0) & b.loc[x.index, "pasa"]).sum())),
                                                esperanza_media=("neto_año", "mean"), R_bruto_medio=("R_bruto", "mean"),
                                                acierto_medio=("acierto", "mean")).round(3).to_string())
    print("\nVariantes que pasan la regla (base):")
    print(b[b.pasa].drop(columns=["coste"]).round(2).to_string(index=False))
    print("\nMejor variante por mercado y entrada (por neto/año, base):")
    print(b.loc[b.groupby(["mercado", "entrada"]).neto_año.idxmax()].drop(columns=["coste"]).round(2).to_string(index=False))

    # PARTE B
    for s in ("M6E", "M6B"):
        D, cb = days[s], fut(s, "base")
        rows = []
        for dur, starts in TFS.items():
            for a in starts:
                for date, m in D:
                    st = setup(m, a, dur, cb.tick)
                    if st is None or st == "mismo":
                        continue
                    rows.append(dict(tf=dur, a=a, date=date, res=race(m, st)))
        df = pd.DataFrame(rows)
        out = []
        for (dur, a), g in df.groupby(["tf", "a"]):
            y = g.groupby(g.date.dt.year).res.agg(lambda x: (x == "continua").mean() - (x == "gira").mean())
            out.append(dict(tf=dur, a=a, ventana=lab(dur, a), dias=len(g), continua=(g.res == "continua").mean() * 100,
                            gira=(g.res == "gira").mean() * 100,
                            dif=((g.res == "continua").mean() - (g.res == "gira").mean()) * 100,
                            años_c=int((y > 0).sum()), años_g=int((y < 0).sum())))
        o = pd.DataFrame(out)
        o.to_csv(exp / f"parteB_{s}_fase1.csv", index=False)
        print(f"\n=== PARTE B · {s} · fase 1 ===")
        print(o.groupby("tf").agg(ventanas=("a", "size"), dif_media=("dif", "mean"), dif_max=("dif", "max"),
                                  dif_min=("dif", "min")).round(1).to_string())
        print("Top 12 continuación:")
        print(o.sort_values("dif", ascending=False).head(12).drop(columns=["tf", "a"]).round(1).to_string(index=False))
        print("Top 6 giro:")
        print(o.sort_values("dif").head(6).drop(columns=["tf", "a"]).round(1).to_string(index=False))
        cand = pd.concat([o[(o.años_c >= 8) & (o.dif >= 5)].assign(modo="favor"),
                          o[(o.años_g >= 8) & (o.dif <= -5)].assign(modo="contra")])
        r2 = []
        for _, cr in cand.iterrows():
            for cn in ("base", "alto"):
                c = fut(s, cn)
                t = run_strategy(D, int(cr.tf), int(cr.a), c, cr.modo, 1.0)
                r2.append(dict(ventana=cr.ventana, tf=cr.tf, a=cr.a, modo=cr.modo, coste=cn, **stats(t, per, c)))
        r2 = pd.DataFrame(r2)
        print(f"Fase 2 · {len(cand)} candidatas")
        if len(r2):
            r2["pasa"] = (r2.dev > 0) & (r2.val > 0) & (r2.n_val >= 30)
            r2.to_csv(exp / f"parteB_{s}_fase2.csv", index=False)
            bb = r2[r2.coste == "base"]
            print(f"  pasan: {int(bb.pasa.sum())} · R bruto medio {bb.R_bruto.mean():.3f} · neto/año medio {bb.neto_año.mean():.0f}")
            print(bb.sort_values("neto_año", ascending=False).head(8).drop(columns=["tf", "a", "coste"]).round(2).to_string(index=False))
            if bb.pasa.any():
                print(r2[r2.ventana.isin(bb[bb.pasa].ventana)].drop(columns=["tf", "a"]).round(2).to_string(index=False))
        r3 = []
        for a, frac in itertools.product(TFS[15], (0.5, 0.75, 1.0)):
            c = fut(s, "base")
            t = run_strategy(D, 15, a, c, "favor", frac)
            r3.append(dict(ventana=lab(15, a), objetivo=frac, **stats(t, per, c)))
        r3 = pd.DataFrame(r3)
        r3["pasa"] = (r3.dev > 0) & (r3.val > 0) & (r3.n_val >= 30)
        r3.to_csv(exp / f"parteB_{s}_fase3.csv", index=False)
        print(f"Fase 3 · velas de 15 min × 3 objetivos: pasan {int(r3.pasa.sum())}, con prueba > 0: "
              f"{int((r3.pasa & (r3.prueba > 0)).sum())} · neto/año medio {r3.neto_año.mean():.0f}")
        if r3.pasa.any():
            print(r3[r3.pasa].round(2).to_string(index=False))
    write_manifest(exp, experimento="Londres (ruptura vs pullback) en 4 mercados + estudio completo EUR/USD y GBP/USD",
                   reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
