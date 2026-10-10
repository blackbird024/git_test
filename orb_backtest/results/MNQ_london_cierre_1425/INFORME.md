# Informe ORB + estructura 1h + entrada 5m — MNQ london_cierre_1425

Zona horaria Europe/London; rango 08:00-09:00; entradas hasta 13:00; cierre obligatorio 14:25; calendario XLON.

**Aviso:** resultados de un backtest. No demuestran rentabilidad futura. Costes: comisión 0,62 USD/lado (supuesto no verificado) + 1 tick de slippage por lado.

## Datos
- Archivo: `/home/user/git_test/orb_backtest/data/NQ_5m_databento.csv` (sha256 `3e20c8094b64b4f4…`) — Databento GLBX.MDP3 NQ.c.0 (continuo por calendario, SIN ajuste de rollover), 5 min desde 1 min. Precios de NQ = precios de MNQ (mismo subyacente y tick).
- Filas: 614,269; desde 2018-01-01 23:00:00+00:00 hasta 2026-10-02 21:55:00+01:00
- Avisos de validación: 1 saltos > 8% entre velas consecutivas (¿error de escala o rollover?); 48 sesiones regulares incompletas (1284 velas ausentes; incluye medias jornadas y festivos con Globex abierto)
- Calendario: XNYS (exchange_calendars)
- Velas de 1 h válidas: 51,430 (descartadas por incompletas: 72); pivotes confirmados: {'highs': 6726, 'lows': 6747}
- Periodos (60/20/20 por sesiones): desarrollo 2018-01-02 → 2023-04-04, validacion 2023-04-05 → 2025-01-02, test 2025-01-03 → 2026-10-02

## Resultados: estrategia completa frente a sin filtro 1H (solo cambia el filtro)

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa | total | 2204 | 1975 | 229 | 0.323 | -0.285 | 0.716 | -4,964.40 | 3,794.40 | 2,563.00 | 6,649.70 | 0.133 | 16 | 17.90 | 0.004 |
| completa | desarrollo | 1322 | 1174 | 148 | 0.324 | -0.318 | 0.690 | -3,644.58 | 2,842.08 | 1,913.00 | 3,811.18 | 0.076 | 10 | 19.56 | 0.004 |
| completa | validacion | 440 | 397 | 43 | 0.163 | -0.703 | 0.312 | -2,681.94 | 534.44 | 395.50 | 2,681.94 | 0.058 | 14 | 16.86 | 0.003 |
| completa | test | 442 | 404 | 38 | 0.500 | 0.314 | 1.73 | 1,362.12 | 417.88 | 254.50 | 351.72 | 0.008 | 3 | 12.63 | 0.002 |
| sin_filtro_1h | total | 2204 | 1330 | 874 | 0.278 | -0.446 | 0.560 | -22,784.88 | 11,143.88 | 7,797.00 | 23,854.98 | 0.477 | 19 | 17.16 | 0.013 |
| sin_filtro_1h | desarrollo | 1322 | 747 | 575 | 0.266 | -0.521 | 0.513 | -18,943.28 | 8,986.28 | 6,287.50 | 19,124.66 | 0.382 | 16 | 17.48 | 0.015 |
| sin_filtro_1h | validacion | 440 | 259 | 181 | 0.249 | -0.497 | 0.516 | -4,277.92 | 1,528.92 | 1,104.50 | 4,439.12 | 0.143 | 19 | 15.86 | 0.013 |
| sin_filtro_1h | test | 442 | 324 | 118 | 0.381 | -0.006 | 1.11 | 436.32 | 628.68 | 405.00 | 716.36 | 0.027 | 6 | 17.58 | 0.009 |

## Pruebas de estrés de costes y sensibilidad

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa · costes slippage_2_ticks | total | 2204 | 1975 | 229 | 0.301 | -0.373 | 0.606 | -6,911.52 | 3,190.52 | 4,372.00 | 8,120.98 | 0.162 | 16 | 20.04 | 0.004 |
| completa · costes slippage_2_ticks | desarrollo | 1322 | 1174 | 148 | 0.297 | -0.422 | 0.565 | -5,211.32 | 2,378.32 | 3,260.00 | 5,367.12 | 0.107 | 10 | 22.74 | 0.005 |
| completa · costes slippage_2_ticks | validacion | 440 | 397 | 43 | 0.163 | -0.733 | 0.297 | -2,598.32 | 456.32 | 677.00 | 2,598.32 | 0.058 | 14 | 16.98 | 0.003 |
| completa · costes slippage_2_ticks | test | 442 | 404 | 38 | 0.474 | 0.226 | 1.48 | 898.12 | 355.88 | 435.00 | 459.22 | 0.011 | 4 | 13.03 | 0.002 |
| sin_filtro_1h · costes slippage_2_ticks | total | 2204 | 1331 | 873 | 0.259 | -0.534 | 0.486 | -25,467.58 | 9,073.08 | 12,869.00 | 26,142.26 | 0.523 | 19 | 17.98 | 0.014 |
| sin_filtro_1h · costes slippage_2_ticks | desarrollo | 1322 | 749 | 573 | 0.243 | -0.619 | 0.434 | -21,468.58 | 7,337.08 | 10,433.00 | 21,554.66 | 0.431 | 16 | 18.55 | 0.016 |
| sin_filtro_1h · costes slippage_2_ticks | validacion | 440 | 259 | 181 | 0.249 | -0.521 | 0.495 | -3,961.02 | 1,206.52 | 1,742.00 | 4,099.92 | 0.144 | 19 | 16.08 | 0.013 |
| sin_filtro_1h · costes slippage_2_ticks | test | 442 | 323 | 119 | 0.353 | -0.143 | 0.990 | -37.98 | 529.48 | 694.00 | 817.08 | 0.033 | 10 | 18.11 | 0.010 |
| completa · costes slippage_3_ticks_comision_x2 | total | 2204 | 1975 | 229 | 0.284 | -0.611 | 0.467 | -9,148.08 | 4,764.08 | 4,977.00 | 9,830.60 | 0.197 | 16 | 21.29 | 0.004 |
| completa · costes slippage_3_ticks_comision_x2 | desarrollo | 1322 | 1174 | 148 | 0.270 | -0.714 | 0.410 | -7,039.06 | 3,526.56 | 3,708.00 | 7,039.06 | 0.141 | 10 | 24.12 | 0.005 |
| completa · costes slippage_3_ticks_comision_x2 | validacion | 440 | 397 | 43 | 0.163 | -0.883 | 0.258 | -2,579.36 | 699.36 | 778.50 | 2,579.36 | 0.060 | 14 | 17.56 | 0.003 |
| completa · costes slippage_3_ticks_comision_x2 | test | 442 | 404 | 38 | 0.474 | 0.096 | 1.27 | 470.34 | 538.16 | 490.50 | 489.68 | 0.012 | 4 | 14.47 | 0.002 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | total | 2204 | 1338 | 866 | 0.244 | -0.783 | 0.358 | -29,551.94 | 12,903.44 | 13,864.50 | 29,620.06 | 0.592 | 19 | 18.24 | 0.014 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | desarrollo | 1322 | 749 | 573 | 0.229 | -0.874 | 0.317 | -24,683.64 | 10,522.64 | 11,344.50 | 24,746.76 | 0.495 | 16 | 19.27 | 0.016 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | validacion | 440 | 258 | 182 | 0.242 | -0.753 | 0.425 | -3,911.48 | 1,676.48 | 1,818.00 | 4,027.20 | 0.159 | 19 | 16.62 | 0.013 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | test | 442 | 331 | 111 | 0.324 | -0.357 | 0.690 | -956.82 | 704.32 | 702.00 | 1,089.32 | 0.051 | 9 | 15.63 | 0.008 |
| sensibilidad: riesgo 0.50% | total | 2204 | 1975 | 229 | 0.323 | -0.285 | 0.723 | -9,346.14 | 7,360.64 | 4,971.00 | 12,415.54 | 0.247 | 16 | 17.90 | 0.004 |
| sensibilidad: riesgo 1.00% | total | 2204 | 1975 | 229 | 0.323 | -0.285 | 0.713 | -17,533.90 | 13,528.40 | 9,144.50 | 22,461.96 | 0.444 | 16 | 17.90 | 0.004 |
| sensibilidad: tamaño fijo 1 contrato | total | 2204 | 1975 | 229 | 0.323 | -0.285 | 0.809 | -392.96 | 283.96 | 192.00 | 752.12 | 0.015 | 16 | 17.90 | 0.004 |

## Bootstrap (completa)
- iid: R total p5/p50/p95 = -100.4 / -65.5 / -29.1; drawdown máx. en R p50/p95 = 71.4 / 104.3; P(R total < 0) = 99.9%
- bloques de 5: P(R total < 0) = 99.9%; dd máx. R p95 = 100.3
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Bootstrap (sin_filtro_1h)
- iid: R total p5/p50/p95 = -456.2 / -390.6 / -322.0; drawdown máx. en R p50/p95 = 393.8 / 459.5; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 463.4
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Desglose (completa)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 35 | 23.10 | -0.031 | 0.457 |
| 2019 | 35 | -1,071.44 | -0.489 | 0.286 |
| 2020 | 28 | -776.64 | -0.386 | 0.286 |
| 2021 | 28 | -951.12 | -0.350 | 0.286 |
| 2022 | 16 | -662.42 | -0.422 | 0.250 |
| 2023 | 36 | -2,354.58 | -0.714 | 0.167 |
| 2024 | 13 | -533.42 | -0.461 | 0.231 |
| 2025 | 21 | 864.28 | 0.391 | 0.524 |
| 2026 | 17 | 497.84 | 0.219 | 0.471 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 19 | -356.72 | -0.179 | 0.368 |
| 2 | 15 | -511.88 | -0.275 | 0.333 |
| 3 | 13 | -323.00 | -0.368 | 0.308 |
| 4 | 20 | -1,270.20 | -0.750 | 0.150 |
| 5 | 18 | -623.62 | -0.378 | 0.278 |
| 6 | 23 | -591.22 | -0.460 | 0.261 |
| 7 | 25 | -1,264.18 | -0.576 | 0.240 |
| 8 | 13 | 599.78 | 0.408 | 0.538 |
| 9 | 27 | -488.10 | -0.253 | 0.370 |
| 10 | 19 | 216.74 | 0.132 | 0.421 |
| 11 | 16 | -779.36 | -0.710 | 0.188 |
| 12 | 21 | 427.36 | 0.198 | 0.476 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 42 | -722.04 | -0.269 | 0.310 |
| Monday | 39 | -1,026.96 | -0.333 | 0.308 |
| Thursday | 42 | 1,155.22 | 0.244 | 0.500 |
| Tuesday | 53 | -2,748.10 | -0.611 | 0.226 |
| Wednesday | 53 | -1,622.52 | -0.356 | 0.302 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 80 | -1,708.80 | -0.289 | 0.312 |
| largo | 149 | -3,255.60 | -0.283 | 0.329 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| objetivo | 72 | 11,920.68 | 1.80 | 1.00 |
| objetivo_hueco | 2 | 622.76 | 1.81 | 1.00 |
| stop | 155 | -17,507.84 | -1.28 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 60 | -654.28 | -0.149 | 0.350 |
| baja | 82 | -1,612.08 | -0.267 | 0.341 |
| media | 77 | -2,258.14 | -0.381 | 0.286 |
| sin_historial | 10 | -439.90 | -0.515 | 0.300 |

## Desglose (sin_filtro_1h)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 141 | -5,857.56 | -0.567 | 0.284 |
| 2019 | 136 | -5,598.84 | -0.645 | 0.243 |
| 2020 | 94 | -3,030.34 | -0.565 | 0.245 |
| 2021 | 102 | -2,403.36 | -0.404 | 0.284 |
| 2022 | 75 | -1,830.56 | -0.471 | 0.240 |
| 2023 | 120 | -3,315.10 | -0.536 | 0.233 |
| 2024 | 87 | -1,258.20 | -0.342 | 0.299 |
| 2025 | 66 | -159.88 | -0.071 | 0.364 |
| 2026 | 53 | 668.96 | 0.113 | 0.415 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 73 | -2,892.20 | -0.509 | 0.260 |
| 2 | 69 | -1,024.02 | -0.163 | 0.362 |
| 3 | 63 | -1,121.32 | -0.396 | 0.302 |
| 4 | 70 | -3,900.32 | -0.959 | 0.129 |
| 5 | 73 | -2,192.00 | -0.477 | 0.260 |
| 6 | 77 | -447.56 | -0.251 | 0.351 |
| 7 | 91 | -3,381.36 | -0.587 | 0.242 |
| 8 | 76 | -1,788.40 | -0.417 | 0.276 |
| 9 | 77 | -1,405.26 | -0.380 | 0.299 |
| 10 | 67 | -980.32 | -0.232 | 0.328 |
| 11 | 68 | -1,224.38 | -0.315 | 0.309 |
| 12 | 70 | -2,427.74 | -0.630 | 0.229 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 168 | -4,713.70 | -0.538 | 0.256 |
| Monday | 159 | -6,136.70 | -0.597 | 0.233 |
| Thursday | 173 | -709.28 | -0.146 | 0.376 |
| Tuesday | 184 | -4,755.22 | -0.425 | 0.277 |
| Wednesday | 190 | -6,469.98 | -0.535 | 0.247 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 388 | -14,065.86 | -0.612 | 0.222 |
| largo | 486 | -8,719.02 | -0.314 | 0.323 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 1 | 57.86 | 0.584 | 1.00 |
| objetivo | 240 | 28,360.60 | 1.81 | 1.00 |
| objetivo_hueco | 2 | 546.20 | 1.81 | 1.00 |
| stop | 629 | -51,409.46 | -1.31 | 0.000 |
| stop_hueco | 2 | -340.08 | -2.67 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 237 | -4,847.62 | -0.340 | 0.295 |
| baja | 299 | -9,023.62 | -0.514 | 0.271 |
| media | 291 | -6,825.60 | -0.441 | 0.271 |
| sin_historial | 47 | -2,088.04 | -0.589 | 0.277 |

## Archivos
- `operaciones_*.csv`: cada operación (sesgo, OR, ruptura, retesteo, entrada, stop, objetivo, contratos, riesgo, salida, bruto, comisiones, slippage, neto en USD y R, avisos)
- `sesiones_*.csv` y `sesiones_excluidas_y_descartadas_*.csv`: estado y motivo de cada sesión
- `resumen.csv`, `bootstrap.json`, `manifest.json` (configuración, datos y versión del código)
- `capital_y_drawdown.png`, `distribucion_R.png`