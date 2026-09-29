"""Backtest de GOLD_SWING_SIMPLE_v1.0 (GC como sustituto de XAUUSD). Reglas: edges/gold_swing_simple.md.

1) Auditoría de look-ahead (si falla, se detiene).  2) v1.0 exacta en DESARROLLO, escenarios A/B/C.
3) Criterios registrados: solo si se cumplen se ejecuta el fuera de muestra.  4) Sensibilidad (diagnóstico, desarrollo).
Uso: python -m src.report.gold_swing   →   reports/GOLD_SWING_SIMPLE_v1.0/ (nunca se sobrescribe).
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.data.datos import inicio_fuera_de_muestra, velas_1m  # noqa: E402
from src.engine.lookahead import comprobar  # noqa: E402
from src.horas import ROMA, sesion_cme  # noqa: E402
from src.metrics.metricas import racha  # noqa: E402
from src.strategies import gold_swing_simple as g  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent.parent
MUESTRA_MIN, GRUPO_MIN = 100, 30
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
SENSIBILIDAD = {
    "v1.0 (oficial)": {},
    "swing 3 velas": {"swing_n": 3},
    "TP 1,5R": {"tp_r": 1.5},
    "TP 2,5R": {"tp_r": 2.5},
    "entrada borde cercano": {"entrada": "cercano"},
    "entrada borde lejano": {"entrada": "lejano"},
    "buffer 0": {"buffer_atr": 0.0},
}


def periodos():
    m1 = velas_1m("GC")
    ses = sesion_cme(m1.index)
    corte = inicio_fuera_de_muestra("GC").date()
    return m1[ses < corte], m1[ses >= corte]


def metricas(ops: pd.DataFrame, saldo0: float) -> dict:
    n = len(ops)
    if n == 0:
        return {"trades": 0, "sample_flag": "INSUFFICIENT_SAMPLE"}
    neto, r = ops.neto_usd, ops.r
    gan, per = neto[neto > 0], neto[neto < 0]
    eq = saldo0 + neto.cumsum().to_numpy()
    pico = np.maximum.accumulate(np.r_[saldo0, eq])[1:]
    dd = eq - pico
    i = int(dd.argmin())
    eq_r = r.cumsum().to_numpy()
    dd_r = eq_r - np.maximum.accumulate(np.r_[0.0, eq_r])[1:]
    t = r.mean() / r.std() * np.sqrt(n) if n > 1 and r.std() > 0 else np.nan
    return {
        "trades": n, "winners": int((neto > 0).sum()), "losers": int((neto < 0).sum()),
        "win_rate_%": round((neto > 0).mean() * 100, 1),
        "profit_factor": round(gan.sum() / -per.sum(), 3) if per.sum() < 0 else np.inf,
        "expectancy_R": round(r.mean(), 4), "expectancy_R_gross": round(ops.r_bruto.mean(), 4),
        "expectancy_$": round(neto.mean(), 2), "net_$": round(neto.sum(), 0),
        "avg_win_$": round(gan.mean(), 2) if len(gan) else 0.0, "avg_loss_$": round(per.mean(), 2) if len(per) else 0.0,
        "avg_win_R": round(r[neto > 0].mean(), 3) if len(gan) else 0.0,
        "avg_loss_R": round(r[neto < 0].mean(), 3) if len(per) else 0.0,
        "t_stat_R": round(t, 2), "median_R": round(r.median(), 3), "std_R": round(r.std(), 3),
        "max_dd_$": round(dd.min(), 0), "max_dd_%": round(dd[i] / pico[i] * 100, 2), "max_dd_R": round(dd_r.min(), 2),
        "max_consec_losses": racha(neto < 0), "max_consec_wins": racha(neto > 0),
        "avg_duration_h": round(ops.duracion_h.mean(), 1), "median_duration_h": round(ops.duracion_h.median(), 1),
        "max_duration_h": round(ops.duracion_h.max(), 1),
        "avg_MAE_R": round(ops.mae_r.mean(), 3), "avg_MFE_R": round(ops.mfe_r.mean(), 3),
        "avg_MAE_R_winners": round(ops.mae_r[neto > 0].mean(), 3) if len(gan) else np.nan,
        "avg_MFE_R_losers": round(ops.mfe_r[neto < 0].mean(), 3) if len(per) else np.nan,
        "avg_risk_pts": round(ops.riesgo_pts.mean(), 2), "avg_ounces": round(ops.onzas.mean(), 1),
        "trades_crossing_roll": int(ops.cruza_roll.sum()),
        "final_balance_$": round(eq[-1], 0),
        "sample_flag": "OK" if n >= MUESTRA_MIN else "INSUFFICIENT_SAMPLE",
    }


CORTAS = ["trades", "win_rate_%", "profit_factor", "expectancy_R", "t_stat_R", "net_$"]


def agrupar(ops, clave, nombre, saldo0):
    filas = []
    for k, grp in ops.groupby(clave):
        m = metricas(grp, saldo0)
        filas.append({nombre: k, **{c: m.get(c) for c in CORTAS},
                      "sample_flag": "OK" if m["trades"] >= GRUPO_MIN else "INSUFFICIENT_SAMPLE"})
    return pd.DataFrame(filas)


def embudo(setups: pd.DataFrame, ops: pd.DataFrame) -> pd.DataFrame:
    al = setups[setups.estado != "NOT_ALIGNED"]
    libres = al[al.estado != "TRADE_OPEN"]
    col = lambda c: libres[c].fillna(False).astype(bool) if c in libres else pd.Series(False, index=libres.index)  # noqa: E731
    pasos = [
        ("0. Barridos 1H detectados (los dos lados, sin filtro)", len(setups)),
        ("1. Barridos a favor de la dirección 4H", len(al)),
        ("   ...descartados por operación abierta", int((al.estado == "TRADE_OPEN").sum())),
        ("   ...evaluables", len(libres)),
        ("2. Con confirmación 1H", int(col("confirmado").sum())),
        ("3. Con FVG", int(col("fvg").sum())),
        ("4. FVG con retest del precio de entrada (24 velas 1H)", int(col("retest").sum())),
        ("5. Entradas ejecutadas", len(ops)),
        ("6. Ganadoras", int((ops.neto_usd > 0).sum()) if len(ops) else 0),
        ("7. Perdedoras", int((ops.neto_usd < 0).sum()) if len(ops) else 0),
    ]
    return pd.DataFrame(pasos, columns=["paso", "n"])


# -------------------------------------------------------------------------------------- look-ahead
def auditoria(m1: pd.DataFrame, cfg: g.Config, prep: dict, ops: pd.DataFrame) -> list[tuple]:
    res = []
    corte = pd.Timestamp(inicio_fuera_de_muestra("GC")).tz_localize("America/New_York") - pd.Timedelta(hours=6)
    res.append(("Datos: nada del fuera de muestra", "OK" if m1.index.max() < corte.tz_convert("UTC") else "FALLO",
                f"última vela {m1.index.max()} (corte: sesión {inicio_fuera_de_muestra('GC').date()})"))
    v1, v4, n = prep["v1"], prep["v4"], cfg.swing_n
    fallos = {k: 0 for k in ("swing", "dir4", "barrido", "orden", "fvg", "stop")}
    for _, op in ops.iterrows():
        # Swing: confirmado (cierre de la vela i+n) antes de que empiece la vela del barrido
        i = v1.index.get_loc(op.t_swing)
        b = v1.index.get_loc(op.t_barrido_fin - pd.Timedelta(hours=1))
        if not i + n <= b - 1:
            fallos["swing"] += 1
        # Dirección 4H recalculada SOLO con velas 4H cerradas en el momento del barrido
        v4c = v4[v4.fin <= op.t_barrido_fin]
        d_trunc = g.direccion_4h(v4c, n)[-1] if len(v4c) else 0
        if d_trunc != op.direccion:
            fallos["dir4"] += 1
        # Barrido recalculado con velas 1H hasta la del barrido (incluida): tiene que aparecer como último evento
        ev = g.barridos(v1.iloc[: b + 1], n)
        if not any(e["b"] == b and e["d"] == op.direccion and e["nivel"] == op.nivel_swing for e in ev):
            fallos["barrido"] += 1
        # Orden temporal: barrido < confirmación < FVG <= entrada
        if not (op.t_barrido_fin < op.t_confirmacion_fin < op.t_fvg <= op.t_entrada):
            fallos["orden"] += 1
        # FVG con velas b, b+1, b+2 ya cerradas; stop con la vela del barrido y el ATR de ese cierre
        vb, v3 = v1.iloc[b], v1.iloc[b + 2]
        zona = (vb.high, v3.low) if op.direccion == 1 else (v3.high, vb.low)
        if not np.allclose(zona, (op.fvg_bajo, op.fvg_alto)):
            fallos["fvg"] += 1
        atr_trunc = g.atr_wilder(v1.iloc[: b + 1], cfg.atr_n)[-1]
        sl = vb.low - cfg.buffer_atr * atr_trunc if op.direccion == 1 else vb.high + cfg.buffer_atr * atr_trunc
        if not np.isclose(sl, op.sl):
            fallos["stop"] += 1
    textos = {
        "swing": "Swing 1H confirmado (cierre de i+2) antes de empezar la vela del barrido",
        "dir4": "Dirección 4H recalculada solo con velas 4H cerradas al cierre del barrido = la usada",
        "barrido": "Barrido recalculado con datos cortados en la vela del barrido = el usado",
        "orden": "Orden temporal: barrido < confirmación < FVG <= entrada en 15m",
        "fvg": "FVG con las velas 1H b, b+1 y b+2 ya cerradas",
        "stop": "Stop con la vela del barrido y el ATR(14) calculado solo hasta ese cierre",
    }
    for k, txt in textos.items():
        res.append((txt, "OK" if fallos[k] == 0 else "FALLO", f"{len(ops)} operaciones; fallos: {fallos[k]}"))
    sabados = [pd.Timestamp(x, tz="UTC") for x in ("2016-06-11", "2017-09-16", "2019-01-12", "2020-05-16",
                                                    "2021-08-14", "2022-10-15")]
    probs = comprobar(lambda v: g.senales(v, cfg), m1, sabados)
    res.append(("Truncamiento global (6 cortes en sábado): entradas anteriores idénticas",
                "OK" if not probs else "FALLO", "; ".join(probs) or "sin diferencias"))
    res.append(("Entrada 15m", "OK (por construcción y pruebas)",
                "orden activa desde el cierre de la vela 3; solo velas de 15m que empiezan después; "
                "tests/test_gold_swing_simple.py"))
    return res


# ------------------------------------------------------------------------------------------ gráficos
COLORES = {"A": "#8a8f98", "B": "#2a78d6", "C": "#d9822b"}


def graficos(curvas: dict, salida: Path, saldo0: float, version: str = g.VERSION):
    fig, ax = plt.subplots(figsize=(9, 4))
    for esc, ops in curvas.items():
        if len(ops):
            ax.plot(ops.t_salida, saldo0 + ops.neto_usd.cumsum(), lw=2, color=COLORES[esc], label=f"Escenario {esc}", drawstyle="steps-post")
    ax.axhline(saldo0, color="#bbb", lw=1)
    ax.set_title(f"{version}: saldo (desarrollo)", loc="left")
    ax.legend(frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#eee")
    fig.tight_layout()
    fig.savefig(salida / "equity_curve.png", dpi=120)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 3))
    for esc, ops in curvas.items():
        if len(ops):
            eq = saldo0 + ops.neto_usd.cumsum()
            pico = np.maximum.accumulate(np.r_[saldo0, eq.to_numpy()])[1:]
            ax.plot(ops.t_salida, (eq - pico) / pico * 100, lw=2, color=COLORES[esc], label=f"Escenario {esc}", drawstyle="steps-post")
    ax.set_title("Drawdown (% del máximo)", loc="left")
    ax.legend(frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#eee")
    fig.tight_layout()
    fig.savefig(salida / "drawdown_curve.png", dpi=120)
    plt.close(fig)


# -------------------------------------------------------------------------------------------- main
def carpeta() -> Path:
    base = RAIZ / "reports" / g.VERSION
    k = 2
    out = base
    while out.exists():
        out = RAIZ / "reports" / f"{g.VERSION}_v{k}"
        k += 1
    return out


def md(df, index=False):
    return df.to_markdown(index=index)


def ejecutar():
    dev, oos = periodos()
    base = g.Config()
    preps = {}

    def prep(cfg):
        if cfg.swing_n not in preps:
            preps[cfg.swing_n] = g.preparar(dev, cfg)
        return preps[cfg.swing_n]

    salida = carpeta()
    salida.mkdir(parents=True)
    ops_b, set_b = g.backtest(dev, base, prep(base))
    audit = auditoria(dev, base, prep(base), ops_b)
    tabla_audit = md(pd.DataFrame(audit, columns=["punto", "resultado", "detalle"]))
    if any(r[1] == "FALLO" for r in audit):
        (salida / "diagnostics.md").write_text("# LOOK-AHEAD DETECTADO — BACKTEST DETENIDO\n\n" + tabla_audit)
        print("LOOK-AHEAD: detenido")
        sys.exit(1)

    resumen, trades, rechazos, anual, lados, dias, horas, embudos, curvas = [], [], [], [], [], [], [], {}, {}
    for esc, costes in g.ESCENARIOS.items():
        cfg = base.con(costes=costes)
        ops, st = g.backtest(dev, cfg, prep(cfg))
        m = metricas(ops, cfg.saldo_inicial)
        resumen.append({"scenario": esc, **m})
        curvas[esc] = ops
        embudos[esc] = embudo(st, ops)
        if len(ops):
            o = ops.assign(scenario=esc)
            roma = pd.DatetimeIndex(o.t_entrada).tz_convert(ROMA)
            o["anio"], o["hora_roma"], o["dia"] = roma.year, roma.hour, [DIAS[d] for d in roma.weekday]
            trades.append(o)
            anual.append(agrupar(o, "anio", "year", cfg.saldo_inicial).assign(scenario=esc))
            lados.append(agrupar(o, "lado", "side", cfg.saldo_inicial).assign(scenario=esc))
            dias.append(agrupar(o, "dia", "weekday", cfg.saldo_inicial).assign(scenario=esc))
            horas.append(agrupar(o, "hora_roma", "entry_hour_rome", cfg.saldo_inicial).assign(scenario=esc))
        if esc == "B":
            rechazos = st[~st.estado.isin(["ENTERED", "NOT_ALIGNED"])]
    resumen = pd.DataFrame(resumen)
    trades = pd.concat(trades) if trades else pd.DataFrame()
    b = resumen.set_index("scenario").loc["B"]
    pasa = (b.trades >= MUESTRA_MIN and b.profit_factor > 1 and b.expectancy_R > 0 and b.t_stat_R >= 2)

    # Sensibilidad (diagnóstico, solo desarrollo)
    sens = []
    for nombre, cambios in SENSIBILIDAD.items():
        for esc, costes in g.ESCENARIOS.items():
            cfg = base.con(**cambios, costes=costes)
            ops, _ = g.backtest(dev, cfg, prep(cfg))
            m = metricas(ops, cfg.saldo_inicial)
            sens.append({"variant": nombre, "scenario": esc, **{k: m.get(k) for k in
                         ["trades", "win_rate_%", "profit_factor", "expectancy_R", "t_stat_R", "net_$", "max_dd_%",
                          "sample_flag"]}})
    sens = pd.DataFrame(sens)

    # Fuera de muestra: SOLO si el desarrollo cumple los criterios registrados
    oos_txt = "NO EJECUTADO: el desarrollo no cumple los criterios registrados."
    if pasa:
        cfg = base
        ops_o, _ = g.backtest(oos, cfg)
        pd.DataFrame([{"scenario": "B", **metricas(ops_o, cfg.saldo_inicial)}]).to_csv(salida / "oos_summary.csv",
                                                                                         index=False)
        oos_txt = "Ejecutado: ver oos_summary.csv"

    # Archivos
    cols = ["scenario", "t_entrada", "t_salida", "lado", "entrada", "sl", "tp", "salida", "resultado", "r", "r_bruto",
            "neto_usd", "bruto_usd", "costes_usd", "onzas", "riesgo_pts", "riesgo_usd", "saldo_antes", "duracion_h",
            "mae_r", "mfe_r", "t_swing", "nivel_swing", "precio_barrido", "t_barrido_fin", "t_confirmacion_fin",
            "t_fvg", "fvg_alto", "fvg_bajo", "fvg_mitad", "atr_1h", "cruza_roll", "ajuste_roll", "entrada_real",
            "sl_real", "tp_real"]
    if len(trades):
        trades[cols].to_csv(salida / "trades.csv", index=False)
    rechazos.to_csv(salida / "rejected_signals.csv", index=False)
    resumen.to_csv(salida / "summary.csv", index=False)
    pd.concat(anual).to_csv(salida / "yearly.csv", index=False) if anual else None
    pd.concat(lados).to_csv(salida / "long_short.csv", index=False) if lados else None
    pd.concat(dias).to_csv(salida / "weekday.csv", index=False) if dias else None
    pd.concat(horas).to_csv(salida / "entry_hour_rome.csv", index=False) if horas else None
    fun = embudos["B"].rename(columns={"n": "B"})
    fun["A"], fun["C"] = embudos["A"].n, embudos["C"].n
    fun.to_csv(salida / "funnel.csv", index=False)
    sens.to_csv(salida / "sensitivity.csv", index=False)
    graficos(curvas, salida, base.saldo_inicial)
    if len(ops_b):
        (salida / "alerts.txt").write_text("\n\n".join(g.alerta(op) for _, op in ops_b.iterrows()) + "\n")
    motivos = set_b.estado.value_counts().rename_axis("estado").reset_index(name="n")
    (salida / "diagnostics.md").write_text("\n".join([
        f"# Diagnóstico: {g.VERSION} (desarrollo)", "", "## Auditoría de look-ahead", "", tabla_audit, "",
        "## Destino de todos los barridos 1H (escenario B)", "", md(motivos), "",
        "## Fuera de muestra", "", oos_txt, ""]))
    print("Informe en", salida, "| criterios de desarrollo:", "CUMPLE" if pasa else "NO CUMPLE")
    return salida


if __name__ == "__main__":
    ejecutar()
