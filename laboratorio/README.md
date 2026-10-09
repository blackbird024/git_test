# Laboratorio cuantitativo Nasdaq

Investigación reproducible de dos sistemas separados:
- **A**: Topstep 50K intradía en MNQ (ORB 5 min, continuación de tendencia, zona de ruido).
- **B**: swing de 1-4 semanas con capital propio (ruptura de 20 sesiones, filtros, RSI(2), retroceso a EMA20) frente a comprar y mantener.

**Empieza por `reports/INFORME_FINAL.md`.**

| Carpeta | Contenido |
|---|---|
| `config/` | `PROTOCOLO.yaml` (periodos y criterios fijados antes de ver resultados), `CONFIG_COSTES.yaml`, `CONFIG_RIESGO.yaml` |
| `data/` | Cargadores (NQ 1 min de `alpaca/.lab_cache`, solo lectura), calendario XNYS, conversión ET → Italia, descarga gratuita de QQQ |
| `strategies/` | `orb.py`, `trend.py`, `noise.py`, `swing.py`, `features.py` (indicadores diarios desplazados un día) |
| `backtests/` | `intraday.py` (ejecución con velas de 1 min), `swing.py` (diario) |
| `execution_costs/` | Modelo de costes leído de la configuración |
| `risk/` | `topstep.py` (MLL con trailing al cierre, DLL, consistencia, límites personales) |
| `validation/` | Métricas, bootstrap por bloques, particiones y manifiestos |
| `experiments/` | Un directorio por ejecución con `manifest.json`, más `reglas_congeladas.yaml` |
| `reports/` | Informe, auditoría, matriz, diario, checklists, gráficos |
| `tests/` | 27 tests: ejecución, stops/huecos, objetivo, medias jornadas, ORB, no-anticipación, Topstep, swing |

Reproducción: ver `reports/INFORME_FINAL.md` §8. La caché local (`data/cache/`) no se versiona.
