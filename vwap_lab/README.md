# Laboratorio VWAP + EMA (MNQ, MGC)

Evalúa seis estrategias de cruces EMA/VWAP con un filtro de "VWAP plano", en las sesiones de Londres y Nueva York, con velas de 5 minutos.

**Empieza por `results/INFORME.md` y `results/CONCLUSIONES.md`.**

```bash
pip install pandas numpy pyyaml matplotlib pytest exchange_calendars
python vwap_lab/tools/build_5m_from_databento.py                 # datos MNQ 5 min con volumen (no descarga nada)
python -m pytest -q vwap_lab/tests                               # 12 pruebas
python -m vwap_lab.run_all --step select   # 1) desarrollo + validación → results/reglas_congeladas.yaml
python -m vwap_lab.run_all --step oos      # 2) OOS una sola vez, costes de estrés, robustez, ablación, walk-forward
python -m vwap_lab.run_all --step report   # 3) results/INFORME.md + gráficos
python -m vwap_lab.run_all --step all      # 1 + 2 + 3 en orden
```

| Carpeta | Contenido |
|---|---|
| `config/vwap_lab.yaml` | Instrumentos, sesiones (zonas IANA), costes base/estrés/severo, parámetros, riesgo y selección |
| `src/data/loader.py` | Carga, validación (reutiliza `orb_backtest.data_io`), volumen, rollovers y sesiones |
| `src/indicators/core.py` | VWAP de sesión, EMA 9/20/21/50, ATR 14 (Wilder) y pendiente del VWAP |
| `src/strategies/signals.py` | Estrategias A–F y filtro de VWAP plano |
| `src/backtest/engine.py` | Ejecución vela a vela, stops, objetivos, cierre de sesión, tamaño y costes |
| `src/metrics/stats.py` | Métricas y bootstrap por bloques de días |
| `run_all.py`, `report.py` | Flujo completo e informe |
| `tests/` | Indicadores, cruces, pendiente, señales A/E, entradas, stops, huecos, objetivo, cierre, tamaño, secuencia, horario de Londres, ausencia de información futura |
| `results/` | CSV de operaciones, rejilla, resultados por periodo, ablación, robustez, walk-forward, gráficos e informe |

Decisiones documentadas en el código:
- **Ejecución:** solo con velas de 5 minutos. Si stop y objetivo caben en la misma vela, cuenta el stop (y se cuentan esas operaciones).
- **Inicio de sesión:** la pendiente del VWAP necesita 6 velas de sesión, así que con el filtro activado no hay señales en los primeros 30 minutos.
- **Rollover:** se excluye la primera sesión tras cada cambio de contrato.
- **Stops demasiado pequeños:** se descartan si el riesgo es menor que 3 veces el coste de ida y vuelta.
- **Comisión:** 0,62 USD por lado, supuesta.
