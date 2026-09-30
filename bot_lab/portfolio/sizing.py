"""Dimensionamiento SEPARADO de la señal (CRITERIOS.md §9): la señal se valida con 1 MNQ; aquí se estudia qué pasa al
arriesgar un % fijo del capital por operación (contratos enteros, máximo 10 MNQ; 0 contratos = no se opera).
Solo para estrategias con stop (riesgo conocido al entrar). Capital fijo (sin reinversión)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def aplicar(ops: pd.DataFrame, capital: float, riesgo_pct: float, max_contratos: int, valor_punto: float = 2.0) -> pd.DataFrame:
    riesgo_1 = ops.riesgo_pts * valor_punto + ops.comision
    n = np.floor(capital * riesgo_pct / 100 / riesgo_1).clip(0, max_contratos)
    o = ops.copy()
    o["contratos"] = n
    o["neto"] = ops.neto * n
    o["bruto"] = ops.bruto * n
    return o[n > 0].reset_index(drop=True)
