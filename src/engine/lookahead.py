"""Comprobación automática de look-ahead (usar información del futuro sin querer).

Idea: si una estrategia no mira el futuro, sus señales hasta el instante T tienen que ser IDÉNTICAS
tanto si le damos todos los datos como si le damos solo los datos hasta T. Si alguna señal anterior a T
cambia al añadir datos posteriores, la estrategia está usando el futuro.

`funcion_senales(velas) -> DataFrame` con al menos la columna `t_senal` (cierre de la vela que la genera).
"""
import pandas as pd


def comprobar(funcion_senales, velas: pd.DataFrame, cortes: list[pd.Timestamp]) -> list[str]:
    """Devuelve una lista de problemas (vacía si todo está bien)."""
    completas = funcion_senales(velas)
    problemas = []
    for corte in cortes:
        parciales = funcion_senales(velas[velas.index < corte])
        a = completas[completas.t_senal < corte].reset_index(drop=True)
        b = parciales[parciales.t_senal < corte].reset_index(drop=True)
        if not a.equals(b):
            problemas.append(f"Las señales anteriores a {corte} cambian al añadir datos posteriores")
    return problemas
