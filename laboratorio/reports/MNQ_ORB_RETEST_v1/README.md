# MNQ_ORB_RETEST_v1 · cómo reproducirlo

Todo se ejecuta desde `laboratorio/` con el Python del entorno (3.11 aquí). No descarga datos: usa la caché local de
NQ 1 min (`data/cache/nq_1m_et.pkl` y `sessions.pkl`, generadas desde `alpaca/.lab_cache/` por `data/loaders.py`).

```bash
cd laboratorio
python -m pytest -q tests                                              # 54 tests (30 previos + 24 de este experimento)
python run_backtest.py --strategy MNQ_ORB_RETEST_v1                    # desarrollo + validación
python run_backtest.py --strategy MNQ_ORB_RETEST_v1 --congelar         # congela las reglas (FREEZE.json)
python run_backtest.py --strategy MNQ_ORB_RETEST_v1 --abrir-prueba     # añade 2025-2026 (exige reglas congeladas)
python run_robustness.py --strategy MNQ_ORB_RETEST_v1                  # rejilla y escenarios → robustness.csv
python generate_report.py --strategy MNQ_ORB_RETEST_v1                 # gráficos + report.md + data_audit.md
```

`--abrir-prueba` se niega a ejecutarse si las reglas actuales no coinciden con las congeladas.

## Código
| Archivo | Función |
|---|---|
| `orb_retest/config.py` | Versión, reglas, escenarios de coste, riesgo y particiones |
| `orb_retest/signals.py` | Rango, velas de 5 min y ruptura → retesteo → confirmación |
| `orb_retest/execution.py` | Entrada, SL, TP, huecos, ambigüedad, cierre por tiempo y contratos |
| `orb_retest/engine.py` | Recorre las sesiones; tamaño por riesgo y límites de cuenta |
| `orb_retest/metrics.py` | Métricas, bootstrap por bloques, drawdown, ruina por Monte Carlo |
| `orb_retest/pipeline.py` | Particiones, escenarios, desgloses y congelación |
| `orb_retest/audit.py` | Auditoría de datos |
| `tests/test_orb_retest.py` | 24 tests de reglas, ejecución, no-anticipación, horario de verano y reproducibilidad |

Reutilizado del laboratorio: `data/loaders.py` (datos, calendario XNYS, sesiones), `validation/metrics.py` (bootstrap
por bloques), `config/PROTOCOLO.yaml` (particiones) y las convenciones de ejecución de `backtests/intraday.py`.

## Archivos de resultados
| Archivo | Contenido |
|---|---|
| `report.md` | Informe y conclusión |
| `strategy_spec.md` | Reglas congeladas |
| `FREEZE.json` | Hash de reglas, commit y fecha de congelación |
| `data_audit.md` / `.json` | Auditoría de datos |
| `backtest_config.json` | Parámetros, costes, particiones y umbrales |
| `metrics.json` | Métricas por partición y por escenario de coste, y tamaño por riesgo |
| `trades.csv` | Operaciones (coste base) con niveles, contratos (riesgo 50 $) y resultado |
| `trades_coste_*.csv.gz` | Operaciones con los demás escenarios de coste |
| `daily_results.csv` | Una fila por sesión, incluidos los días sin operación y su motivo |
| `monthly_results.csv`, `yearly_results.csv` | Agregados |
| `robustness.csv` | 48 variantes |
| `desglose_*.csv` | Por año, lado, anchura del rango, volatilidad previa, semana de vencimiento y salida |
| `*.png` | Equity, drawdown, distribución de R, mensual, anual, particiones y sensibilidad |
