# Informe ORB 1h + estructura 1h + entrada 5m — MNQ

**Aviso:** resultados de un backtest. No demuestran rentabilidad futura. Costes: comisión 0,62 USD/lado (supuesto no verificado) + 1 tick de slippage por lado.

## Datos
- Archivo: `/home/user/git_test/orb_backtest/data/NQ_5m_databento.csv` (sha256 `3e20c8094b64b4f4…`) — Databento GLBX.MDP3 NQ.c.0 (continuo por calendario, SIN ajuste de rollover), 5 min desde 1 min. Precios de NQ = precios de MNQ (mismo subyacente y tick).
- Filas: 614,269; desde 2018-01-01 18:00:00-05:00 hasta 2026-10-02 16:55:00-04:00
- Avisos de validación: 1 saltos > 8% entre velas consecutivas (¿error de escala o rollover?); 81 sesiones regulares incompletas (2765 velas ausentes; incluye medias jornadas y festivos con Globex abierto)
- Calendario: XNYS (exchange_calendars)
- Velas de 1 h válidas: 51,430 (descartadas por incompletas: 72); pivotes confirmados: {'highs': 6726, 'lows': 6747}
- Periodos (60/20/20 por sesiones): desarrollo 2018-01-02 → 2023-03-31, validacion 2023-04-03 → 2024-12-31, test 2025-01-02 → 2026-10-02

## Resultados: estrategia completa frente a sin filtro 1H (solo cambia el filtro)

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa | total | 2162 | 2005 | 157 | 0.318 | -0.244 | 0.730 | -3,334.58 | 2,129.08 | 1,483.50 | 4,248.46 | 0.084 | 10 | 16.15 | 0.003 |
| completa | desarrollo | 1297 | 1190 | 107 | 0.336 | -0.221 | 0.765 | -1,989.02 | 1,702.52 | 1,170.00 | 2,594.88 | 0.051 | 10 | 16.12 | 0.003 |
| completa | validacion | 433 | 404 | 29 | 0.241 | -0.441 | 0.538 | -1,181.32 | 301.32 | 233.00 | 1,342.84 | 0.028 | 6 | 16.55 | 0.003 |
| completa | test | 432 | 411 | 21 | 0.333 | -0.087 | 0.875 | -164.24 | 125.24 | 80.50 | 836.34 | 0.018 | 9 | 15.71 | 0.002 |
| sin_filtro_1h | total | 2162 | 1659 | 503 | 0.268 | -0.376 | 0.602 | -14,135.08 | 5,446.08 | 3,893.50 | 14,304.48 | 0.286 | 18 | 15.60 | 0.009 |
| sin_filtro_1h | desarrollo | 1297 | 959 | 338 | 0.260 | -0.418 | 0.568 | -11,082.14 | 4,229.64 | 3,012.00 | 11,416.94 | 0.228 | 18 | 17.01 | 0.011 |
| sin_filtro_1h | validacion | 433 | 333 | 100 | 0.280 | -0.305 | 0.656 | -2,174.22 | 778.72 | 569.50 | 2,557.34 | 0.065 | 10 | 12.90 | 0.008 |
| sin_filtro_1h | test | 432 | 367 | 65 | 0.292 | -0.267 | 0.751 | -878.72 | 437.72 | 312.00 | 1,236.72 | 0.033 | 8 | 12.38 | 0.005 |

## Pruebas de estrés de costes y sensibilidad

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa · costes slippage_2_ticks | total | 2162 | 2005 | 157 | 0.306 | -0.305 | 0.669 | -4,089.84 | 1,848.84 | 2,599.00 | 4,718.78 | 0.094 | 10 | 16.40 | 0.003 |
| completa · costes slippage_2_ticks | desarrollo | 1297 | 1190 | 107 | 0.318 | -0.302 | 0.694 | -2,630.86 | 1,474.36 | 2,049.00 | 2,951.84 | 0.059 | 10 | 16.50 | 0.003 |
| completa · costes slippage_2_ticks | validacion | 433 | 404 | 29 | 0.241 | -0.464 | 0.473 | -1,290.16 | 259.16 | 401.00 | 1,453.68 | 0.031 | 6 | 16.55 | 0.003 |
| completa · costes slippage_2_ticks | test | 432 | 411 | 21 | 0.333 | -0.099 | 0.871 | -168.82 | 115.32 | 149.00 | 848.86 | 0.018 | 9 | 15.71 | 0.002 |
| sin_filtro_1h · costes slippage_2_ticks | total | 2162 | 1662 | 500 | 0.260 | -0.426 | 0.557 | -15,497.56 | 4,735.56 | 6,796.00 | 15,660.16 | 0.313 | 18 | 16.11 | 0.010 |
| sin_filtro_1h · costes slippage_2_ticks | desarrollo | 1297 | 961 | 336 | 0.250 | -0.476 | 0.525 | -12,159.78 | 3,685.28 | 5,275.00 | 12,492.78 | 0.250 | 18 | 17.59 | 0.012 |
| sin_filtro_1h · costes slippage_2_ticks | validacion | 433 | 333 | 100 | 0.270 | -0.356 | 0.616 | -2,328.08 | 672.08 | 981.00 | 2,700.90 | 0.071 | 10 | 13.35 | 0.008 |
| sin_filtro_1h · costes slippage_2_ticks | test | 432 | 368 | 64 | 0.297 | -0.276 | 0.699 | -1,009.70 | 378.20 | 540.00 | 1,327.16 | 0.037 | 8 | 12.66 | 0.005 |
| completa · costes slippage_3_ticks_comision_x2 | total | 2162 | 2005 | 157 | 0.287 | -0.512 | 0.530 | -5,728.58 | 2,842.08 | 3,036.00 | 5,981.86 | 0.120 | 10 | 17.61 | 0.003 |
| completa · costes slippage_3_ticks_comision_x2 | desarrollo | 1297 | 1190 | 107 | 0.290 | -0.559 | 0.523 | -4,086.92 | 2,241.92 | 2,377.50 | 4,086.92 | 0.082 | 10 | 17.94 | 0.004 |
| completa · costes slippage_3_ticks_comision_x2 | validacion | 433 | 404 | 29 | 0.241 | -0.583 | 0.440 | -1,319.70 | 409.20 | 472.50 | 1,482.74 | 0.032 | 6 | 17.59 | 0.003 |
| completa · costes slippage_3_ticks_comision_x2 | test | 432 | 411 | 21 | 0.333 | -0.174 | 0.744 | -321.96 | 190.96 | 186.00 | 817.36 | 0.018 | 9 | 15.95 | 0.002 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | total | 2162 | 1662 | 500 | 0.248 | -0.603 | 0.454 | -18,096.34 | 7,149.84 | 7,756.50 | 18,224.86 | 0.364 | 18 | 16.91 | 0.010 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | desarrollo | 1297 | 961 | 336 | 0.232 | -0.684 | 0.410 | -14,585.00 | 5,580.00 | 6,063.00 | 14,834.12 | 0.297 | 18 | 18.62 | 0.012 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | validacion | 433 | 333 | 100 | 0.270 | -0.467 | 0.535 | -2,565.38 | 1,006.88 | 1,098.00 | 2,809.86 | 0.079 | 10 | 13.65 | 0.008 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | test | 432 | 368 | 64 | 0.297 | -0.388 | 0.679 | -945.96 | 562.96 | 595.50 | 1,214.32 | 0.037 | 8 | 13.05 | 0.005 |
| sensibilidad: riesgo 0.50% | total | 2162 | 2005 | 157 | 0.318 | -0.244 | 0.740 | -6,451.10 | 4,265.60 | 2,971.00 | 8,413.18 | 0.164 | 10 | 16.15 | 0.003 |
| sensibilidad: riesgo 1.00% | total | 2162 | 2005 | 157 | 0.318 | -0.244 | 0.746 | -12,242.34 | 8,296.84 | 5,774.00 | 15,954.78 | 0.304 | 10 | 16.15 | 0.003 |
| sensibilidad: tamaño fijo 1 contrato | total | 2162 | 2005 | 157 | 0.318 | -0.244 | 1.03 | 52.82 | 194.68 | 132.00 | 336.66 | 0.007 | 10 | 16.15 | 0.003 |

## Bootstrap (completa)
- iid: R total p5/p50/p95 = -66.9 / -38.1 / -8.6; drawdown máx. en R p50/p95 = 45.0 / 70.9; P(R total < 0) = 98.3%
- bloques de 5: P(R total < 0) = 98.0%; dd máx. R p95 = 70.8
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Bootstrap (sin_filtro_1h)
- iid: R total p5/p50/p95 = -239.5 / -190.6 / -137.2; drawdown máx. en R p50/p95 = 194.5 / 242.8; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 244.3
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Desglose (completa)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 37 | -392.68 | -0.144 | 0.378 |
| 2019 | 31 | -55.84 | -0.106 | 0.387 |
| 2020 | 11 | -58.02 | -0.039 | 0.364 |
| 2021 | 12 | -240.98 | -0.148 | 0.333 |
| 2022 | 14 | -1,031.96 | -0.743 | 0.143 |
| 2023 | 15 | -760.88 | -0.634 | 0.200 |
| 2024 | 16 | -629.98 | -0.357 | 0.250 |
| 2025 | 13 | -435.90 | -0.401 | 0.231 |
| 2026 | 8 | 271.66 | 0.424 | 0.500 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 15 | -1,168.22 | -0.809 | 0.133 |
| 2 | 14 | -23.22 | 0.073 | 0.429 |
| 3 | 14 | -83.18 | -0.077 | 0.357 |
| 4 | 15 | -519.88 | -0.427 | 0.267 |
| 5 | 13 | 34.16 | -0.023 | 0.385 |
| 6 | 15 | -98.10 | -0.116 | 0.333 |
| 7 | 11 | -78.60 | -0.098 | 0.364 |
| 8 | 22 | -1,862.82 | -1.01 | 0.091 |
| 9 | 11 | -131.54 | -0.052 | 0.364 |
| 10 | 10 | 610.38 | 0.657 | 0.600 |
| 11 | 9 | 76.14 | 0.054 | 0.444 |
| 12 | 8 | -89.70 | -0.097 | 0.375 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 25 | -1,055.00 | -0.523 | 0.240 |
| Monday | 34 | 138.40 | -0.006 | 0.412 |
| Thursday | 33 | -1,942.38 | -0.567 | 0.212 |
| Tuesday | 32 | -619.48 | -0.240 | 0.312 |
| Wednesday | 33 | 143.88 | 0.043 | 0.394 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 54 | -2,291.38 | -0.467 | 0.241 |
| largo | 103 | -1,043.20 | -0.126 | 0.359 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| objetivo | 50 | 8,997.92 | 1.88 | 1.00 |
| stop | 107 | -12,332.50 | -1.24 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 29 | -1,127.62 | -0.436 | 0.241 |
| baja | 59 | -1,591.94 | -0.289 | 0.305 |
| media | 53 | -720.42 | -0.178 | 0.340 |
| sin_historial | 16 | 105.40 | 0.055 | 0.438 |

## Desglose (sin_filtro_1h)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 87 | -2,928.34 | -0.397 | 0.276 |
| 2019 | 90 | -3,131.40 | -0.460 | 0.267 |
| 2020 | 56 | -1,391.56 | -0.318 | 0.286 |
| 2021 | 50 | -888.26 | -0.266 | 0.300 |
| 2022 | 40 | -2,241.48 | -0.674 | 0.150 |
| 2023 | 64 | -881.32 | -0.224 | 0.312 |
| 2024 | 51 | -1,794.00 | -0.463 | 0.216 |
| 2025 | 46 | -491.74 | -0.232 | 0.304 |
| 2026 | 19 | -386.98 | -0.353 | 0.263 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 45 | -3,112.66 | -0.874 | 0.111 |
| 2 | 45 | -1,725.72 | -0.428 | 0.244 |
| 3 | 43 | -194.18 | -0.085 | 0.349 |
| 4 | 41 | -1,353.04 | -0.387 | 0.268 |
| 5 | 39 | -1,152.32 | -0.427 | 0.256 |
| 6 | 35 | -293.42 | -0.109 | 0.343 |
| 7 | 35 | -1,066.38 | -0.440 | 0.257 |
| 8 | 55 | -2,638.30 | -0.653 | 0.182 |
| 9 | 49 | -1,208.42 | -0.307 | 0.286 |
| 10 | 36 | 179.62 | 0.007 | 0.389 |
| 11 | 41 | -1,134.22 | -0.415 | 0.268 |
| 12 | 39 | -436.04 | -0.196 | 0.333 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 77 | -3,307.88 | -0.570 | 0.208 |
| Monday | 113 | -1,638.22 | -0.207 | 0.327 |
| Thursday | 106 | -4,336.78 | -0.532 | 0.217 |
| Tuesday | 100 | -2,693.62 | -0.367 | 0.270 |
| Wednesday | 107 | -2,158.58 | -0.269 | 0.299 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 185 | -6,618.02 | -0.458 | 0.238 |
| largo | 318 | -7,517.06 | -0.329 | 0.286 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 2 | -77.94 | -0.452 | 0.000 |
| objetivo | 135 | 21,356.72 | 1.89 | 1.00 |
| stop | 366 | -35,413.86 | -1.21 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 95 | -3,593.70 | -0.500 | 0.211 |
| baja | 190 | -4,449.06 | -0.332 | 0.295 |
| media | 183 | -4,625.08 | -0.345 | 0.273 |
| sin_historial | 35 | -1,467.24 | -0.444 | 0.257 |

## Archivos
- `operaciones_*.csv`: cada operación (sesgo, OR, ruptura, retesteo, entrada, stop, objetivo, contratos, riesgo, salida, bruto, comisiones, slippage, neto en USD y R, avisos)
- `sesiones_*.csv` y `sesiones_excluidas_y_descartadas_*.csv`: estado y motivo de cada sesión
- `resumen.csv`, `bootstrap.json`, `manifest.json` (configuración, datos y versión del código)
- `capital_y_drawdown.png`, `distribucion_R.png`