# Informe ORB + estructura 1h + entrada 5m — MES london_cierre_1625

Zona horaria Europe/London; rango 08:00-09:00; entradas hasta 13:00; cierre obligatorio 16:25; calendario XLON.

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
| completa | total | 2207 | 1780 | 427 | 0.241 | -0.551 | 0.463 | -16,621.41 | 4,630.16 | 8,317.50 | 16,790.25 | 0.336 | 17 | 28.78 | 0.011 |
| completa | desarrollo | 1325 | 1046 | 279 | 0.233 | -0.591 | 0.442 | -12,241.64 | 3,361.64 | 6,062.50 | 12,309.39 | 0.246 | 11 | 29.28 | 0.012 |
| completa | validacion | 440 | 358 | 82 | 0.256 | -0.500 | 0.508 | -2,575.10 | 762.60 | 1,368.75 | 2,634.39 | 0.070 | 17 | 32.13 | 0.012 |
| completa | test | 442 | 376 | 66 | 0.258 | -0.448 | 0.524 | -1,804.67 | 505.92 | 886.25 | 2,066.49 | 0.059 | 13 | 22.50 | 0.007 |
| sin_filtro_1h | total | 2207 | 696 | 1511 | 0.244 | -0.537 | 0.460 | -37,178.47 | 10,729.72 | 19,215.00 | 37,229.79 | 0.745 | 20 | 29.09 | 0.039 |
| sin_filtro_1h | desarrollo | 1325 | 411 | 914 | 0.252 | -0.524 | 0.467 | -27,758.77 | 8,367.52 | 14,986.25 | 28,039.17 | 0.561 | 20 | 31.62 | 0.043 |
| sin_filtro_1h | validacion | 440 | 112 | 328 | 0.238 | -0.550 | 0.455 | -5,725.13 | 1,533.88 | 2,735.00 | 5,725.13 | 0.257 | 12 | 29.54 | 0.043 |
| sin_filtro_1h | test | 442 | 173 | 269 | 0.223 | -0.567 | 0.412 | -3,694.57 | 828.32 | 1,493.75 | 3,745.89 | 0.227 | 19 | 19.94 | 0.024 |

## Pruebas de estrés de costes y sensibilidad

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa · costes slippage_2_ticks | total | 2207 | 1780 | 427 | 0.208 | -0.716 | 0.364 | -19,465.36 | 3,520.36 | 12,832.50 | 19,589.14 | 0.392 | 17 | 33.99 | 0.013 |
| completa · costes slippage_2_ticks | desarrollo | 1325 | 1046 | 279 | 0.208 | -0.730 | 0.362 | -13,929.19 | 2,580.44 | 9,392.50 | 13,981.90 | 0.280 | 14 | 34.27 | 0.014 |
| completa · costes slippage_2_ticks | validacion | 440 | 358 | 82 | 0.195 | -0.762 | 0.331 | -3,490.43 | 566.68 | 2,105.00 | 3,509.31 | 0.097 | 17 | 38.11 | 0.014 |
| completa · costes slippage_2_ticks | test | 442 | 376 | 66 | 0.227 | -0.599 | 0.423 | -2,045.74 | 373.24 | 1,335.00 | 2,239.86 | 0.069 | 13 | 27.73 | 0.008 |
| sin_filtro_1h · costes slippage_2_ticks | total | 2207 | 711 | 1496 | 0.213 | -0.697 | 0.368 | -39,484.49 | 7,503.24 | 27,315.00 | 39,529.53 | 0.791 | 25 | 32.59 | 0.043 |
| sin_filtro_1h · costes slippage_2_ticks | desarrollo | 1325 | 412 | 913 | 0.218 | -0.694 | 0.371 | -31,096.15 | 6,057.40 | 22,072.50 | 31,237.68 | 0.625 | 22 | 35.65 | 0.048 |
| sin_filtro_1h · costes slippage_2_ticks | validacion | 440 | 114 | 326 | 0.209 | -0.706 | 0.345 | -5,498.59 | 949.84 | 3,445.00 | 5,498.59 | 0.291 | 13 | 32.50 | 0.047 |
| sin_filtro_1h · costes slippage_2_ticks | test | 442 | 185 | 257 | 0.202 | -0.700 | 0.374 | -2,889.75 | 496.00 | 1,797.50 | 2,934.79 | 0.219 | 25 | 21.87 | 0.025 |
| completa · costes slippage_3_ticks_comision_x2 | total | 2207 | 1780 | 427 | 0.178 | -0.977 | 0.253 | -22,009.32 | 5,044.32 | 14,028.75 | 22,094.36 | 0.442 | 20 | 37.96 | 0.014 |
| completa · costes slippage_3_ticks_comision_x2 | desarrollo | 1325 | 1046 | 279 | 0.168 | -1.02 | 0.239 | -16,408.63 | 3,734.88 | 10,413.75 | 16,453.91 | 0.329 | 16 | 39.37 | 0.016 |
| completa · costes slippage_3_ticks_comision_x2 | validacion | 440 | 358 | 82 | 0.171 | -1.00 | 0.245 | -3,597.37 | 791.12 | 2,223.75 | 3,597.37 | 0.107 | 19 | 40.79 | 0.015 |
| completa · costes slippage_3_ticks_comision_x2 | test | 442 | 376 | 66 | 0.227 | -0.740 | 0.360 | -2,003.32 | 518.32 | 1,391.25 | 2,107.55 | 0.070 | 13 | 28.48 | 0.008 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | total | 2207 | 768 | 1439 | 0.184 | -0.965 | 0.254 | -41,306.39 | 9,902.64 | 27,491.25 | 41,322.72 | 0.826 | 32 | 36.36 | 0.046 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | desarrollo | 1325 | 414 | 911 | 0.187 | -0.964 | 0.255 | -34,153.22 | 8,280.72 | 23,010.00 | 34,196.00 | 0.684 | 32 | 39.60 | 0.053 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | validacion | 440 | 122 | 318 | 0.182 | -0.962 | 0.253 | -4,762.41 | 1,096.16 | 3,030.00 | 4,762.41 | 0.301 | 19 | 36.51 | 0.052 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | test | 442 | 232 | 210 | 0.176 | -0.978 | 0.243 | -2,390.76 | 525.76 | 1,451.25 | 2,407.09 | 0.217 | 23 | 22.10 | 0.021 |
| sensibilidad: riesgo 0.50% | total | 2207 | 1780 | 427 | 0.241 | -0.551 | 0.459 | -28,250.15 | 7,886.40 | 14,183.75 | 28,514.03 | 0.570 | 17 | 28.78 | 0.011 |
| sensibilidad: riesgo 1.00% | total | 2207 | 1780 | 427 | 0.241 | -0.551 | 0.451 | -40,725.85 | 11,519.60 | 20,760.00 | 40,909.71 | 0.818 | 17 | 28.78 | 0.011 |
| sensibilidad: tamaño fijo 1 contrato | total | 2207 | 1780 | 427 | 0.241 | -0.551 | 0.545 | -1,904.48 | 529.48 | 940.00 | 1,960.76 | 0.039 | 17 | 28.78 | 0.011 |

## Bootstrap (completa)
- iid: R total p5/p50/p95 = -281.3 / -235.9 / -191.0; drawdown máx. en R p50/p95 = 238.6 / 283.3; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 284.4
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Bootstrap (sin_filtro_1h)
- iid: R total p5/p50/p95 = -900.0 / -813.4 / -721.2; drawdown máx. en R p50/p95 = 816.3 / 903.2; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 902.1
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Desglose (completa)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 52 | -2,754.77 | -0.744 | 0.212 |
| 2019 | 60 | -3,089.99 | -0.662 | 0.233 |
| 2020 | 51 | -952.01 | -0.298 | 0.314 |
| 2021 | 53 | -2,746.43 | -0.649 | 0.208 |
| 2022 | 49 | -2,102.03 | -0.575 | 0.204 |
| 2023 | 56 | -1,487.05 | -0.402 | 0.286 |
| 2024 | 40 | -1,684.46 | -0.678 | 0.200 |
| 2025 | 35 | -1,080.29 | -0.539 | 0.229 |
| 2026 | 31 | -724.38 | -0.345 | 0.290 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 30 | -2,145.79 | -1.02 | 0.100 |
| 2 | 31 | -1,249.49 | -0.508 | 0.258 |
| 3 | 36 | -1,403.28 | -0.500 | 0.250 |
| 4 | 28 | -2,078.68 | -1.12 | 0.071 |
| 5 | 44 | -483.88 | -0.210 | 0.341 |
| 6 | 38 | -2,196.68 | -0.799 | 0.158 |
| 7 | 47 | -1,797.04 | -0.509 | 0.255 |
| 8 | 34 | -456.69 | -0.334 | 0.324 |
| 9 | 38 | -1,212.85 | -0.407 | 0.289 |
| 10 | 38 | -902.39 | -0.332 | 0.289 |
| 11 | 36 | -1,544.64 | -0.595 | 0.222 |
| 12 | 27 | -1,150.00 | -0.564 | 0.259 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 88 | -3,852.52 | -0.632 | 0.216 |
| Monday | 92 | -5,097.93 | -0.733 | 0.185 |
| Thursday | 64 | -2,118.20 | -0.469 | 0.266 |
| Tuesday | 100 | -883.61 | -0.174 | 0.360 |
| Wednesday | 83 | -4,669.15 | -0.782 | 0.169 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 156 | -4,290.35 | -0.394 | 0.282 |
| largo | 271 | -12,331.06 | -0.642 | 0.218 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 1 | 60.06 | 0.801 | 1.00 |
| objetivo | 97 | 13,621.48 | 1.87 | 1.00 |
| objetivo_hueco | 5 | 654.16 | 1.85 | 1.00 |
| stop | 322 | -30,769.75 | -1.32 | 0.000 |
| stop_hueco | 2 | -187.36 | -1.22 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 139 | -6,944.09 | -0.690 | 0.187 |
| baja | 152 | -4,327.91 | -0.419 | 0.296 |
| media | 125 | -4,062.22 | -0.478 | 0.256 |
| sin_historial | 11 | -1,287.19 | -1.46 | 0.000 |

## Desglose (sin_filtro_1h)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 207 | -11,634.18 | -0.779 | 0.193 |
| 2019 | 192 | -7,292.08 | -0.638 | 0.240 |
| 2020 | 151 | -1,384.73 | -0.210 | 0.325 |
| 2021 | 165 | -3,858.11 | -0.487 | 0.261 |
| 2022 | 157 | -2,757.81 | -0.405 | 0.261 |
| 2023 | 190 | -3,694.44 | -0.539 | 0.242 |
| 2024 | 180 | -2,862.55 | -0.543 | 0.239 |
| 2025 | 152 | -1,893.30 | -0.470 | 0.257 |
| 2026 | 117 | -1,801.27 | -0.694 | 0.179 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 131 | -4,461.38 | -0.746 | 0.183 |
| 2 | 111 | -2,474.54 | -0.487 | 0.261 |
| 3 | 122 | -1,739.51 | -0.182 | 0.328 |
| 4 | 126 | -3,701.02 | -0.722 | 0.190 |
| 5 | 129 | -1,965.66 | -0.414 | 0.279 |
| 6 | 130 | -3,568.68 | -0.599 | 0.223 |
| 7 | 150 | -3,619.83 | -0.507 | 0.260 |
| 8 | 121 | -3,326.71 | -0.646 | 0.215 |
| 9 | 127 | -3,366.78 | -0.546 | 0.244 |
| 10 | 133 | -2,704.62 | -0.432 | 0.271 |
| 11 | 112 | -2,733.70 | -0.498 | 0.259 |
| 12 | 119 | -3,516.04 | -0.664 | 0.210 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 305 | -7,417.52 | -0.558 | 0.230 |
| Monday | 261 | -9,154.18 | -0.668 | 0.207 |
| Thursday | 322 | -8,048.18 | -0.521 | 0.248 |
| Tuesday | 320 | -5,191.75 | -0.418 | 0.281 |
| Wednesday | 303 | -7,366.84 | -0.548 | 0.244 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 645 | -16,018.47 | -0.527 | 0.247 |
| largo | 866 | -21,160.00 | -0.545 | 0.241 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 3 | 90.08 | 0.640 | 0.667 |
| objetivo | 345 | 29,029.30 | 1.86 | 1.00 |
| objetivo_hueco | 21 | 2,581.29 | 2.28 | 1.00 |
| stop | 1136 | -68,520.74 | -1.32 | 0.000 |
| stop_hueco | 6 | -358.40 | -1.31 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 413 | -7,850.95 | -0.423 | 0.262 |
| baja | 540 | -15,425.54 | -0.614 | 0.231 |
| media | 497 | -9,930.96 | -0.514 | 0.249 |
| sin_historial | 61 | -3,971.02 | -0.832 | 0.180 |

## Archivos
- `operaciones_*.csv`: cada operación (sesgo, OR, ruptura, retesteo, entrada, stop, objetivo, contratos, riesgo, salida, bruto, comisiones, slippage, neto en USD y R, avisos)
- `sesiones_*.csv` y `sesiones_excluidas_y_descartadas_*.csv`: estado y motivo de cada sesión
- `resumen.csv`, `bootstrap.json`, `manifest.json` (configuración, datos y versión del código)
- `capital_y_drawdown.png`, `distribucion_R.png`