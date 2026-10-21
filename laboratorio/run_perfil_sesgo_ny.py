"""Petición del usuario: ¿el perfil de volumen de la sesión de NY de ayer da un sesgo útil para hoy? NQ 1 min 2018-2026.
Reglas fijadas ANTES de ver resultados:
  Perfil de NY: sesión regular 9:30-16:00 ET (15:30-22:00 Italia; el calendario ET ya absorbe los cambios de hora).
    El volumen de cada minuto se reparte por igual entre su mínimo y su máximo en tramos de 1 punto.
    POC = tramo con más volumen; área de valor (VAH/VAL) = 70 % del volumen, creciendo desde el POC tramo a tramo
    hacia el lado con más volumen. Solo días completos (sin medias jornadas) y del mismo contrato que los dos días previos.
  Clasificación de cada día (con información conocida antes de abrir):
    A. Cierre de ayer (16:00) respecto al área de valor de ayer: encima (+1) / dentro (0) / debajo (−1).
    B. Apertura de hoy (9:30) respecto al área de valor de ayer: encima (+1) / dentro (0) / debajo (−1).
    C. Migración del valor: POC de ayer frente al de anteayer: sube (+1) / igual (0) / baja (−1).
    Sesgo = signo(A + B + C). "Alineado" = los tres en el mismo sentido (suma ±3).
  Resultados medidos hoy:
    1. ¿Cerró a favor del sesgo? signo(cierre 16:00 − apertura 9:30) = sesgo. Recorrido en % del precio a favor.
    2. Primer nivel de ayer tocado (VAH, POC o VAL; un minuto toca un nivel si su rango lo contiene).
    3. Aperturas en un borde (fuera del área, o dentro a menos del 10 % de su ancho de un borde):
       ACEPTA = primero dos cierres seguidos de 30 min dentro del área y más allá de esa franja del 10 %;
       RECHAZA = primero dos cierres seguidos de 30 min fuera del área por el lado de ese borde; si no, INDECISO.
       Tras aceptar: ¿toca el borde opuesto (regla del 80 %)? Tras rechazar: ¿cierra el día fuera por ese lado?
  Referencia al azar: el mismo cálculo con los sesgos barajados entre días (10.000 permutaciones) y las tasas de
  todos los días sin condición. Desglose por desarrollo / validación / prueba para ver si es estable."""
import numpy as np
import pandas as pd

from data.loaders import sessions
from orb_retest.config import BASELINE
from orb_retest.pipeline import label
from validation.runner import new_experiment, write_manifest

RNG = np.random.default_rng(20261021)


def perfil(m, close_min):
    x = m[:close_min]
    ok = ~np.isnan(x[:, 0])
    H, L, V = x[ok, 1], x[ok, 2], np.nan_to_num(x[ok, 4])
    lo = int(np.floor(L.min()))
    a = np.floor(L).astype(int) - lo
    b = np.ceil(H).astype(int) - lo
    n = b - a + 1
    diff = np.zeros(b.max() + 2)
    np.add.at(diff, a, V / n)
    np.add.at(diff, b + 1, -V / n)
    vol = np.cumsum(diff)[:-1]
    poc = int(np.argmax(vol))
    tot, acc, i, j = vol.sum(), vol[poc], poc, poc
    while acc < 0.7 * tot and (i > 0 or j < len(vol) - 1):
        up = vol[j + 1] if j < len(vol) - 1 else -1
        dn = vol[i - 1] if i > 0 else -1
        if up >= dn:
            j += 1
            acc += up
        else:
            i -= 1
            acc += dn
    return dict(POC=lo + poc + 0.5, VAH=lo + j + 1.0, VAL=lo + i + 0.0)


def pos(x, p):
    return 1 if x > p["VAH"] else (-1 if x < p["VAL"] else 0)


def first_touch(m, close_min, p):
    names = ("VAH", "POC", "VAL")
    for k in range(close_min):
        if np.isnan(m[k, 0]):
            continue
        hit = [nm for nm in names if m[k, 2] <= p[nm] <= m[k, 1]]
        if len(hit) == 1:
            return hit[0]
        if len(hit) > 1:
            return "varios_mismo_minuto"
    return "ninguno"


def borde(m, close_min, p, o):
    w = p["VAH"] - p["VAL"]
    if w <= 0:
        return None
    if o > p["VAH"] - 0.1 * w:
        side = 1
    elif o < p["VAL"] + 0.1 * w:
        side = -1
    else:
        return None
    inner_hi, inner_lo = p["VAH"] - 0.1 * w, p["VAL"] + 0.1 * w
    closes, ks = [], []
    for k0 in range(0, close_min, 30):
        seg = m[k0:k0 + 30, 3]
        seg = seg[~np.isnan(seg)]
        if len(seg):
            closes.append(seg[-1])
            ks.append(k0 + 30)
    res, t = "indeciso", None
    for c0, c1, k in zip(closes, closes[1:], ks[1:]):
        inside = all(inner_lo < c < inner_hi for c in (c0, c1))
        outside = all((c > p["VAH"]) if side == 1 else (c < p["VAL"]) for c in (c0, c1))
        if inside:
            res, t = "acepta", k
            break
        if outside:
            res, t = "rechaza", k
            break
    opp = p["VAL"] if side == 1 else p["VAH"]
    traverse = False if res == "acepta" else None
    if res == "acepta" and np.any(~np.isnan(m[t:close_min, 0])):
        seg = m[t:close_min]
        traverse = bool(np.nanmin(seg[:, 2]) <= opp) if side == 1 else bool(np.nanmax(seg[:, 1]) >= opp)
    seg = m[:close_min]
    any_opp = bool(np.nanmin(seg[:, 2]) <= opp) if side == 1 else bool(np.nanmax(seg[:, 1]) >= opp)
    return dict(borde="VAH" if side == 1 else "VAL", fuera=bool(o > p["VAH"] or o < p["VAL"]), resultado=res,
                cruza_al_otro_borde=traverse, toca_otro_borde_en_el_dia=any_opp, k_senal=t,
                px_senal=(m[t - 30:t, 3][~np.isnan(m[t - 30:t, 3])][-1] if t else np.nan))


def build():
    S = [s for s in sessions()]
    rows, prof = [], {}
    for idx, s in enumerate(S):
        if s.close_min < 390 or np.isnan(s.m[:390, 0]).all():
            continue
        prof[idx] = perfil(s.m, s.close_min)
    for idx in range(2, len(S)):
        s, y, z = S[idx], S[idx - 1], S[idx - 2]
        if idx not in prof or idx - 1 not in prof or idx - 2 not in prof:
            continue
        if not (s.instrument_id == y.instrument_id == z.instrument_id):
            continue
        m = s.m
        okk = np.nonzero(~np.isnan(m[:390, 0]))[0]
        if len(okk) == 0 or okk[0] > 5:
            continue
        o = m[okk[0], 0]
        c = m[okk[-1], 3]
        yk = np.nonzero(~np.isnan(y.m[:390, 3]))[0]
        yc = y.m[yk[-1], 3]
        p, pz = prof[idx - 1], prof[idx - 2]
        A, B = pos(yc, p), pos(o, p)
        C = int(np.sign(p["POC"] - pz["POC"]))
        score = A + B + C
        r = dict(date=s.date, A=A, B=B, C=C, score=score, sesgo=int(np.sign(score)), apertura=o, cierre=c,
                 ret_pct=(c - o) / o * 100, vah=p["VAH"], val=p["VAL"], poc=p["POC"],
                 primer_toque=first_touch(m, 390, p))
        bd = borde(m, 390, p, o)
        if bd:
            bd["cierre_fuera_lado"] = bool(c > p["VAH"]) if bd["borde"] == "VAH" else bool(c < p["VAL"])
            r.update(bd)
        rows.append(r)
    d = pd.DataFrame(rows)
    d["particion"] = label(d.date, BASELINE)
    return d


def favor_table(d):
    d = d.copy()
    d["dir"] = np.sign(d.ret_pct)
    out = []
    groups = [("sesgo alcista (suma > 0)", d.sesgo == 1), ("sesgo bajista (suma < 0)", d.sesgo == -1),
              ("sin sesgo (suma = 0)", d.sesgo == 0), ("alineado alcista (+3)", d.score == 3),
              ("alineado bajista (−3)", d.score == -3)]
    for nm, mask in groups:
        x = d[mask]
        s = 1 if "alcista" in nm else (-1 if "bajista" in nm else 0)
        row = dict(grupo=nm, dias=len(x), p_cierra_arriba=(x.dir > 0).mean())
        if s:
            row["p_a_favor"] = (x.dir == s).mean()
            row["recorrido_medio_a_favor_pct"] = (s * x.ret_pct).mean()
        for p in ("desarrollo", "validacion", "prueba"):
            xp = x[x.particion == p]
            row[f"{p}_p_a_favor"] = (xp.dir == s).mean() if s and len(xp) else np.nan
            row[f"{p}_dias"] = len(xp)
        out.append(row)
    return pd.DataFrame(out)


def perm_test(d, n=10000):
    x = d[d.sesgo != 0]
    real = (np.sign(x.ret_pct).to_numpy() == x.sesgo.to_numpy()).mean()
    dirs, b = np.sign(x.ret_pct).to_numpy(), x.sesgo.to_numpy()
    sims = np.array([(dirs == RNG.permutation(b)).mean() for _ in range(n)])
    return real, sims.mean(), (sims >= real).mean()


def main():
    d = build()
    exp = new_experiment("perfil_sesgo_ny")
    d.to_csv(exp / "dias.csv.gz", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(f"días válidos: {len(d)}  ({d.date.min().date()} → {d.date.max().date()})")
    print("\nTodos los días: P(cierre > apertura) =", round((d.ret_pct > 0).mean(), 3))
    ft = favor_table(d)
    ft.to_csv(exp / "a_favor.csv", index=False)
    print("\n1. ¿Cierra a favor del sesgo?\n", ft.round(3).to_string(index=False))
    real, rnd, pv = perm_test(d)
    print(f"\n   Con sesgo (≠0): a favor {real:.3f} · al azar (sesgos barajados) {rnd:.3f} · p = {pv:.4f}")
    by = d.groupby(["A", "B", "C"]).apply(lambda x: pd.Series(dict(dias=len(x), p_arriba=(x.ret_pct > 0).mean(),
                                                                    ret_medio_pct=x.ret_pct.mean())))
    by.to_csv(exp / "por_combinacion.csv")
    print("\n   Por combinación (A cierre ayer, B apertura, C POC):\n", by.round(3).to_string())
    for nm, col in (("A · cierre de ayer", "A"), ("B · apertura de hoy", "B"), ("C · migración del POC", "C")):
        g = d.groupby(col).ret_pct.agg(dias="size", p_arriba=lambda r: (r > 0).mean(), ret_medio_pct="mean")
        print(f"\n   {nm}:\n", g.round(3).to_string())
    inside = d[d.B == 0]
    t2 = pd.crosstab(inside.sesgo, inside.primer_toque, normalize="index").round(3)
    t2["dias"] = inside.groupby("sesgo").size()
    t2.to_csv(exp / "primer_toque_dentro.csv")
    print("\n2. Primer nivel de ayer tocado (aperturas DENTRO del área), por sesgo:\n", t2.to_string())
    print("   Todas las aperturas dentro:", inside.primer_toque.value_counts(normalize=True).round(3).to_dict())
    bd = d[d.resultado.notna()] if "resultado" in d else d.iloc[0:0]
    t3 = bd.groupby(["fuera", "borde", "resultado"]).agg(
        dias=("date", "size"), cruza_al_otro_borde=("cruza_al_otro_borde", "mean"),
        cierre_fuera_lado=("cierre_fuera_lado", "mean")).round(3)
    t3.to_csv(exp / "bordes.csv")
    print("\n3. Aperturas en un borde (fuera=True: abrió fuera del área):\n", t3.to_string())
    acc = bd[bd.resultado == "acepta"]
    print("   Tras aceptar, cruza al otro borde:", round(acc.cruza_al_otro_borde.mean(), 3), f"({len(acc)} días)")
    for p in ("desarrollo", "validacion", "prueba"):
        a = acc[acc.particion == p]
        print(f"     {p}: {a.cruza_al_otro_borde.mean():.3f} ({len(a)} días)")
    print("   Referencia: todas las aperturas en borde, tocan el otro borde en el día:",
          round(bd.toca_otro_borde_en_el_dia.mean(), 3), f"({len(bd)} días)")
    rej = bd[bd.resultado == "rechaza"]
    print("   Tras rechazar, cierra fuera por ese lado:", round(rej.cierre_fuera_lado.mean(), 3), f"({len(rej)} días)")
    print("   Referencia: días que abren fuera, cierran fuera por ese lado:",
          round(bd[bd.fuera].cierre_fuera_lado.mean(), 3), f"({int(bd.fuera.sum())} días)")
    # lo operable: desde el cierre de la vela de 30 min que confirma hasta el cierre del día, en el sentido de la señal
    sig = bd[bd.resultado.isin(["acepta", "rechaza"])].copy()
    sgn = np.where(sig.borde == "VAH", 1, -1) * np.where(sig.resultado == "rechaza", 1, -1)
    sig["ret_tras_senal_pct"] = sgn * (sig.cierre - sig.px_senal) / sig.px_senal * 100
    t4 = sig.groupby(["resultado", "particion"]).ret_tras_senal_pct.agg(
        dias="size", p_a_favor=lambda r: (r > 0).mean(), medio_pct="mean").round(3)
    t4.to_csv(exp / "tras_senal.csv")
    print("\n3b. Desde la confirmación (cierre de 30 min) hasta el cierre del día, a favor de la señal:\n", t4.to_string())
    write_manifest(exp, experimento="perfil NY de ayer → sesgo de hoy", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
