"""Informes diario y semanal (Markdown). Solo estadística descriptiva: sin rankings, sin ganador, sin recomendaciones
de cambiar nada."""
from __future__ import annotations

import numpy as np
import pandas as pd

N = {"NOISE_ZONE": "Noise Zone", "RSI2": "RSI(2)"}


def _f(x, dec=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:,.{dec}f}".replace(",", " ") if isinstance(x, (int, float, np.floating, np.integer)) else str(x)


def _tabla(df: pd.DataFrame) -> str:
    if df is None or len(df) == 0:
        return "_(sin datos)_\n"
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for k, r in df.iterrows():
        out.append("| " + " | ".join([str(k)] + [_f(v) if isinstance(v, (int, float, np.floating, np.integer)) else str(v) for v in r]) + " |")
    return "\n".join(out) + "\n"


def _dd_actual(x: pd.Series) -> float:
    if len(x) == 0:
        return 0.0
    eq = x.astype(float).cumsum()
    return float(eq.iloc[-1] - max(0.0, eq.max()))


def diario(fecha, estado: dict, cerradas: dict, abiertas: pd.DataFrame, ea: pd.DataFrame, emparejadas: pd.DataFrame,
           deriva: pd.DataFrame, comparaciones: dict, config_hash: str, senal_rsi: dict) -> str:
    f = pd.Timestamp(fecha).date()
    del_dia = {k: v[pd.to_datetime(v.t_salida_ny).dt.date == f] if len(v) else v for k, v in cerradas.items()}
    pnl = {k: float(v["neto_$"].sum()) if len(v) else 0.0 for k, v in del_dia.items()}
    acum = {k: float(v["neto_$"].sum()) if len(v) else 0.0 for k, v in cerradas.items()}
    dd = {k: _dd_actual(v["neto_$"]) if len(v) else 0.0 for k, v in cerradas.items()}
    n_dia = sum(len(v) for v in del_dia.values())
    L = [f"# FORWARD — informe diario {f}", "",
         f"**ESTADO DEL DÍA: {estado['estado']}**" + (f" — {'; '.join(estado['motivos'])}" if estado["motivos"] else ""), "",
         "```text",
         f"DATE:             {f}",
         f"TRADES:           {n_dia} cerradas hoy (Noise Zone {len(del_dia['NOISE_ZONE'])}, RSI(2) {len(del_dia['RSI2'])})",
         f"NET P&L:          {_f(sum(pnl.values()))} $   (suma descriptiva; cada estrategia se evalúa por separado)",
         f"Noise Zone P&L:   {_f(pnl['NOISE_ZONE'])} $",
         f"RSI2 P&L:         {_f(pnl['RSI2'])} $   (realizado; posición abierta aparte)",
         f"CUMULATIVE P&L:   Noise Zone {_f(acum['NOISE_ZONE'])} $ | RSI(2) {_f(acum['RSI2'])} $ (desde el 30/09/2026, 1 MNQ cada una)",
         f"CURRENT DD:       Noise Zone {_f(dd['NOISE_ZONE'])} $ | RSI(2) {_f(dd['RSI2'])} $",
         f"SLIPPAGE:         teórico = el del backtest; EA: {_resumen_slippage(ea, f)}",
         f"EXECUTION ISSUES: {_problemas_ejecucion(emparejadas, estado)}",
         f"DRIFT ALERTS:     {_alertas(deriva)}",
         "```", ""]
    if len(abiertas):
        L += ["**Posiciones abiertas (teórico):**", _tabla(abiertas.set_index("id")[["t_entrada_ny", "precio_real_entrada", "sesiones"]]
                                                               if "sesiones" in abiertas else abiertas.set_index("id")[["t_entrada_ny"]])]
    L += [f"**RSI(2), última sesión cerrada ({senal_rsi['sesion']}):** RSI(2) = {senal_rsi['rsi2']}, sobre SMA200: "
          f"{'sí' if senal_rsi['sobre_sma200'] else 'no'}, señal de entrada para la próxima reapertura: "
          f"{'SÍ' if senal_rsi['senal_de_entrada'] else 'no'}.", ""]
    for k in ("NOISE_ZONE", "RSI2"):
        if len(del_dia[k]):
            cols = [c for c in ("t_entrada_ny", "t_salida_ny", "direccion", "precio_teorico_entrada", "precio_teorico_salida",
                                "neto_$", "mae_pts", "mfe_pts", "motivo", "VOL_ATR") if c in del_dia[k]]
            L += [f"**Operaciones de hoy — {N[k]}:**", _tabla(del_dia[k].set_index("id")[cols])]
    L += ["## BACKTEST VS FORWARD", ""]
    for k, c in comparaciones.items():
        r = c["rango"]
        if r["operaciones_forward"] == 0:
            L.append(f"- **{N[k]}:** sin operaciones forward todavía.")
            continue
        txt = (f"- **{N[k]}:** {r['operaciones_forward']} operaciones; media forward {_f(c['forward']['expectativa_$'])} $ frente a "
               f"backtest {_f(c['backtest']['expectativa_$'])} $")
        if "p5_hist_%" in r:
            txt += (f"; en % del precio: media {r['media_forward_%']:.4f} %, rango histórico p5-p95 para {r['operaciones_forward']} "
                    f"operaciones [{r['p5_hist_%']:.4f}, {r['p95_hist_%']:.4f}] → **{'dentro' if r['dentro_de_rango'] else 'FUERA'}** "
                    f"(en $: {'dentro' if r['dentro_de_rango_$'] else 'fuera'}; la comparación en $ está sesgada por la escala del precio)")
        if not r["concluyente"]:
            txt += f". Muestra < {r['minimo_para_comparar']}: NO concluyente"
        L.append(txt + ".")
    L += ["", f"_Config congelada SHA-256 {config_hash[:16]}… · todas las alertas son informativas; no se cambia nada._"]
    return "\n".join(L)


def _resumen_slippage(ea: pd.DataFrame, f) -> str:
    if ea is None or len(ea) == 0 or "slippage_total_pts" not in ea:
        return "sin operaciones del EA registradas"
    x = ea[pd.to_datetime(ea.t_entrada_ny).dt.date == f]
    if len(x) == 0:
        return "sin operaciones del EA hoy"
    return f"{x.slippage_total_pts.mean():.2f} pts medios por operación (spread medio {x.spread_entrada_pts.mean():.2f} pts)"


def _problemas_ejecucion(emp: pd.DataFrame, estado: dict) -> str:
    if emp is None or len(emp) == 0:
        return "ninguno detectado (sin registro del EA para comparar)" if not estado.get("ea_leido") else "ninguno"
    malos = emp[emp.estado != "emparejada"]
    return "ninguno" if len(malos) == 0 else f"{len(malos)} operaciones sin pareja entre el teórico y el EA (ver logs/emparejamiento.csv)"


def _alertas(d: pd.DataFrame) -> str:
    if d is None or len(d) == 0:
        return "—"
    malas = d[d.estado.str.contains("WARNING|ALERT", regex=True)]
    if len(malas) == 0:
        return "ninguna (" + ", ".join(f"{N[e]} {int(v)}: {s}" for e, v, s in zip(d.estrategia, d.ventana, d.estado) if "insuficiente" not in s) + ")" \
            if (~d.estado.str.contains("insuficiente")).any() else "ninguna (muestra insuficiente en todas las ventanas)"
    return "; ".join(f"{N[e]} últimas {v} ({'$' if md == 'neto_$' else '% precio'}): media {m} → {s}"
                     for e, md, v, m, s in zip(malas.estrategia, malas.medida, malas.ventana, malas.media_ultimas, malas.estado))


def semanal(anio_semana: str, cerradas: dict, ea: pd.DataFrame, deriva: pd.DataFrame, comparaciones: dict,
            ventanas: dict) -> str:
    L = [f"# FORWARD — informe semanal {anio_semana}", "",
         "Solo estadística descriptiva. Sin ranking y sin ganador. Una muestra pequeña **no** es evidencia.", ""]
    for k in ("NOISE_ZONE", "RSI2"):
        o = cerradas[k]
        L += [f"## {N[k]}", ""]
        if len(o) == 0:
            L += ["Sin operaciones forward cerradas.", ""]
            continue
        sem = o[pd.to_datetime(o.t_salida_ny).dt.strftime("%G-W%V") == anio_semana]
        x = o["neto_$"].astype(float)
        L.append(f"- Operaciones: {len(sem)} esta semana, {len(o)} desde el inicio.")
        L.append(f"- Expectativa: semana {_f(sem['neto_$'].mean() if len(sem) else np.nan)} $; acumulada {_f(x.mean())} $.")
        for n in ventanas[k]:
            L.append(f"- Expectativa móvil últimas {n}: {_f(x.iloc[-n:].mean()) if len(x) >= n else 'muestra insuficiente'}")
        eq = x.cumsum()
        L.append(f"- Drawdown máximo forward: {_f(float((eq - eq.cummax().clip(lower=0)).min()))} $; actual: {_f(_dd_actual(x))} $.")
        if ea is not None and len(ea) and "slippage_total_pts" in ea:
            e = ea[(ea.estrategia == k) & (ea.estado == "CERRADA")]
            L.append(f"- Slippage EA: {_f(e.slippage_total_pts.mean())} pts medios ({len(e)} operaciones del EA).")
        L.append(f"- Distribución (forward): p5 {_f(np.percentile(x, 5))}, p25 {_f(np.percentile(x, 25))}, mediana "
                 f"{_f(np.median(x))}, p75 {_f(np.percentile(x, 75))}, p95 {_f(np.percentile(x, 95))} $.")
        L += ["", "**Backtest vs forward:**", _tabla(comparaciones[k]["tabla"])]
    L += ["## Combinado (descriptivo)", ""]
    todas = pd.concat([v for v in cerradas.values() if len(v)], ignore_index=True) if any(len(v) for v in cerradas.values()) else pd.DataFrame()
    if len(todas):
        todas = todas.sort_values("t_salida_utc")
        y = todas["neto_$"].astype(float)
        L.append(f"- {len(todas)} operaciones, neto {_f(y.sum())} $, DD máximo {_f(float((y.cumsum() - y.cumsum().cummax().clip(lower=0)).min()))} $ "
                 "(1 MNQ por estrategia, suma descriptiva).")
    L += ["", "## Deriva (informativa; en $ con umbrales oficiales y en % del precio)",
          _tabla(deriva.set_index(["estrategia", "medida", "ventana"]) if len(deriva) else deriva)]
    return "\n".join(L)
