"""Un solo comando para todo el proyecto:  python run_all.py

Paso 0 (datos): carga, control de calidad, marcos temporales y corte desarrollo / fuera de muestra.
Los pasos 1-4 se irán añadiendo aquí a medida que se aprueben.
"""
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from src.data.calidad import dias_iliquidos, huecos, informe, limpiar, saltos  # noqa: E402
from src.data.cargadores import cargar_databento, cargar_mt5  # noqa: E402
from src.data.marcos import remuestrear  # noqa: E402
from src.horas import sesion_cme  # noqa: E402

PROCESADOS = RAIZ / "data" / "processed"
INFORMES = RAIZ / "reports"
PARTICION = RAIZ / "config" / "particion.json"
FRACCION_DESARROLLO = 0.70


def paso0() -> None:
    PROCESADOS.mkdir(parents=True, exist_ok=True)
    INFORMES.mkdir(exist_ok=True)
    filas, detalles, particion = [], [], {}

    fuentes = {r: (lambda r=r: cargar_databento(r)) for r in ("NQ", "GC")}
    for f in sorted((RAIZ / "data" / "mt5").glob("*.csv")):
        fuentes[f"MT5_{f.stem}"] = (lambda f=f: cargar_mt5(f))

    for nombre, cargar in fuentes.items():
        print(f"[paso 0] {nombre}: cargando...", flush=True)
        bruto = cargar()
        info = informe(bruto, nombre)
        filas.append(info)
        limpio = limpiar(bruto)
        h, s = huecos(limpio), saltos(limpio)
        det = [f"### {nombre}", "",
               f"Huecos inesperados de más de 30 min dentro de la sesión: **{len(h)}**. Los 10 mayores:", "",
               h.sort_values("duracion", ascending=False).head(10).to_markdown(index=False) if len(h) else "(ninguno)", "",
               f"Picos de 1 minuto que se deshacen en el minuto siguiente (errores o latigazos de noticias; NO se borran): **{len(s)}**. Los 10 mayores:", "",
               s.reindex(s["rendimiento_%"].abs().sort_values(ascending=False).index).head(10).to_markdown(index=False)
               if len(s) else "(ninguno)", ""]
        if "instrument_id" in limpio:
            ili = sorted(dias_iliquidos(limpio))
            det += [f"Días ilíquidos previsibles (se excluyen de los backtests): **{len(ili)}**. "
                    f"Ejemplos: {', '.join(str(d) for d in ili[:8])}", ""]
        detalles += det
        limpio.to_parquet(PROCESADOS / f"{nombre}_1M.parquet")
        for marco in ("5M", "1H", "4H", "1D"):
            remuestrear(limpio, marco).to_parquet(PROCESADOS / f"{nombre}_{marco}.parquet")
        sesiones = sorted(set(sesion_cme(limpio.index)))
        corte = sesiones[int(len(sesiones) * FRACCION_DESARROLLO)]
        particion[nombre] = {"primera_sesion": str(sesiones[0]), "ultima_sesion": str(sesiones[-1]),
                             "inicio_fuera_de_muestra": str(corte)}

    # Datos diarios (para las ventajas de varios días): mismo corte del 70 %.
    for f in sorted((RAIZ / "data" / "raw" / "daily").glob("*.parquet")):
        d = pd.read_parquet(f)
        dias = sorted(pd.to_datetime(d.index).tz_convert("UTC").date)
        particion[f"diario_{f.stem}"] = {"primera_sesion": str(dias[0]), "ultima_sesion": str(dias[-1]),
                                         "inicio_fuera_de_muestra": str(dias[int(len(dias) * FRACCION_DESARROLLO)])}

    PARTICION.parent.mkdir(exist_ok=True)
    if PARTICION.exists():
        print("[paso 0] config/particion.json ya existe: NO se modifica (el corte se fija una sola vez).")
    else:
        PARTICION.write_text(json.dumps(particion, indent=2, ensure_ascii=False))
    tabla = pd.DataFrame(filas)
    texto = ["# Informe de calidad de los datos", "",
             "Todas las horas en UTC. Fuente principal: futuros de CME (Databento), contrato continuo por volumen.", "",
             tabla.to_markdown(index=False), "",
             "## Corte desarrollo / fuera de muestra (fijado ahora, antes de cualquier resultado)", "",
             "```json", json.dumps(json.loads(PARTICION.read_text()), indent=2, ensure_ascii=False), "```", "",
             "## Detalle por mercado", ""] + detalles
    (INFORMES / "calidad_datos.md").write_text("\n".join(texto), encoding="utf-8")
    print(tabla.T.to_string())
    print(f"\nInforme: {INFORMES / 'calidad_datos.md'}")


if __name__ == "__main__":
    paso0()
