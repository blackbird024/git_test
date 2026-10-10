# Informe ORB + estructura 1h + entrada 5m — MGC london

Zona horaria Europe/London; rango 08:00-09:00; entradas hasta 13:00; cierre obligatorio 16:25; calendario XLON.

**Aviso:** resultados de un backtest. No demuestran rentabilidad futura. Costes: comisión 0,62 USD/lado (supuesto no verificado) + 1 tick de slippage por lado.

## Datos
- Archivo: `/home/user/git_test/orb_backtest/data/GC_5m_databento.csv` (sha256 `1eba7299d70cf561…`) — Databento GLBX.MDP3 GC.v.0 (continuo por VOLUMEN, sin ajuste de rollover; según alpaca/README.md), 5 min. Precios de GC = precios de MGC (mismo subyacente y tick 0,10).
- Filas: 617,168; desde 2018-01-01 23:00:00+00:00 hasta 2026-10-02 21:55:00+01:00
- Avisos de validación: 39 sesiones regulares incompletas (922 velas ausentes; incluye medias jornadas y festivos con Globex abierto)
- Calendario: XNYS (exchange_calendars)
- Velas de 1 h válidas: 51,481 (descartadas por incompletas: 268); pivotes confirmados: {'highs': 6579, 'lows': 6757}
- Periodos (60/20/20 por sesiones): desarrollo 2018-01-02 → 2023-04-03, validacion 2023-04-04 → 2025-01-02, test 2025-01-03 → 2026-10-02

## Resultados: estrategia completa frente a sin filtro 1H (solo cambia el filtro)

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa | total | 2185 | 1773 | 412 | 0.257 | -0.501 | 0.504 | -15,013.96 | 4,964.96 | 6,995.00 | 15,205.84 | 0.303 | 15 | 21.77 | 0.008 |
| completa | desarrollo | 1310 | 1045 | 265 | 0.275 | -0.459 | 0.525 | -9,844.52 | 3,624.52 | 5,067.00 | 10,036.40 | 0.200 | 15 | 24.57 | 0.010 |
| completa | validacion | 436 | 355 | 81 | 0.235 | -0.580 | 0.463 | -2,985.44 | 875.44 | 1,254.00 | 3,168.08 | 0.079 | 15 | 20.12 | 0.007 |
| completa | test | 439 | 373 | 66 | 0.212 | -0.575 | 0.447 | -2,184.00 | 465.00 | 674.00 | 2,184.00 | 0.059 | 13 | 12.58 | 0.004 |
| sin_filtro_1h | total | 2185 | 864 | 1321 | 0.266 | -0.480 | 0.518 | -32,741.00 | 12,028.00 | 16,877.00 | 33,268.76 | 0.659 | 22 | 23.16 | 0.027 |
| sin_filtro_1h | desarrollo | 1310 | 442 | 868 | 0.272 | -0.477 | 0.524 | -25,207.04 | 9,729.04 | 13,596.00 | 25,905.40 | 0.513 | 22 | 25.99 | 0.034 |
| sin_filtro_1h | validacion | 436 | 140 | 296 | 0.240 | -0.554 | 0.451 | -5,929.20 | 1,742.20 | 2,484.00 | 5,950.80 | 0.240 | 17 | 20.86 | 0.028 |
| sin_filtro_1h | test | 439 | 282 | 157 | 0.287 | -0.353 | 0.611 | -1,604.76 | 556.76 | 797.00 | 1,637.36 | 0.087 | 11 | 11.85 | 0.008 |

## Pruebas de estrés de costes y sensibilidad

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa · costes slippage_2_ticks | total | 2185 | 1773 | 412 | 0.233 | -0.622 | 0.433 | -17,023.96 | 3,910.96 | 11,182.00 | 17,208.32 | 0.343 | 19 | 24.00 | 0.009 |
| completa · costes slippage_2_ticks | desarrollo | 1310 | 1045 | 265 | 0.253 | -0.575 | 0.456 | -11,251.40 | 2,864.40 | 8,110.00 | 11,435.76 | 0.228 | 19 | 27.23 | 0.011 |
| completa · costes slippage_2_ticks | validacion | 436 | 355 | 81 | 0.185 | -0.783 | 0.337 | -3,707.28 | 678.28 | 2,008.00 | 3,716.52 | 0.096 | 15 | 22.59 | 0.008 |
| completa · costes slippage_2_ticks | test | 439 | 373 | 66 | 0.212 | -0.613 | 0.444 | -2,065.28 | 368.28 | 1,064.00 | 2,065.28 | 0.059 | 13 | 12.80 | 0.004 |
| sin_filtro_1h · costes slippage_2_ticks | total | 2185 | 871 | 1314 | 0.243 | -0.602 | 0.443 | -35,324.68 | 8,905.68 | 25,308.00 | 35,585.80 | 0.708 | 26 | 25.16 | 0.030 |
| sin_filtro_1h · costes slippage_2_ticks | desarrollo | 1310 | 442 | 868 | 0.248 | -0.601 | 0.447 | -28,118.76 | 7,345.76 | 20,808.00 | 28,502.04 | 0.567 | 25 | 28.46 | 0.037 |
| sin_filtro_1h · costes slippage_2_ticks | validacion | 436 | 142 | 294 | 0.211 | -0.694 | 0.368 | -5,807.76 | 1,176.76 | 3,408.00 | 5,809.00 | 0.265 | 26 | 22.30 | 0.029 |
| sin_filtro_1h · costes slippage_2_ticks | test | 439 | 287 | 152 | 0.276 | -0.430 | 0.584 | -1,398.16 | 383.16 | 1,092.00 | 1,417.88 | 0.088 | 11 | 11.91 | 0.008 |
| completa · costes slippage_3_ticks_comision_x2 | total | 2185 | 1774 | 411 | 0.212 | -0.852 | 0.317 | -19,693.00 | 5,704.00 | 12,354.00 | 19,833.16 | 0.396 | 19 | 26.73 | 0.010 |
| completa · costes slippage_3_ticks_comision_x2 | desarrollo | 1310 | 1045 | 265 | 0.223 | -0.840 | 0.317 | -14,005.88 | 4,230.88 | 9,108.00 | 14,146.04 | 0.282 | 19 | 31.02 | 0.012 |
| completa · costes slippage_3_ticks_comision_x2 | validacion | 436 | 355 | 81 | 0.185 | -0.946 | 0.281 | -3,588.88 | 944.88 | 2,097.00 | 3,588.88 | 0.100 | 15 | 23.83 | 0.009 |
| completa · costes slippage_3_ticks_comision_x2 | test | 439 | 374 | 65 | 0.200 | -0.782 | 0.373 | -2,098.24 | 528.24 | 1,149.00 | 2,098.24 | 0.065 | 14 | 12.85 | 0.004 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | total | 2185 | 903 | 1282 | 0.216 | -0.866 | 0.313 | -38,267.36 | 11,797.36 | 25,515.00 | 38,370.12 | 0.766 | 32 | 28.47 | 0.033 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | desarrollo | 1310 | 443 | 867 | 0.218 | -0.874 | 0.313 | -32,096.56 | 10,036.56 | 21,681.00 | 32,287.00 | 0.644 | 32 | 32.18 | 0.042 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | validacion | 436 | 148 | 288 | 0.198 | -0.908 | 0.284 | -4,859.64 | 1,346.64 | 2,943.00 | 4,859.64 | 0.271 | 26 | 24.39 | 0.032 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | test | 439 | 312 | 127 | 0.244 | -0.710 | 0.418 | -1,311.16 | 414.16 | 891.00 | 1,311.16 | 0.101 | 11 | 12.36 | 0.007 |
| sensibilidad: riesgo 0.50% | total | 2185 | 1770 | 415 | 0.258 | -0.498 | 0.515 | -25,824.60 | 8,791.60 | 12,361.00 | 26,223.12 | 0.520 | 15 | 22.41 | 0.008 |
| sensibilidad: riesgo 1.00% | total | 2185 | 1770 | 415 | 0.258 | -0.498 | 0.518 | -38,538.32 | 13,569.32 | 19,036.00 | 39,335.36 | 0.774 | 15 | 22.41 | 0.008 |
| sensibilidad: tamaño fijo 1 contrato | total | 2185 | 1770 | 415 | 0.258 | -0.498 | 0.547 | -2,003.60 | 514.60 | 723.00 | 2,018.36 | 0.040 | 15 | 22.41 | 0.008 |

## Bootstrap (completa)
- iid: R total p5/p50/p95 = -253.7 / -206.0 / -159.5; drawdown máx. en R p50/p95 = 209.1 / 255.2; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 256.6
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Bootstrap (sin_filtro_1h)
- iid: R total p5/p50/p95 = -718.6 / -632.9 / -548.7; drawdown máx. en R p50/p95 = 636.5 / 721.2; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 718.9
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Desglose (completa)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 43 | -1,649.76 | -0.422 | 0.302 |
| 2019 | 53 | -2,198.72 | -0.515 | 0.264 |
| 2020 | 48 | -755.52 | -0.156 | 0.354 |
| 2021 | 56 | -3,014.36 | -0.614 | 0.214 |
| 2022 | 52 | -1,650.92 | -0.516 | 0.269 |
| 2023 | 46 | -2,756.60 | -0.899 | 0.152 |
| 2024 | 47 | -706.64 | -0.254 | 0.319 |
| 2025 | 50 | -1,706.84 | -0.541 | 0.220 |
| 2026 | 17 | -574.60 | -0.711 | 0.176 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 40 | -1,831.52 | -0.584 | 0.225 |
| 2 | 32 | -1,151.36 | -0.544 | 0.250 |
| 3 | 38 | -1,799.12 | -0.531 | 0.237 |
| 4 | 29 | -1,532.52 | -0.606 | 0.207 |
| 5 | 29 | -1,274.68 | -0.509 | 0.241 |
| 6 | 39 | -1,304.20 | -0.498 | 0.256 |
| 7 | 41 | -2,106.44 | -0.816 | 0.195 |
| 8 | 37 | 29.16 | -0.028 | 0.405 |
| 9 | 34 | -111.52 | -0.079 | 0.382 |
| 10 | 26 | -304.08 | -0.230 | 0.346 |
| 11 | 30 | -810.48 | -0.501 | 0.267 |
| 12 | 37 | -2,817.20 | -0.964 | 0.108 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 84 | -4,298.28 | -0.670 | 0.202 |
| Monday | 77 | -3,768.24 | -0.628 | 0.208 |
| Thursday | 85 | -2,280.52 | -0.393 | 0.294 |
| Tuesday | 96 | -3,496.88 | -0.556 | 0.250 |
| Wednesday | 70 | -1,170.04 | -0.217 | 0.343 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 187 | -5,870.08 | -0.407 | 0.283 |
| largo | 225 | -9,143.88 | -0.580 | 0.236 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| objetivo | 105 | 15,113.52 | 1.85 | 1.00 |
| objetivo_hueco | 1 | 118.36 | 1.79 | 1.00 |
| stop | 306 | -30,245.84 | -1.31 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 163 | -4,112.64 | -0.384 | 0.288 |
| baja | 72 | -2,700.60 | -0.502 | 0.278 |
| media | 169 | -7,505.60 | -0.593 | 0.225 |
| sin_historial | 8 | -695.12 | -0.944 | 0.125 |

## Desglose (sin_filtro_1h)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 183 | -7,250.24 | -0.521 | 0.279 |
| 2019 | 173 | -5,470.36 | -0.469 | 0.283 |
| 2020 | 164 | -3,344.80 | -0.321 | 0.305 |
| 2021 | 161 | -5,889.00 | -0.656 | 0.205 |
| 2022 | 149 | -2,771.20 | -0.459 | 0.275 |
| 2023 | 174 | -3,865.68 | -0.577 | 0.241 |
| 2024 | 159 | -2,496.24 | -0.464 | 0.258 |
| 2025 | 112 | -1,547.84 | -0.440 | 0.259 |
| 2026 | 46 | -105.64 | -0.159 | 0.348 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 108 | -3,060.84 | -0.511 | 0.269 |
| 2 | 110 | -2,144.24 | -0.391 | 0.300 |
| 3 | 115 | -3,508.32 | -0.531 | 0.243 |
| 4 | 109 | -4,492.12 | -0.694 | 0.193 |
| 5 | 106 | -2,692.72 | -0.444 | 0.274 |
| 6 | 107 | -2,094.64 | -0.356 | 0.308 |
| 7 | 118 | -2,416.08 | -0.477 | 0.280 |
| 8 | 121 | -2,806.48 | -0.459 | 0.264 |
| 9 | 110 | -2,298.88 | -0.402 | 0.282 |
| 10 | 114 | -1,287.72 | -0.310 | 0.316 |
| 11 | 93 | -1,941.00 | -0.457 | 0.280 |
| 12 | 110 | -3,997.96 | -0.725 | 0.191 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 267 | -5,071.92 | -0.364 | 0.300 |
| Monday | 252 | -9,510.12 | -0.666 | 0.202 |
| Thursday | 266 | -7,125.32 | -0.556 | 0.244 |
| Tuesday | 268 | -6,420.56 | -0.509 | 0.265 |
| Wednesday | 268 | -4,613.08 | -0.315 | 0.317 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 611 | -15,494.64 | -0.482 | 0.264 |
| largo | 710 | -17,246.36 | -0.478 | 0.269 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| objetivo | 348 | 34,814.04 | 1.84 | 1.00 |
| objetivo_hueco | 4 | 361.44 | 1.72 | 1.00 |
| stop | 964 | -67,595.80 | -1.32 | 0.000 |
| stop_hueco | 5 | -320.68 | -1.45 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 534 | -9,844.04 | -0.384 | 0.288 |
| baja | 206 | -6,482.96 | -0.522 | 0.272 |
| media | 523 | -14,110.52 | -0.557 | 0.239 |
| sin_historial | 58 | -2,303.48 | -0.511 | 0.293 |

## Archivos
- `operaciones_*.csv`: cada operación (sesgo, OR, ruptura, retesteo, entrada, stop, objetivo, contratos, riesgo, salida, bruto, comisiones, slippage, neto en USD y R, avisos)
- `sesiones_*.csv` y `sesiones_excluidas_y_descartadas_*.csv`: estado y motivo de cada sesión
- `resumen.csv`, `bootstrap.json`, `manifest.json` (configuración, datos y versión del código)
- `capital_y_drawdown.png`, `distribucion_R.png`