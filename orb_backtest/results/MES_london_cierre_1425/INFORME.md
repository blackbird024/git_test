# Informe ORB + estructura 1h + entrada 5m — MES london_cierre_1425

Zona horaria Europe/London; rango 08:00-09:00; entradas hasta 13:00; cierre obligatorio 14:25; calendario XLON.

**Aviso:** resultados de un backtest. No demuestran rentabilidad futura. Costes: comisión 0,62 USD/lado (supuesto no verificado) + 1 tick de slippage por lado.

## Datos
- Archivo: `/home/user/git_test/orb_backtest/data/ES_5m_databento.csv` (sha256 `15da2be41380dd74…`) — Databento GLBX.MDP3 ES (archivo dbn_ES_5m.pkl de una descarga anterior; se SUPONE ES.c.0 continuo por calendario sin ajuste, no verificado), 5 min desde 1 min. Precios de ES = precios de MES (mismo subyacente y tick).
- Filas: 614,628; desde 2018-01-01 23:00:00+00:00 hasta 2026-10-02 21:55:00+01:00
- Avisos de validación: 1 saltos > 8% entre velas consecutivas (¿error de escala o rollover?); 47 sesiones regulares incompletas (1192 velas ausentes; incluye medias jornadas y festivos con Globex abierto)
- Calendario: XNYS (exchange_calendars)
- Velas de 1 h válidas: 51,445 (descartadas por incompletas: 86); pivotes confirmados: {'highs': 6309, 'lows': 6466}
- Periodos (60/20/20 por sesiones): desarrollo 2018-01-02 → 2023-04-04, validacion 2023-04-05 → 2025-01-02, test 2025-01-03 → 2026-10-02

## Resultados: estrategia completa frente a sin filtro 1H (solo cambia el filtro)

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa | total | 2207 | 1780 | 427 | 0.241 | -0.550 | 0.464 | -16,592.64 | 4,632.64 | 8,322.50 | 16,761.48 | 0.335 | 17 | 28.78 | 0.011 |
| completa | desarrollo | 1325 | 1046 | 279 | 0.233 | -0.589 | 0.443 | -12,197.88 | 3,362.88 | 6,065.00 | 12,265.63 | 0.245 | 11 | 29.28 | 0.012 |
| completa | validacion | 440 | 358 | 82 | 0.256 | -0.500 | 0.507 | -2,590.09 | 763.84 | 1,371.25 | 2,649.38 | 0.070 | 17 | 32.13 | 0.012 |
| completa | test | 442 | 376 | 66 | 0.258 | -0.448 | 0.524 | -1,804.67 | 505.92 | 886.25 | 2,066.49 | 0.059 | 13 | 22.50 | 0.007 |
| sin_filtro_1h | total | 2207 | 696 | 1511 | 0.244 | -0.539 | 0.458 | -37,216.08 | 10,716.08 | 19,208.75 | 37,267.40 | 0.745 | 20 | 28.95 | 0.039 |
| sin_filtro_1h | desarrollo | 1325 | 411 | 914 | 0.253 | -0.527 | 0.464 | -27,803.87 | 8,355.12 | 14,982.50 | 28,084.27 | 0.562 | 20 | 31.39 | 0.042 |
| sin_filtro_1h | validacion | 440 | 112 | 328 | 0.238 | -0.550 | 0.455 | -5,717.64 | 1,532.64 | 2,732.50 | 5,717.64 | 0.258 | 12 | 29.54 | 0.043 |
| sin_filtro_1h | test | 442 | 173 | 269 | 0.223 | -0.567 | 0.412 | -3,694.57 | 828.32 | 1,493.75 | 3,745.89 | 0.227 | 19 | 19.94 | 0.024 |

## Pruebas de estrés de costes y sensibilidad

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa · costes slippage_2_ticks | total | 2207 | 1780 | 427 | 0.208 | -0.716 | 0.361 | -19,470.37 | 3,519.12 | 12,847.50 | 19,594.15 | 0.392 | 17 | 33.97 | 0.013 |
| completa · costes slippage_2_ticks | desarrollo | 1325 | 1046 | 279 | 0.208 | -0.731 | 0.358 | -13,949.20 | 2,579.20 | 9,407.50 | 14,001.91 | 0.280 | 14 | 34.25 | 0.014 |
| completa · costes slippage_2_ticks | validacion | 440 | 358 | 82 | 0.195 | -0.762 | 0.331 | -3,490.43 | 566.68 | 2,105.00 | 3,509.31 | 0.097 | 17 | 38.11 | 0.014 |
| completa · costes slippage_2_ticks | test | 442 | 376 | 66 | 0.227 | -0.594 | 0.425 | -2,030.74 | 373.24 | 1,335.00 | 2,224.86 | 0.068 | 13 | 27.65 | 0.008 |
| sin_filtro_1h · costes slippage_2_ticks | total | 2207 | 712 | 1495 | 0.214 | -0.698 | 0.360 | -39,594.75 | 7,471.00 | 27,275.00 | 39,639.79 | 0.793 | 25 | 32.29 | 0.043 |
| sin_filtro_1h · costes slippage_2_ticks | desarrollo | 1325 | 412 | 913 | 0.218 | -0.697 | 0.363 | -31,217.55 | 6,038.80 | 22,075.00 | 31,359.08 | 0.627 | 22 | 35.31 | 0.048 |
| sin_filtro_1h · costes slippage_2_ticks | validacion | 440 | 114 | 326 | 0.212 | -0.702 | 0.342 | -5,468.67 | 939.92 | 3,412.50 | 5,468.67 | 0.291 | 13 | 32.45 | 0.047 |
| sin_filtro_1h · costes slippage_2_ticks | test | 442 | 186 | 256 | 0.203 | -0.699 | 0.366 | -2,908.53 | 492.28 | 1,787.50 | 2,953.57 | 0.222 | 25 | 21.33 | 0.024 |
| completa · costes slippage_3_ticks_comision_x2 | total | 2207 | 1780 | 427 | 0.178 | -0.979 | 0.247 | -22,040.67 | 5,031.92 | 14,047.50 | 22,125.71 | 0.443 | 20 | 37.92 | 0.014 |
| completa · costes slippage_3_ticks_comision_x2 | desarrollo | 1325 | 1046 | 279 | 0.168 | -1.03 | 0.231 | -16,471.21 | 3,724.96 | 10,440.00 | 16,516.49 | 0.330 | 16 | 39.32 | 0.016 |
| completa · costes slippage_3_ticks_comision_x2 | validacion | 440 | 358 | 82 | 0.171 | -1.00 | 0.245 | -3,597.37 | 791.12 | 2,223.75 | 3,597.37 | 0.107 | 19 | 40.79 | 0.015 |
| completa · costes slippage_3_ticks_comision_x2 | test | 442 | 376 | 66 | 0.227 | -0.735 | 0.363 | -1,972.09 | 515.84 | 1,383.75 | 2,092.55 | 0.070 | 13 | 28.41 | 0.008 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | total | 2207 | 770 | 1437 | 0.184 | -0.967 | 0.247 | -41,310.38 | 9,872.88 | 27,517.50 | 41,326.71 | 0.827 | 32 | 36.10 | 0.046 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | desarrollo | 1325 | 414 | 911 | 0.187 | -0.965 | 0.247 | -34,212.15 | 8,258.40 | 23,051.25 | 34,254.93 | 0.685 | 32 | 39.19 | 0.053 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | validacion | 440 | 122 | 318 | 0.179 | -0.965 | 0.250 | -4,754.93 | 1,093.68 | 3,030.00 | 4,754.93 | 0.301 | 19 | 36.43 | 0.052 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | test | 442 | 234 | 208 | 0.178 | -0.975 | 0.247 | -2,343.30 | 520.80 | 1,436.25 | 2,359.63 | 0.214 | 23 | 22.04 | 0.020 |
| sensibilidad: riesgo 0.50% | total | 2207 | 1780 | 427 | 0.241 | -0.550 | 0.460 | -28,183.75 | 7,905.00 | 14,217.50 | 28,447.63 | 0.569 | 17 | 28.78 | 0.011 |
| sensibilidad: riesgo 1.00% | total | 2207 | 1780 | 427 | 0.241 | -0.550 | 0.451 | -40,700.68 | 11,540.68 | 20,800.00 | 40,884.54 | 0.818 | 17 | 28.78 | 0.011 |
| sensibilidad: tamaño fijo 1 contrato | total | 2207 | 1780 | 427 | 0.241 | -0.550 | 0.546 | -1,899.48 | 529.48 | 940.00 | 1,955.76 | 0.039 | 17 | 28.78 | 0.011 |

## Bootstrap (completa)
- iid: R total p5/p50/p95 = -280.9 / -235.5 / -190.2; drawdown máx. en R p50/p95 = 238.0 / 283.0; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 284.0
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Bootstrap (sin_filtro_1h)
- iid: R total p5/p50/p95 = -902.5 / -816.1 / -724.8; drawdown máx. en R p50/p95 = 819.0 / 904.8; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 906.0
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Desglose (completa)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 52 | -2,754.77 | -0.744 | 0.212 |
| 2019 | 60 | -3,046.23 | -0.652 | 0.233 |
| 2020 | 51 | -952.01 | -0.298 | 0.314 |
| 2021 | 53 | -2,746.43 | -0.649 | 0.208 |
| 2022 | 49 | -2,102.03 | -0.575 | 0.204 |
| 2023 | 56 | -1,487.05 | -0.402 | 0.286 |
| 2024 | 40 | -1,699.45 | -0.678 | 0.200 |
| 2025 | 35 | -1,080.29 | -0.539 | 0.229 |
| 2026 | 31 | -724.38 | -0.345 | 0.290 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 30 | -2,145.79 | -1.02 | 0.100 |
| 2 | 31 | -1,249.49 | -0.508 | 0.258 |
| 3 | 36 | -1,403.28 | -0.500 | 0.250 |
| 4 | 28 | -2,078.68 | -1.12 | 0.071 |
| 5 | 44 | -498.87 | -0.210 | 0.341 |
| 6 | 38 | -2,196.68 | -0.799 | 0.158 |
| 7 | 47 | -1,747.04 | -0.497 | 0.255 |
| 8 | 34 | -456.69 | -0.334 | 0.324 |
| 9 | 38 | -1,212.85 | -0.407 | 0.289 |
| 10 | 38 | -902.39 | -0.332 | 0.289 |
| 11 | 36 | -1,550.88 | -0.595 | 0.222 |
| 12 | 27 | -1,150.00 | -0.564 | 0.259 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 88 | -3,852.52 | -0.632 | 0.216 |
| Monday | 92 | -5,047.93 | -0.727 | 0.185 |
| Thursday | 64 | -2,118.20 | -0.469 | 0.266 |
| Tuesday | 100 | -889.85 | -0.174 | 0.360 |
| Wednesday | 83 | -4,684.14 | -0.782 | 0.169 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 156 | -4,311.58 | -0.394 | 0.282 |
| largo | 271 | -12,281.06 | -0.640 | 0.218 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 2 | -2.34 | 0.044 | 0.500 |
| objetivo | 97 | 13,621.48 | 1.87 | 1.00 |
| objetivo_hueco | 5 | 654.16 | 1.85 | 1.00 |
| stop | 321 | -30,678.58 | -1.32 | 0.000 |
| stop_hueco | 2 | -187.36 | -1.22 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 139 | -6,944.09 | -0.690 | 0.187 |
| baja | 152 | -4,284.15 | -0.415 | 0.296 |
| media | 125 | -4,077.21 | -0.478 | 0.256 |
| sin_historial | 11 | -1,287.19 | -1.46 | 0.000 |

## Desglose (sin_filtro_1h)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 207 | -11,582.89 | -0.776 | 0.193 |
| 2019 | 192 | -7,398.38 | -0.650 | 0.240 |
| 2020 | 151 | -1,402.26 | -0.218 | 0.331 |
| 2021 | 165 | -3,841.91 | -0.487 | 0.261 |
| 2022 | 157 | -2,746.57 | -0.405 | 0.261 |
| 2023 | 190 | -3,694.44 | -0.539 | 0.242 |
| 2024 | 180 | -2,855.06 | -0.543 | 0.239 |
| 2025 | 152 | -1,893.30 | -0.470 | 0.257 |
| 2026 | 117 | -1,801.27 | -0.694 | 0.179 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 131 | -4,401.37 | -0.741 | 0.183 |
| 2 | 111 | -2,635.79 | -0.512 | 0.261 |
| 3 | 122 | -1,735.76 | -0.182 | 0.328 |
| 4 | 126 | -3,701.02 | -0.722 | 0.190 |
| 5 | 129 | -1,958.17 | -0.414 | 0.279 |
| 6 | 130 | -3,552.45 | -0.599 | 0.223 |
| 7 | 150 | -3,488.64 | -0.496 | 0.267 |
| 8 | 121 | -3,316.72 | -0.646 | 0.215 |
| 9 | 127 | -3,366.78 | -0.546 | 0.244 |
| 10 | 133 | -2,799.62 | -0.444 | 0.271 |
| 11 | 112 | -2,727.44 | -0.498 | 0.259 |
| 12 | 119 | -3,532.32 | -0.670 | 0.210 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 305 | -7,395.05 | -0.558 | 0.230 |
| Monday | 261 | -9,116.68 | -0.666 | 0.207 |
| Thursday | 322 | -8,113.24 | -0.528 | 0.248 |
| Tuesday | 320 | -5,266.75 | -0.422 | 0.284 |
| Wednesday | 303 | -7,324.36 | -0.548 | 0.244 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 645 | -15,832.28 | -0.525 | 0.248 |
| largo | 866 | -21,383.80 | -0.550 | 0.241 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 10 | 152.90 | 0.329 | 0.700 |
| objetivo | 341 | 28,575.38 | 1.86 | 1.00 |
| objetivo_hueco | 21 | 2,581.29 | 2.28 | 1.00 |
| stop | 1133 | -68,167.25 | -1.32 | 0.000 |
| stop_hueco | 6 | -358.40 | -1.31 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 413 | -7,762.22 | -0.422 | 0.264 |
| baja | 540 | -15,399.36 | -0.614 | 0.231 |
| media | 497 | -10,136.00 | -0.521 | 0.249 |
| sin_historial | 61 | -3,918.50 | -0.821 | 0.180 |

## Archivos
- `operaciones_*.csv`: cada operación (sesgo, OR, ruptura, retesteo, entrada, stop, objetivo, contratos, riesgo, salida, bruto, comisiones, slippage, neto en USD y R, avisos)
- `sesiones_*.csv` y `sesiones_excluidas_y_descartadas_*.csv`: estado y motivo de cada sesión
- `resumen.csv`, `bootstrap.json`, `manifest.json` (configuración, datos y versión del código)
- `capital_y_drawdown.png`, `distribucion_R.png`