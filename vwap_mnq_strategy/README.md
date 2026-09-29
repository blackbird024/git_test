# VWAP direccional en MNQ (15 min): investigación reproducible

Proyecto para comprobar, con datos históricos, costes realistas y validación fuera de muestra, si operar en la
dirección del precio respecto al VWAP de sesión en velas de 15 minutos tiene ventaja estadística en MNQ. **No
presupone que la tenga.** El informe final está en `reports/INFORME.md` (lo genera `report`).

## Instalación (Ubuntu)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd vwap_mnq_strategy
python -m pytest -q tests          # pruebas unitarias (datos sintéticos)
```

## Datos
Ver `data/README.md`. Por defecto usa las velas de 1 min de NQ (Databento, contrato continuo) de `../data/raw/`.
Con CSV: cambia `data.path` en `config/settings.yaml`.

## Comandos (desde `vwap_mnq_strategy/`)
| Acción | Comando |
|---|---|
| Cargar y validar datos | `python -m src.run_backtest validate` |
| Baseline (train) | `python -m src.run_backtest baseline --periodo train` |
| Variante | `python -m src.run_backtest variant --periodo validation --set strategy.filters.ema.enabled=true` |
| Optimización acotada | `python -m src.run_backtest optimize --periodo train` |
| Walk-forward | `python -m src.run_backtest walkforward` |
| Exportar operaciones | `python -m src.run_backtest export --periodo train --salida reports/ops.csv` |
| Investigación completa + informe | `python -m src.run_backtest report` |

Todos los parámetros están en `config/settings.yaml` y se pueden cambiar con `--set clave=valor`.

## Estructura
```
config/settings.yaml    parámetros (sesión, costes, riesgo, filtros, particiones, rejilla)
src/data_loader.py      CSV/parquet -> OHLCV en UTC; validación (duplicados, NaN, OHLC, volumen)
src/session_manager.py  sesión RTH en America/New_York, velas de 15 min, VWAP RTH y extendido, tramos de contrato
src/indicators.py       VWAP, bandas, ATR, EMA, RSI, pendiente (causales)
src/signals.py          señal base (cruce / confirmación) y filtros A-G
src/execution.py        costes, deslizamiento, stops/targets intravela (hipótesis conservadora)
src/risk_manager.py     tamaño por riesgo, límites diarios, pausa tras pérdidas
src/backtester.py       motor cronológico (decisión en 15 min, gestión con sub-velas de 1 min)
src/metrics.py          métricas, desgloses, bootstrap
src/optimizer.py        rejilla pequeña de salidas con elección suavizada
src/walk_forward.py     walk-forward anual
src/plots.py            gráficos
src/research.py         protocolo completo e informe
tests/                  pruebas unitarias y de no anticipación
```

## Supuestos principales (conservadores y configurables)
- **Precio:** NQ como fuente de precio para MNQ (mismo índice y cotización; volumen de NQ para el VWAP, más
  representativo). P&L con las especificaciones de MNQ: 2 $ por punto, tick 0,25.
- **Sesión:** 09:30–16:00 NY. VWAP reiniciado a las 09:30; comparación aparte con VWAP desde las 18:00 NY.
- **Ejecución:** señal al cierre de la vela de 15 min; entrada a mercado en la apertura de la siguiente (+1 tick en
  contra). Stops con +1 tick en contra (o la apertura si hay hueco). Target límite sin deslizamiento, solo si el precio
  lo supera en 1 tick. Stop y target en la misma sub-vela de 1 min: se asume el stop.
- **Costes:** 0,85 $ por contrato y lado (broker + CME + NFA aprox.); escenario adverso con 2 ticks.
- **Sin posiciones overnight:** cierre forzado a las 15:45 NY; última entrada 15:15.
- **Contratos:** sin ajuste hacia atrás; ATR/EMA/RSI se reinician en cada cambio de contrato (no hay cambios dentro
  de ninguna vela de 15 min de la sesión regular en los datos).
- **Sesiones incompletas** (cierres anticipados, huecos) excluidas.

## Protocolo de investigación (fijado ANTES de ejecutar la investigación completa)
Particiones cronológicas: **train** 2015-01-01 → 2020-12-31, **validación** 2021-01-01 → 2023-03-21, **test final**
2023-03-22 → fin de datos. Walk-forward: optimiza 3 años, prueba el siguiente, años de prueba 2018–2022.

1. **Baseline fijo** (modo cruce, salida por señal contraria con giro, stop 2×ATR(14), cierre 15:45, riesgo 0,5 %):
   se registra en train y validación sin cambios.
2. **Variantes de entrada** (confirmación B; VWAP extendido): se informan por separado.
3. **Filtros A–G**, uno a uno sobre el baseline. Un filtro se **acepta** si mejora la expectativa neta en R respecto al
   baseline **en train y en validación** y deja al menos 150 operaciones en train.
4. **Salidas** (lista cerrada en `research.py`). Se **acepta** la de mayor expectativa neta en R en train entre las que
   también superan al baseline en validación.
5. **Candidata** = modo cruce + filtros aceptados (combinados; si la combinación es peor en validación que el mejor
   filtro solo, solo ese) + salida aceptada (o la del baseline).
6. Rejilla de stop/target (4×5 = 20 combinaciones) en train con elección suavizada por vecinas, y walk-forward.
7. **Test final**: se ejecuta **una sola vez** el baseline y la candidata. No se cambia nada después.
8. **Criterio de "hipótesis apoyada por los datos"**: en validación y en test, expectativa neta en R > 0 con
   t ≥ 2 y profit factor > 1. Cualquier otra cosa se informa como "no apoyada".

Número de variantes evaluadas: se cuenta y se informa (riesgo de selección múltiple).
