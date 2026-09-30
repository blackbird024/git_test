"""Congela FORWARD_TESTING v1.0 (se ejecuta UNA vez, antes de las 09:30 NY del 30/09/2026):

    python -m forward_testing.congelar

Escribe config/FORWARD_TESTING_CONFIG.json (+ .sha256), las bandas de deriva (config/bandas_deriva_v1.json) y el
MAE/MFE de referencia del backtest (config/referencia_mae_mfe.csv). Después hay que hacer commit: el commit es la prueba
de que nada se cambió una vez empezado el forward.
"""
from __future__ import annotations

import json

import pandas as pd

from bot_lab.core.datos import Contexto
from forward_testing.src import congelado as CG
from forward_testing.src import deriva as DV
from src.data.datos import excluidos, velas_1m
from src.strategies import nq_rsi2
from survivor.src import congeladas as K
from survivor.src import trayectorias as TR

from .run_diario import FT, referencia


def main(forzar: bool = False):
    K.comprobar_integridad()
    ref = referencia()
    ventanas = CG.contenido()["deriva"]
    ventanas = {k: v["ventanas"] for k, v in ventanas.items() if k in ("NOISE_ZONE", "RSI2")}
    b = DV.todas_las_bandas(ref, ventanas)
    (FT / "config" / "bandas_deriva_v1.json").write_text(json.dumps(b, indent=2), encoding="utf-8")
    bp = DV.todas_las_bandas(ref, ventanas, pct=True)
    (FT / "config" / "bandas_deriva_v1_pct.json").write_text(json.dumps(bp, indent=2), encoding="utf-8")
    m1, ex = velas_1m("NQ"), excluidos("NQ")
    ctx = Contexto(m1, ex)
    zr = K.zona_ruido(m1, ex)
    rs = K.rsi2(m1, ex)
    s = nq_rsi2.preparar(m1, K.RSI2_SURVIVOR_V1)
    tz, tr = TR.zona_ruido(ctx, zr), TR.rsi2(rs, s)
    entrada_rsi = s.open.to_numpy()[pd.Index(s.t_primera).get_indexer(rs.t_entrada)]
    pd.concat([pd.DataFrame({"estrategia": "NOISE_ZONE", "mae_pts": tz.mae_pts, "mfe_pts": tz.mfe_pts}),
               pd.DataFrame({"estrategia": "RSI2", "mae_pts": tr["mae_%"] / 100 * entrada_rsi,
                             "mfe_pts": tr["mfe_%"] / 100 * entrada_rsi})]) \
        .to_csv(FT / "config" / "referencia_mae_mfe.csv", index=False)
    CG.generar(forzar=forzar)
    print("congelado:", CG.CONFIG, "sha256", CG.HUELLA.read_text().strip())
    for k, v in b.items():
        print(k, {n: (x["p1"], x["p5"], x["p50"]) for n, x in v.items()})


if __name__ == "__main__":
    import sys
    main(forzar="--forzar-antes-del-inicio" in sys.argv)
