"""Congelación de FORWARD_TESTING v1.0.

`generar()` escribe config/FORWARD_TESTING_CONFIG.json UNA vez (antes de las 09:30 NY del 30/09/2026) con los SHA-256 del código,
los parámetros, costes, deslizamiento, horarios, reglas, tamaño y exposición nocturna, y guarda el SHA-256 del propio
JSON en config/FORWARD_TESTING_CONFIG.sha256. `verificar()` se ejecuta en CADA corrida: si algo no coincide, el día es
INVALID (no se corrige nada en silencio).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

from survivor.src import congeladas as K

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "forward_testing" / "config" / "FORWARD_TESTING_CONFIG.json"
HUELLA = CONFIG.with_suffix(".sha256")
REFERENCIAS = [RAIZ / "forward_testing" / "config" / n for n in ("bandas_deriva_v1.json", "bandas_deriva_v1_pct.json",
                                                                  "referencia_mae_mfe.csv")] + \
    [RAIZ / "survivor" / "experimentos" / "20260930_0939" / n for n in ("operaciones_RSI2.csv", "operaciones_NOISE_ZONE.csv")]
ARCHIVOS = ["src/strategies/nq_rsi2.py", "src/strategies/zona_ruido.py", "src/engine/costes.py", "src/data/datos.py",
            "src/data/calidad.py", "src/horas.py", "survivor/src/congeladas.py", "mt5/APEX_Multiestrategia.mq5"]


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _parametros(cfg) -> dict:
    out = {}
    for f in dataclasses.fields(cfg):
        v = getattr(cfg, f.name)
        out[f.name] = dataclasses.asdict(v) if dataclasses.is_dataclass(v) else v
    return out


def contenido() -> dict:
    return {
        "version": "FORWARD_TESTING v1.0",
        "inicio_forward": {"fecha": "2026-09-30", "zona": "America/New_York",
                           "regla": "operación forward = operación con ENTRADA >= 2026-09-30 00:00 NY"},
        "estrategias": {
            "RSI2": {"version": "RSI2_SURVIVOR_V1", "codigo": "src/strategies/nq_rsi2.py",
                     "parametros": _parametros(K.RSI2_SURVIVOR_V1),
                     "reglas": {"señal": "al cierre de la sesión CME: close_aj > SMA200 y RSI(2) < 20",
                                "entrada": "apertura de la sesión siguiente (reapertura de Globex 18:00 NY), a mercado",
                                "salida": "apertura siguiente al cierre con RSI(2) > 70 o tras 5 sesiones", "stop": "ninguno",
                                "lado": "solo largos"},
                     "horario": "decisión 17:00 NY (cierre de sesión CME), ejecución 18:00 NY",
                     "costes": {"comision_lado_$": 1.0, "desl_ticks_apertura_globex": 2, "desl_ticks_resto": 1},
                     "exposicion_nocturna": "SÍ: mantiene posiciones de 1 a 5 sesiones (incluye fines de semana)"},
            "NOISE_ZONE": {"version": "NOISE_ZONE_SURVIVOR_V1", "codigo": "src/strategies/zona_ruido.py",
                           "parametros": _parametros(K.NOISE_ZONE_SURVIVOR_V1),
                           "reglas": {"bandas": "max/min(apertura, cierre anterior) × (1 ± sigma de 14 días del minuto)",
                                      "entrada": "chequeos 10:00-15:30 NY cada 30 min con el cierre del minuto anterior; "
                                                 "sobre la banda sup. -> largo, bajo la inf. -> corto; ejecución en la apertura del minuto",
                                      "salida": "largo: precio < max(banda sup., VWAP); corto: simétrico; cierre forzado 15:59 NY",
                                      "stop": "ninguno (trailing por banda/VWAP en cada chequeo)"},
                           "horario": "09:30-16:00 NY", "costes": {"comision_lado_$": 1.0, "desl_ticks_por_lado": 1},
                           "exposicion_nocturna": "NO: todo se cierra en el día"},
        },
        "mercado": {"simbolo": "NQ.v.0 (Databento GLBX.MDP3, ohlcv-1m) -> se opera como MNQ", "tick": 0.25,
                    "valor_punto_MNQ_$": 2.0, "zona_horaria_datos": "UTC", "sesiones_excluidas": "regla causal dias_iliquidos"},
        "tamano": {"RSI2_MNQ": 1, "NOISE_ZONE_MNQ": 1, "nota": "cada estrategia se evalúa POR SEPARADO con 1 MNQ; la vista "
                   "combinada es solo descriptiva. El tamaño no cambia por resultados."},
        "deriva": {"NOISE_ZONE": {"ventanas": [20, 50, 100], "umbral_oficial": {"ventana": 50, "media_$": -20.5}},
                   "RSI2": {"ventanas": [10, 15, 25], "umbral_oficial": {"ventana": 15, "media_$": -71.0}},
                   "accion": "SOLO INFORMATIVA: no apaga, no cambia parámetros, no cambia el riesgo"},
        "referencia_backtest": {"origen": "survivor/experimentos/20260930_0939 (2015-01-02 -> 2026-09-28, NOT OUT-OF-SAMPLE)",
                                "operaciones": {"RSI2": "operaciones_RSI2.csv", "NOISE_ZONE": "operaciones_NOISE_ZONE.csv"}},
        "muestras_minimas_para_comparar": {"NOISE_ZONE": 50, "RSI2": 15},
        "ea_demo": {"archivo": "mt5/APEX_Multiestrategia.mq5", "registro": "MQL5/Files/APEX_registro_v2.csv",
                    "instrumento": "CFD NAS100 Pepperstone (NO es el futuro: mide ejecución, no la estrategia pura)",
                    "entradas_recomendadas": {"DineroPorPuntoZona": 2.0, "DineroPorPuntoRSI": 2.0, "PerdidaDiariaMax": 5000.0,
                                              "CaidaMaximaCartera": 5000.0}},
        "sha256": {a: sha256(RAIZ / a) for a in ARCHIVOS},
        "archivos_referencia": {str(f.relative_to(RAIZ)): sha256(f) for f in REFERENCIAS if f.exists()},
        "datos_base": {"archivo": "data/processed/NQ_1M.parquet", "sha256": sha256(RAIZ / "data" / "processed" / "NQ_1M.parquet")},
    }


def generar(forzar: bool = False) -> dict:
    if CONFIG.exists() and not forzar:
        raise SystemExit("La configuración ya está congelada. No se regenera (usa forzar=True SOLO antes de las 09:30 NY del 30/09/2026).")
    c = contenido()
    texto = json.dumps(c, indent=2, ensure_ascii=False)
    CONFIG.write_text(texto, encoding="utf-8")
    HUELLA.write_text(hashlib.sha256(texto.encode("utf-8")).hexdigest() + "\n", encoding="utf-8")
    return c


def cargar() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def verificar() -> list[str]:
    """Lista de problemas (vacía = todo coincide con lo congelado)."""
    problemas = []
    if not CONFIG.exists():
        return ["no existe FORWARD_TESTING_CONFIG.json"]
    if hashlib.sha256(CONFIG.read_bytes()).hexdigest() != HUELLA.read_text().strip():
        problemas.append("FORWARD_TESTING_CONFIG.json ha cambiado después de congelarse")
    c = cargar()
    for a, h in {**c["sha256"], **c.get("archivos_referencia", {})}.items():
        real = sha256(RAIZ / a)
        if real != h:
            problemas.append(f"{a} ha cambiado (SHA-256 {real[:12]}… ≠ congelado {h[:12]}…)")
    if len(c.get("archivos_referencia", {})) < len(REFERENCIAS):
        problemas.append("faltan huellas de archivos de referencia en la configuración")
    actual = contenido()["estrategias"]
    for est in ("RSI2", "NOISE_ZONE"):
        if json.loads(json.dumps(actual[est]["parametros"])) != c["estrategias"][est]["parametros"]:
            problemas.append(f"los parámetros de {est} no coinciden con los congelados")
    return problemas


if __name__ == "__main__":
    generar()
    print(CONFIG)
