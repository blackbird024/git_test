"""Puntuación reproducible de nichos (Fase 1).

Pesos: config/niche_criteria.yaml. Puntuaciones y evidencia: data/research/niche_scores.yaml.
La puntuación sirve para comparar opciones con criterios explícitos; no predice el éxito de un canal.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CRITERIOS = RAIZ / "config" / "niche_criteria.yaml"
PUNTUACIONES = RAIZ / "data" / "research" / "niche_scores.yaml"


@dataclass(frozen=True)
class Resultado:
    clave: str
    nombre: str
    puntuacion: float          # 0-100
    pct_juicio: float          # % del peso total que descansa en juicio (sin fuente)


def cargar(criterios: Path = CRITERIOS, puntuaciones: Path = PUNTUACIONES) -> tuple[dict, dict]:
    pesos = {k: float(v["peso"]) for k, v in yaml.safe_load(criterios.read_text())["criterios"].items()}
    datos = yaml.safe_load(puntuaciones.read_text())
    validar(pesos, datos)
    return pesos, datos


def validar(pesos: dict, datos: dict) -> None:
    if abs(sum(pesos.values()) - 100) > 1e-9:
        raise ValueError(f"Los pesos deben sumar 100 (suman {sum(pesos.values())})")
    fuentes = set(datos.get("fuentes", {}))
    for clave, cat in datos["categorias"].items():
        p = cat["puntuaciones"]
        if set(p) != set(pesos):
            raise ValueError(f"{clave}: criterios distintos de los configurados: {sorted(set(p) ^ set(pesos))}")
        for crit, v in p.items():
            if not 1 <= v["valor"] <= 5:
                raise ValueError(f"{clave}.{crit}: valor fuera de 1-5")
            ev = v["evidencia"]
            if ev != "juicio" and not (ev.startswith("fuente:") and ev.split(":", 1)[1] in fuentes):
                raise ValueError(f"{clave}.{crit}: evidencia '{ev}' no es 'juicio' ni una fuente listada")


def puntuar(pesos: dict, datos: dict) -> list[Resultado]:
    out = []
    for clave, cat in datos["categorias"].items():
        p = cat["puntuaciones"]
        total = sum(pesos[c] * (p[c]["valor"] - 1) / 4 for c in pesos)      # 1 -> 0, 5 -> peso completo
        juicio = sum(pesos[c] for c in pesos if p[c]["evidencia"] == "juicio")
        out.append(Resultado(clave, cat["nombre"], round(total, 1), round(juicio, 1)))
    return sorted(out, key=lambda r: -r.puntuacion)


def sensibilidad(pesos: dict, datos: dict, n: int = 2000, variacion: float = 0.2, semilla: int = 7) -> dict:
    """Varía cada peso al azar ±`variacion` (y renormaliza a 100) `n` veces.
    Devuelve, por categoría, el % de veces que queda primera y su puesto medio."""
    rng = np.random.default_rng(semilla)
    claves = list(pesos)
    base = np.array([pesos[c] for c in claves])
    cats = list(datos["categorias"])
    valores = np.array([[datos["categorias"][k]["puntuaciones"][c]["valor"] for c in claves] for k in cats])
    norm = (valores - 1) / 4
    primeros, puestos = np.zeros(len(cats)), np.zeros(len(cats))
    for _ in range(n):
        w = base * rng.uniform(1 - variacion, 1 + variacion, len(base))
        w = w / w.sum() * 100
        s = norm @ w
        orden = np.argsort(-s)
        primeros[orden[0]] += 1
        puestos[orden] += np.arange(1, len(cats) + 1)
    return {k: {"primero_%": round(primeros[i] / n * 100, 1), "puesto_medio": round(puestos[i] / n, 2)}
            for i, k in enumerate(cats)}
