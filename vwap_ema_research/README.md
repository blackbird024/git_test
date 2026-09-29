# VWAP + EMAs, 15 minutos: backtest y optimización por instrumento

Objetivo: saber si existe una ventaja **robusta fuera de muestra**, no encontrar la combinación que más ganó.
Prioridad: robustez > simplicidad > consistencia > profit factor > P&L.

## Comandos (desde `vwap_ema_research/`, Ubuntu)
```bash
pip install -r requirements.txt
python -m pytest -q tests      # pruebas unitarias
python run_backtest.py         # datos + baseline VWAP -> +EMA200 -> +EMA50/200 -> +EMA20, entradas, filtros, horarios
python optimize.py             # optimización secuencial, walk-forward, sensibilidad, TEST, riesgo, Monte Carlo
python generate_report.py      # gráficos (plots/) y reports/FINAL_REPORT.md
```
Todos los parámetros en `config/config.yaml`.

## Estructura
```
config/config.yaml     instrumentos (sesión, costes, tick, valor del punto), baseline, rejillas pequeñas
data/README.md         fuentes y cómo añadir datos (p. ej. XAUUSD)
src/                   data_loader, indicators, strategy, risk, execution, backtester, optimizer, walk_forward,
                       monte_carlo, metrics, report, plotting, common
backtest/              tablas del paso 1 (run_backtest.py)
optimization/          tablas de cada etapa de optimización
results/               resultados en bruto (pickle) y TEST_LOG.md
plots/                 gráficos
reports/FINAL_REPORT.md
tests/                 pruebas unitarias y de no anticipación
```

## Supuestos (configurables)
- **Todo con velas de 15 min** (`general.intrabar: "15m"`): VWAP de sesión con las velas de 15 min; stop y target se
  comprueban con el máximo/mínimo de cada vela de 15 min; si ambos caen en la misma vela se asume el stop.
- Señal al cierre de la vela; ejecución en la apertura de la siguiente. Una posición por instrumento, sin
  pyramiding, sin martingala, sin overnight.
- MNQ/NQ: sesión 09:30–16:00 NY (VWAP reiniciado a las 09:30), cierre forzado 15:45. MGC/GC: 03:00–13:30 NY
  (apertura de Londres → cierre del pit COMEX), cierre forzado 13:15. Horas en America/New_York.
- Precio de MNQ/MGC = precio de NQ/GC (mismo subyacente y cotización; volumen de los futuros grandes para el VWAP).
- Costes: comisión por lado, 1 tick de deslizamiento por ejecución a mercado/stop; escenario con el doble.
- NQ y GC son referencias con 1 contrato fijo y 500.000 $ de capital (con 50.000 $ y riesgo 0,5 % no cabe 1 contrato).
- **XAUUSD: no hay datos en el proyecto.** No se inventan; ver `data/README.md`.

## Protocolo (fijado antes de ejecutar la optimización)
1. Particiones cronológicas por sesiones válidas: train 60 %, validation 20 %, test 20 %.
2. Baseline: modelo A (VWAP), entrada `state`, stop 1,5×ATR(14), sin TP, salida VWAP, riesgo 0,5 %.
3. Etapas secuenciales (una variable cada vez): modelo (A→B→C→D), entrada, filtros de tendencia, stop, TP,
   salida, ventana horaria. **Train optimiza** (la opción debe mejorar la expectativa neta en R de train y tener
   ≥ 150 operaciones), **validation selecciona** (la de mejor R en validation, solo si también mejora la actual en
   validation). Si ninguna cumple, se mantiene la actual.
4. Walk-forward anual (3 años → 1) re-optimizando stop×TP con elección suavizada por vecinas.
5. **Test**: se ejecuta la configuración final y los modelos A–D del baseline; cada uso queda en
   `results/TEST_LOG.md`. No se cambia nada después de verlo.
6. **Candidata a investigación adicional** solo si: expectativa neta > 0 en train, validation y test; t ≥ 2 en al
   menos validation+test combinados; no depende de un solo año, franja o parámetro (sensibilidad); se mantiene con
   costes dobles.
