# Informe ORB 1h + estructura 1h + entrada 5m — MES

**Aviso:** resultados de un backtest. No demuestran rentabilidad futura. Costes: comisión 0,62 USD/lado (supuesto no verificado) + 1 tick de slippage por lado.

## Datos
- Archivo: `/home/user/git_test/orb_backtest/data/ES_5m_databento.csv` (sha256 `15da2be41380dd74…`) — Databento GLBX.MDP3 ES (archivo dbn_ES_5m.pkl de una descarga anterior; se SUPONE ES.c.0 continuo por calendario sin ajuste, no verificado), 5 min desde 1 min. Precios de ES = precios de MES (mismo subyacente y tick).
- Filas: 614,628; desde 2018-01-01 18:00:00-05:00 hasta 2026-10-02 16:55:00-04:00
- Avisos de validación: 1 saltos > 8% entre velas consecutivas (¿error de escala o rollover?); 82 sesiones regulares incompletas (2841 velas ausentes; incluye medias jornadas y festivos con Globex abierto)
- Calendario: XNYS (exchange_calendars)
- Velas de 1 h válidas: 51,445 (descartadas por incompletas: 86); pivotes confirmados: {'highs': 6309, 'lows': 6466}
- Periodos (60/20/20 por sesiones): desarrollo 2018-01-02 → 2023-04-03, validacion 2023-04-04 → 2024-12-31, test 2025-01-02 → 2026-10-02

## Resultados: estrategia completa frente a sin filtro 1H (solo cambia el filtro)

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa | total | 2162 | 1763 | 399 | 0.288 | -0.334 | 0.628 | -10,838.16 | 3,638.16 | 6,302.50 | 11,839.37 | 0.235 | 10 | 23.63 | 0.011 |
| completa | desarrollo | 1298 | 1042 | 256 | 0.281 | -0.365 | 0.605 | -7,819.00 | 2,604.00 | 4,501.25 | 8,306.41 | 0.165 | 10 | 25.08 | 0.013 |
| completa | validacion | 432 | 352 | 80 | 0.300 | -0.303 | 0.643 | -1,932.46 | 624.96 | 1,077.50 | 1,932.46 | 0.046 | 8 | 22.19 | 0.011 |
| completa | test | 432 | 369 | 63 | 0.302 | -0.250 | 0.723 | -1,086.70 | 409.20 | 723.75 | 1,811.12 | 0.045 | 7 | 19.60 | 0.007 |
| sin_filtro_1h | total | 2162 | 920 | 1242 | 0.268 | -0.388 | 0.548 | -29,148.21 | 7,971.96 | 13,996.25 | 29,210.81 | 0.584 | 18 | 21.74 | 0.032 |
| sin_filtro_1h | desarrollo | 1298 | 528 | 770 | 0.249 | -0.456 | 0.508 | -23,579.88 | 6,059.88 | 10,686.25 | 23,725.41 | 0.475 | 18 | 23.59 | 0.036 |
| sin_filtro_1h | validacion | 432 | 164 | 268 | 0.295 | -0.298 | 0.632 | -3,676.72 | 1,181.72 | 2,048.75 | 3,755.50 | 0.142 | 10 | 19.66 | 0.031 |
| sin_filtro_1h | test | 432 | 228 | 204 | 0.304 | -0.249 | 0.709 | -1,891.61 | 730.36 | 1,261.25 | 2,270.68 | 0.098 | 8 | 17.50 | 0.021 |

## Pruebas de estrés de costes y sensibilidad

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa · costes slippage_2_ticks | total | 2162 | 1763 | 399 | 0.261 | -0.463 | 0.514 | -13,933.19 | 2,859.44 | 10,085.00 | 14,525.13 | 0.289 | 16 | 25.54 | 0.012 |
| completa · costes slippage_2_ticks | desarrollo | 1298 | 1042 | 256 | 0.258 | -0.490 | 0.507 | -9,712.14 | 2,059.64 | 7,245.00 | 9,991.09 | 0.199 | 16 | 27.21 | 0.014 |
| completa · costes slippage_2_ticks | validacion | 432 | 352 | 80 | 0.237 | -0.511 | 0.449 | -2,944.84 | 484.84 | 1,727.50 | 2,944.84 | 0.073 | 8 | 24.19 | 0.011 |
| completa · costes slippage_2_ticks | test | 432 | 369 | 63 | 0.302 | -0.292 | 0.647 | -1,276.21 | 314.96 | 1,112.50 | 1,746.72 | 0.047 | 7 | 20.48 | 0.008 |
| sin_filtro_1h · costes slippage_2_ticks | total | 2162 | 939 | 1223 | 0.238 | -0.534 | 0.442 | -33,377.01 | 5,950.76 | 21,272.50 | 33,414.57 | 0.668 | 18 | 23.32 | 0.034 |
| sin_filtro_1h · costes slippage_2_ticks | desarrollo | 1298 | 531 | 767 | 0.227 | -0.581 | 0.426 | -26,608.35 | 4,699.60 | 16,817.50 | 26,623.42 | 0.532 | 18 | 25.99 | 0.039 |
| sin_filtro_1h · costes slippage_2_ticks | validacion | 432 | 170 | 262 | 0.244 | -0.499 | 0.461 | -4,508.62 | 791.12 | 2,830.00 | 4,566.14 | 0.195 | 10 | 20.65 | 0.032 |
| sin_filtro_1h · costes slippage_2_ticks | test | 432 | 238 | 194 | 0.273 | -0.396 | 0.554 | -2,260.04 | 460.04 | 1,625.00 | 2,389.03 | 0.126 | 13 | 16.39 | 0.019 |
| completa · costes slippage_3_ticks_comision_x2 | total | 2162 | 1764 | 398 | 0.231 | -0.677 | 0.392 | -16,635.78 | 4,243.28 | 11,415.00 | 16,772.75 | 0.335 | 16 | 28.14 | 0.013 |
| completa · costes slippage_3_ticks_comision_x2 | desarrollo | 1298 | 1042 | 256 | 0.219 | -0.739 | 0.370 | -12,169.01 | 3,067.76 | 8,276.25 | 12,169.01 | 0.243 | 16 | 29.79 | 0.015 |
| completa · costes slippage_3_ticks_comision_x2 | validacion | 432 | 352 | 80 | 0.237 | -0.634 | 0.400 | -2,862.99 | 714.24 | 1,908.75 | 2,862.99 | 0.076 | 8 | 26.62 | 0.013 |
| completa · costes slippage_3_ticks_comision_x2 | test | 432 | 370 | 62 | 0.274 | -0.477 | 0.508 | -1,603.78 | 461.28 | 1,230.00 | 1,820.77 | 0.052 | 7 | 23.31 | 0.009 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | total | 2162 | 975 | 1187 | 0.214 | -0.747 | 0.338 | -35,546.15 | 8,382.40 | 22,837.50 | 35,566.23 | 0.711 | 22 | 25.12 | 0.035 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | desarrollo | 1298 | 536 | 762 | 0.201 | -0.800 | 0.322 | -29,319.07 | 6,780.32 | 18,525.00 | 29,319.07 | 0.586 | 22 | 27.87 | 0.042 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | validacion | 432 | 181 | 251 | 0.231 | -0.677 | 0.378 | -4,210.39 | 1,036.64 | 2,801.25 | 4,240.41 | 0.205 | 13 | 22.69 | 0.034 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | test | 432 | 258 | 174 | 0.247 | -0.616 | 0.456 | -2,016.69 | 565.44 | 1,511.25 | 2,036.77 | 0.124 | 13 | 16.55 | 0.017 |
| sensibilidad: riesgo 0.50% | total | 2162 | 1763 | 399 | 0.288 | -0.334 | 0.615 | -20,434.15 | 6,615.40 | 11,468.75 | 22,057.58 | 0.434 | 10 | 23.63 | 0.011 |
| sensibilidad: riesgo 1.00% | total | 2162 | 1763 | 399 | 0.288 | -0.334 | 0.617 | -32,663.79 | 10,845.04 | 18,772.50 | 35,091.07 | 0.681 | 10 | 23.63 | 0.011 |
| sensibilidad: tamaño fijo 1 contrato | total | 2162 | 1763 | 399 | 0.288 | -0.334 | 0.697 | -1,572.26 | 494.76 | 857.50 | 1,869.08 | 0.037 | 10 | 23.63 | 0.011 |

## Bootstrap (completa)
- iid: R total p5/p50/p95 = -177.4 / -133.0 / -86.8; drawdown máx. en R p50/p95 = 137.7 / 180.4; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 176.9
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Bootstrap (sin_filtro_1h)
- iid: R total p5/p50/p95 = -561.2 / -480.5 / -401.0; drawdown máx. en R p50/p95 = 484.8 / 564.6; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 558.8
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Desglose (completa)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 60 | -1,012.97 | -0.220 | 0.333 |
| 2019 | 49 | -2,351.25 | -0.550 | 0.245 |
| 2020 | 52 | -1,447.34 | -0.314 | 0.288 |
| 2021 | 51 | -1,735.19 | -0.416 | 0.255 |
| 2022 | 34 | -1,330.35 | -0.471 | 0.235 |
| 2023 | 49 | -1,166.82 | -0.319 | 0.306 |
| 2024 | 41 | -707.54 | -0.203 | 0.317 |
| 2025 | 36 | -1,060.67 | -0.399 | 0.250 |
| 2026 | 27 | -26.03 | -0.050 | 0.370 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 35 | -52.51 | -0.058 | 0.371 |
| 2 | 28 | -881.62 | -0.344 | 0.286 |
| 3 | 28 | -792.08 | -0.404 | 0.250 |
| 4 | 40 | -579.74 | -0.187 | 0.325 |
| 5 | 29 | -1,929.24 | -0.781 | 0.138 |
| 6 | 39 | -621.59 | -0.227 | 0.333 |
| 7 | 32 | -1,156.24 | -0.415 | 0.281 |
| 8 | 43 | -1,390.49 | -0.361 | 0.279 |
| 9 | 26 | -1,112.96 | -0.558 | 0.231 |
| 10 | 36 | -156.32 | -0.088 | 0.361 |
| 11 | 28 | 57.29 | 0.049 | 0.429 |
| 12 | 35 | -2,222.66 | -0.751 | 0.143 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 75 | -2,378.16 | -0.368 | 0.280 |
| Monday | 77 | -1,635.29 | -0.286 | 0.312 |
| Thursday | 73 | -921.05 | -0.190 | 0.329 |
| Tuesday | 73 | -1,897.18 | -0.341 | 0.288 |
| Wednesday | 101 | -4,006.48 | -0.445 | 0.248 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 150 | -3,333.42 | -0.291 | 0.293 |
| largo | 249 | -7,504.74 | -0.360 | 0.285 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 5 | -76.00 | -0.135 | 0.600 |
| objetivo | 110 | 17,839.32 | 1.89 | 1.00 |
| objetivo_hueco | 2 | 378.94 | 1.88 | 1.00 |
| stop | 282 | -28,980.42 | -1.22 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 97 | -2,616.04 | -0.300 | 0.289 |
| baja | 149 | -6,046.57 | -0.500 | 0.248 |
| media | 132 | -2,467.46 | -0.241 | 0.311 |
| sin_historial | 21 | 291.91 | 0.096 | 0.429 |

## Desglose (sin_filtro_1h)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 170 | -5,903.41 | -0.399 | 0.276 |
| 2019 | 163 | -6,844.39 | -0.556 | 0.227 |
| 2020 | 134 | -4,545.07 | -0.512 | 0.224 |
| 2021 | 146 | -3,327.89 | -0.432 | 0.253 |
| 2022 | 120 | -2,619.27 | -0.444 | 0.242 |
| 2023 | 149 | -2,497.80 | -0.362 | 0.282 |
| 2024 | 156 | -1,518.77 | -0.215 | 0.314 |
| 2025 | 123 | -1,013.91 | -0.231 | 0.309 |
| 2026 | 81 | -877.70 | -0.277 | 0.296 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 115 | -2,295.91 | -0.332 | 0.287 |
| 2 | 93 | -2,992.47 | -0.479 | 0.237 |
| 3 | 100 | -2,189.93 | -0.403 | 0.260 |
| 4 | 96 | -3,247.26 | -0.563 | 0.208 |
| 5 | 112 | -3,484.72 | -0.479 | 0.232 |
| 6 | 104 | -2,809.18 | -0.431 | 0.260 |
| 7 | 115 | -3,086.14 | -0.438 | 0.261 |
| 8 | 114 | -1,577.77 | -0.218 | 0.325 |
| 9 | 97 | -1,738.90 | -0.334 | 0.289 |
| 10 | 112 | -2,028.69 | -0.346 | 0.277 |
| 11 | 87 | -1,232.83 | -0.167 | 0.345 |
| 12 | 97 | -2,464.41 | -0.467 | 0.237 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 222 | -4,263.70 | -0.322 | 0.288 |
| Monday | 226 | -5,364.85 | -0.390 | 0.274 |
| Thursday | 250 | -5,199.79 | -0.336 | 0.280 |
| Tuesday | 260 | -6,940.70 | -0.491 | 0.235 |
| Wednesday | 284 | -7,379.17 | -0.389 | 0.268 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 523 | -11,653.82 | -0.372 | 0.270 |
| largo | 719 | -17,494.39 | -0.399 | 0.267 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 9 | -117.22 | -0.255 | 0.333 |
| objetivo | 325 | 34,612.50 | 1.89 | 1.00 |
| objetivo_hueco | 5 | 620.36 | 1.88 | 1.00 |
| stop | 903 | -64,263.85 | -1.22 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 275 | -6,947.57 | -0.437 | 0.244 |
| baja | 472 | -11,632.21 | -0.411 | 0.269 |
| media | 436 | -8,610.03 | -0.337 | 0.280 |
| sin_historial | 59 | -1,958.40 | -0.350 | 0.288 |

## Archivos
- `operaciones_*.csv`: cada operación (sesgo, OR, ruptura, retesteo, entrada, stop, objetivo, contratos, riesgo, salida, bruto, comisiones, slippage, neto en USD y R, avisos)
- `sesiones_*.csv` y `sesiones_excluidas_y_descartadas_*.csv`: estado y motivo de cada sesión
- `resumen.csv`, `bootstrap.json`, `manifest.json` (configuración, datos y versión del código)
- `capital_y_drawdown.png`, `distribucion_R.png`