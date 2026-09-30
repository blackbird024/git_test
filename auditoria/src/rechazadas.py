"""Fases 5-6: vuelve a ejecutar las estrategias rechazadas y el bot con su código y reglas originales (sin cambios),
normaliza sus operaciones y las clasifica con los criterios de auditoria/CRITERIOS.md."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.datos import excluidos, velas_1m
from src.report.smc_kz import VARIANTES as SMC_VARIANTES
from src.strategies import bot_oferta_demanda as bot
from src.strategies import nq_rsi2, or_london_vwap, pares_oro_plata, smc_sweep, vwap_15m, zona_ruido
from src.data.datos import sesiones_diarias_databento

from . import metricas as mt

RAIZ = Path(__file__).resolve().parents[2]


def _norm(o: pd.DataFrame, entrada: str, salida: str, neto: str, bruto: str | None = None, r: str | None = None) -> pd.DataFrame:
    if o is None or len(o) == 0:
        return pd.DataFrame(columns=["t_entrada", "t_salida", "neto", "bruto", "r"])
    x = pd.DataFrame({"t_entrada": pd.to_datetime(o[entrada]), "t_salida": pd.to_datetime(o[salida]),
                      "neto": o[neto].astype(float)})
    for c in ("t_entrada", "t_salida"):
        x[c] = (x[c].dt.tz_localize("UTC") if x[c].dt.tz is None else x[c].dt.tz_convert("UTC"))
    x["bruto"] = o[bruto].astype(float).to_numpy() if bruto else np.nan
    x["r"] = o[r].astype(float).to_numpy() if r else np.nan
    return x


def _subproyecto(carpeta: str, codigo: str) -> list[pd.DataFrame]:
    """Ejecuta código en otro subproyecto (su propio paquete `src`) y lee las operaciones que deja en CSV."""
    salida = RAIZ / "auditoria" / "cache"
    salida.mkdir(exist_ok=True)
    r = subprocess.run([sys.executable, "-c", codigo.replace("__OUT__", str(salida))], cwd=RAIZ / carpeta,
                       capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(f"{carpeta}: {r.stderr[-2000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


VWAP_MNQ = r'''
import json, pandas as pd
from src.pipeline import load_config, preparar, barras_con_indicadores
from src.backtester import run
cfg = load_config(); ses, _ = preparar(cfg); b = barras_con_indicadores(ses, cfg)
r = run(b, ses.sub, cfg, "2015-01-01", "2100-01-01")
p = "__OUT__/vwap_direccional_mnq.csv"; r.trades.to_csv(p, index=False); print(json.dumps([p]))
'''

VWAP_EMA = r'''
import json
from src.common import Lab, load_config, params
cfg = load_config(); rutas = {}
for inst in ("MNQ", "MGC"):
    lab = Lab(cfg, inst)
    for m in ("A", "B", "C", "D"):
        r, _ = lab.run(params(cfg, model=m), (lab.splits["train"][0], lab.splits["test"][1]))
        p = f"__OUT__/vwap_ema_{inst}_{m}.csv"; r.trades.to_csv(p, index=False); rutas[f"{inst}_{m}"] = p
    rutas[f"{inst}_fin_desarrollo"] = str(lab.splits["validation"][1].date())
print(json.dumps(rutas))
'''


def ejecutar_todas() -> dict:
    """Devuelve {nombre: (operaciones normalizadas, corte de desarrollo, mercado, nota)}."""
    out = {}
    nq, ex_nq = velas_1m("NQ"), excluidos("NQ")
    gc, ex_gc = velas_1m("GC"), excluidos("GC")
    c = "2023-03-22"
    for nombre, cfg in SMC_VARIANTES.items():
        o, _ = smc_sweep.backtest(nq, cfg, ex_nq)
        out[f"SMC/ICT {nombre}"] = (_norm(o, "t_entrada", "t_salida", "neto", "bruto", "r"), c, "NQ (1 MNQ)",
                                    "originalmente solo desarrollo")
    o, _ = or_london_vwap.backtest(nq, or_london_vwap.Config(), ex_nq)
    out["Rango 30 min + London + VWAP"] = (_norm(o, "t_entrada", "t_salida", "neto", "bruto", "r"), c, "NQ (1 MNQ)", "")
    o, _ = vwap_15m.backtest(nq, vwap_15m.Config(), ex_nq)
    out["Cruce VWAP 15m 1:2"] = (_norm(o, "t_entrada", "t_salida", "neto", "bruto", "r"), c, "NQ (1 MNQ)", "")
    o, _ = zona_ruido.backtest(gc, zona_ruido.Config(valor_punto=10.0, tick=0.10), ex_gc)
    out["Zona de ruido en oro"] = (_norm(o, "t_entrada", "t_salida", "neto", "bruto"), c, "GC (1 MGC)", "")
    o = nq_rsi2.backtest(gc, nq_rsi2.Config(valor_punto=10.0, tick=0.10), ex_gc)
    out["RSI(2) en oro"] = (_norm(o, "t_entrada", "t_salida", "neto", None, "r"), c, "GC (1 MGC)", "")
    d = pares_oro_plata.preparar(sesiones_diarias_databento("GC"), sesiones_diarias_databento("SI"), pares_oro_plata.Config())
    o = pares_oro_plata.backtest(d, pares_oro_plata.Config())
    out["Pares oro/plata"] = (_norm(o, "t_entrada", "t_salida", "neto", "bruto"), "2021-11-09", "GC+SI diario (1 MGC + 1 SIL)", "")
    o = bot.backtest(bot.ajustar_continuo(_gc_crudo()), bot.Config())    # como en src/report/bot_oro.py
    out["Bot oferta/demanda (oro)"] = (_norm(o, "entry_time", "t_salida", "neto", None, "r"), c,
                                       "GC ajustado H1 (costes XAUUSD, en onzas)", "precio del futuro, no del CFD; sin swap")
    for p in _subproyecto("vwap_mnq_strategy", VWAP_MNQ):
        o = pd.read_csv(p)
        out["VWAP direccional (baseline)"] = (_norm(o, "entry_time", "exit_time", "net_pnl", "gross_pnl", "r_net"), c,
                                              "NQ→MNQ (riesgo 0,5 %)", "tamaño variable")
    rutas = _subproyecto("vwap_ema_research", VWAP_EMA)
    for inst in ("MNQ", "MGC"):
        for m in ("A", "B", "C", "D"):
            o = pd.read_csv(rutas[f"{inst}_{m}"])
            out[f"VWAP+EMAs modelo {m} ({inst})"] = (_norm(o, "entry_time", "exit_time", "net_pnl", "gross_pnl", "r_net"),
                                                   (pd.Timestamp(rutas[f"{inst}_fin_desarrollo"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                                                   f"{inst} (riesgo 0,5 %, velas 15m)", "desarrollo = train+validation del proyecto")
    return out


def _gc_crudo() -> pd.DataFrame:
    from src.data.cargadores import cargar_databento
    return cargar_databento("GC")


def clasificar(total: dict, dev: dict) -> str:
    n = total.get("operaciones", 0)
    if n == 0:
        return "No verificable (sin operaciones)"
    lo_t, hi_t = total.get("IC95_bloques_$", (np.nan, np.nan))
    lo_d, hi_d = dev.get("IC95_bloques_$", (np.nan, np.nan))
    if n >= 100 and ((np.isfinite(hi_t) and hi_t < 0) or (dev.get("operaciones", 0) >= 100 and np.isfinite(hi_d) and hi_d < 0)):
        return "Evidencia negativa"
    if n < 100:
        return "No concluyente por muestra insuficiente"
    if np.isfinite(lo_t) and lo_t > 0 and dev.get("expectativa_$", -1) > 0:
        return "Evidencia positiva (a revisar con el resto de criterios)"
    return "No concluyente (el IC 95 % incluye el 0)"
