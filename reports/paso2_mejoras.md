# Paso 2 — Mejoras del RSI(2) en NQ (solo periodo de desarrollo)

## Cambio 1 — Salida rápida (RSI > 60 en vez de 70)

Causa: el rebote que buscamos es corto; salir antes asegura la parte más fiable.

| versión                |   operaciones |   acierto_% |   profit_factor |   R_medio |    t |   neto_$ |   drawdown_max_$ |   peor_op_% |
|:-----------------------|--------------:|------------:|----------------:|----------:|-----:|---------:|-----------------:|------------:|
| base (salida RSI > 70) |            97 |        68   |            1.46 |     0.3   | 1.22 |     6919 |            -2016 |      -10.77 |
| salida RSI > 60        |            99 |        66.7 |            1.37 |     0.208 | 0.89 |     5295 |            -2351 |      -10.77 |

**Decisión: se descarta.**

## Cambios 2 y 3 — Filtro de volatilidad frente a stop de catástrofe (compiten por el 3.er parámetro)

Causa del filtro: en pánicos las caídas vienen de ventas forzadas que continúan.
Causa del stop: limitar pérdidas extremas como la de febrero de 2020.

| versión                                     |   operaciones |   acierto_% |   profit_factor |   R_medio |    t |   neto_$ |   drawdown_max_$ |   peor_op_% |
|:--------------------------------------------|--------------:|------------:|----------------:|----------:|-----:|---------:|-----------------:|------------:|
| actual                                      |            97 |        68   |            1.46 |     0.3   | 1.22 |     6919 |            -2016 |      -10.77 |
| + filtro de volatilidad (ATR5/ATR50 <= 1,5) |            90 |        68.9 |            1.42 |     0.361 | 1.44 |     5822 |            -2016 |      -10.77 |
| + stop de catástrofe (2 x ATR14)            |           114 |        63.2 |            1.37 |     0.317 | 1.52 |     7403 |            -2914 |       -4.7  |

**Decisión: no se queda ninguno.**

## Versión final para el paso 3

`Config(entrada=20.0, salida=70.0, max_dias=5, filtro_vol=None, stop_atr=None, sma=200, rsi_n=2, tick=0.25, valor_punto=2.0, contratos=1, costes=Costes(comision_lado=1.0, ticks_normal=1, ticks_apertura=2, multiplicador=1.0))`
