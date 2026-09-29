# Datos

**Nunca se inventan ni se rellenan datos.** Si faltan o la calidad no llega al mínimo (`data.min_sessions`,
`data.max_invalid_fraction`), el programa se detiene y explica por qué.

## Fuente por defecto
Velas de 1 minuto de NQ (E-mini Nasdaq-100) de Databento, dataset GLBX.MDP3, contrato continuo `NQ.v.0` (sigue al
vencimiento con más volumen), en `../data/raw/NQ_1m_<AÑO>.parquet` (no están en git: son datos con licencia; copia
privada en el repositorio `apex-datos`). Índice en UTC, columnas open, high, low, close, volume, instrument_id.

## Importar un CSV propio
1. Una fila por vela, con cabecera. Columna de tiempo: `timestamp` (o `datetime`, `time`, `date`, `ts_event`) +
   `open, high, low, close, volume` (+ `instrument_id` opcional: sin ella no se detectan los cambios de contrato).
2. Si los timestamps no llevan zona horaria, indica cuál es en `data.timezone_if_naive` (p. ej. `America/New_York`).
3. Indica el marco de la fuente en `data.source_bar_minutes` (1 recomendado; 15 también funciona, pero entonces
   stops y targets dentro de la vela se resuelven con la hipótesis conservadora sobre la vela entera).
4. Pon la ruta en `data.path` (admite comodines) y ejecuta `python -m src.run_backtest validate`.

## Contratos continuos
El contrato continuo **sin ajustar** muestra un salto de precio en cada cambio de vencimiento. Ajustar hacia atrás
(sumar o multiplicar el pasado) usa información que no se conocía en su momento, así que no se hace. Como la
estrategia es intradía y cierra antes de las 16:00, el salto nunca cae dentro de una operación; los indicadores de
varias sesiones (ATR, EMA, RSI) se reinician en cada contrato para no mezclar precios de contratos distintos.
