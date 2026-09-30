"""Auditoría completa. Uso (desde la raíz del repositorio):

    python -m auditoria.run_auditoria            -> auditoria/experimentos/<AAAAMMDD_HHMM>/ (resultados + manifiesto)
    python -m auditoria.generar_informe <carpeta> -> INFORME_FINAL.md y gráficos en esa carpeta

No modifica ningún archivo original: todo se escribe en la carpeta del experimento.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.engine.costes import Costes
from src.strategies import nq_rsi2, zona_ruido as z

from .src import cartera as ca
from .src import rechazadas as rj
from .src import validadas as va

RAIZ = Path(__file__).resolve().parent.parent
LOG = []


def log(msg: str) -> None:
    linea = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(linea, flush=True)
    LOG.append(linea)


def manifiesto(cfg: dict, carpeta: Path) -> dict:
    def git(*a):
        return subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    datos = {}
    for f in sorted((RAIZ / "data" / "raw").glob("*_1m_*.parquet")) + sorted((RAIZ / "data" / "raw" / "daily").glob("*.parquet")):
        datos[str(f.relative_to(RAIZ))] = {"bytes": f.stat().st_size, "sha1": hashlib.sha1(f.read_bytes()).hexdigest()}
    import matplotlib
    m = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "commit": git("rev-parse", "HEAD"),
         "cambios_sin_commit": git("status", "--porcelain"), "python": sys.version.split()[0], "plataforma": platform.platform(),
         "pandas": pd.__version__, "numpy": np.__version__, "matplotlib": matplotlib.__version__, "semilla": cfg["semilla"],
         "config": cfg, "datos": datos}
    (carpeta / "manifiesto.json").write_text(json.dumps(m, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return m


def main() -> None:
    cfg = yaml.safe_load((RAIZ / "auditoria" / "config" / "auditoria.yaml").read_text(encoding="utf-8"))
    carpeta = RAIZ / "auditoria" / "experimentos" / datetime.now().strftime("%Y%m%d_%H%M")
    carpeta.mkdir(parents=True, exist_ok=False)
    (carpeta / "config_usada.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    log(f"experimento en {carpeta}")
    manifiesto(cfg, carpeta)
    R = {}
    ctx = va.Contexto(cfg)
    capital = cfg["cartera"]["capital"]

    log("Fase 1: comprobaciones empíricas (calidad de datos, truncamiento)")
    R["auditoria"] = va.auditoria_empirica(ctx)

    log("Fase 2: reproducción exacta")
    zr, rs = va.correr_zr(ctx), va.correr_rsi(ctx)
    R["ops"] = {"zona_ruido": zr, "rsi2": rs}
    R["original"] = va.ORIGINAL
    R["analisis"] = {"zona_ruido": va.analizar(ctx, "zona_ruido", zr, capital), "rsi2": va.analizar(ctx, "rsi2", rs, capital)}

    log("Fase 4: costes y latencia")
    cz = cfg["zona_ruido"]["costes"]
    costes = {"zona_ruido": {}, "rsi2": {}}
    for k in ("x2", "x3"):
        costes["zona_ruido"][k] = ctx.evaluar(va.correr_zr(ctx, z.Config().con(**cz[k])), capital, bootstrap=False)
        costes["rsi2"][k] = ctx.evaluar(va.correr_rsi(ctx, nq_rsi2.Config().con(costes=Costes(**cfg["rsi2"]["costes"][k]))), capital, bootstrap=False)
    costes["zona_ruido"]["sin_costes"] = ctx.evaluar(va.correr_zr(ctx, z.Config().con(ticks_entrada=0, ticks_salida=0, comision_lado=0.0)), capital, bootstrap=False)
    costes["rsi2"]["sin_costes"] = ctx.evaluar(va.correr_rsi(ctx, nq_rsi2.Config().con(costes=Costes(multiplicador=0.0))), capital, bootstrap=False)
    if cfg["zona_ruido"]["ejecucion_siguiente_minuto"]:
        costes["zona_ruido"]["ejecucion_1_min_despues"] = ctx.evaluar(va.correr_zr(ctx, retardo=1), capital, bootstrap=False)
    R["costes_latencia"] = costes

    log("Fase 4: vecindad de parámetros")
    R["vecindad"] = {"zona_ruido": va.vecindad_zr(ctx), "rsi2": va.vecindad_rsi(ctx)}

    log("Fases 5-6: estrategias rechazadas y bot")
    rech = {}
    for nombre, (o, corte, mercado, nota) in rj.ejecutar_todas().items():
        t = pd.DatetimeIndex(o.t_entrada).tz_convert(va.mt.NY).tz_localize(None)
        dev, pos = o[t < pd.Timestamp(corte)], o[t >= pd.Timestamp(corte)]
        r_tot, r_dev, r_pos = ctx.evaluar(o, 50000), ctx.evaluar(dev, 50000), ctx.evaluar(pos, 50000)
        rech[nombre] = {"mercado": mercado, "nota": nota, "corte_desarrollo": corte, "total": r_tot, "desarrollo": r_dev,
                        "posterior": r_pos, "estado": rj.clasificar(r_tot, r_dev), "ops": o}
        log(f"  {nombre}: {r_tot.get('operaciones')} operaciones, {rech[nombre]['estado']}")
    R["rechazadas"] = rech

    log("Fase 7: cartera")
    d = ca.series(zr, rs, ctx.sesiones)
    corte = pd.Timestamp(cfg["corte_desarrollo"])
    asign = {"1. solo zona de ruido (1 MNQ)": (1.0, 0.0), "2. solo RSI(2) (1 MNQ)": (0.0, 1.0)}
    for nombre, rel in cfg["cartera"]["pesos_relativos"].items():
        asign[f"3/4. {nombre} (misma vol. que la zona sola)"] = ca.pesos(d, corte, tuple(rel))
    asign["5. 1 + 1 MNQ (plan actual, más riesgo total)"] = (1.0, 1.0)
    tabla = []
    for nombre, (wz, wr) in asign.items():
        for tramo, x in (("total", d), ("desarrollo", d[d.index < corte]), ("posterior (ya visto)", d[d.index >= corte])):
            tabla.append({"asignación": nombre, "tramo": tramo, **ca.evaluar_cartera(x, wz, wr, capital)})
    R["cartera"] = {"diario": d, "asignaciones": asign, "tabla": pd.DataFrame(tabla), "correlaciones": ca.correlaciones(d),
                    "solapamiento": ca.solapamiento(zr, rs),
                    "costes_anuales_1+1_$": round((zr.bruto - zr.neto).sum() / (len(d) / 252), 0)}

    log("Fase 8: simulación de riesgo")
    b = cfg["bootstrap"]
    sims = []
    for cap in cfg["riesgo"]["capitales"]:
        for n in cfg["riesgo"]["contratos"]:
            p = n * (d.zona + d.rsi2)
            for lim in cfg["riesgo"]["limite_diario"]:
                for cmax in cfg["riesgo"]["caida_maxima"]:
                    sims.append({"capital_$": cap, "contratos_por_estrategia": n, "limite_diario_$": lim, "caida_maxima_$": cmax,
                                 **ca.simular_riesgo(p, cap, lim, cmax, b["bloque_sesiones"], b["n"], b["horizonte_sesiones"], cfg["semilla"])})
    peor = {"zona_peor_operacion_1MNQ_$": round(zr.neto.min(), 0), "rsi2_peor_operacion_1MNQ_$": round(rs.neto.min(), 0),
            "rsi2_peor_ret_%": round(rs["ret_%"].min(), 2)}
    R["riesgo"] = {"simulaciones": pd.DataFrame(sims), "peores": peor}

    (carpeta / "resultados.pkl").write_bytes(pickle.dumps(R))
    for n, o in R["ops"].items():
        o.to_csv(carpeta / f"operaciones_{n}.csv", index=False)
    R["cartera"]["tabla"].to_csv(carpeta / "cartera.csv", index=False)
    R["riesgo"]["simulaciones"].to_csv(carpeta / "simulaciones_riesgo.csv", index=False)
    (carpeta / "log.txt").write_text("\n".join(LOG), encoding="utf-8")
    log("fin")
    print(carpeta)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"{time.time() - t0:.0f} s")
