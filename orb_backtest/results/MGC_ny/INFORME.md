# Informe ORB + estructura 1h + entrada 5m — MGC ny

Zona horaria America/New_York; rango 09:30-10:30; entradas hasta 15:00; cierre obligatorio 15:55; calendario XNYS.

**Aviso:** resultados de un backtest. No demuestran rentabilidad futura. Costes: comisión 0,62 USD/lado (supuesto no verificado) + 1 tick de slippage por lado.

## Datos
- Archivo: `/home/user/git_test/orb_backtest/data/GC_5m_databento.csv` (sha256 `1eba7299d70cf561…`) — Databento GLBX.MDP3 GC.v.0 (continuo por VOLUMEN, sin ajuste de rollover; según alpaca/README.md), 5 min. Precios de GC = precios de MGC (mismo subyacente y tick 0,10).
- Filas: 617,168; desde 2018-01-01 18:00:00-05:00 hasta 2026-10-02 16:55:00-04:00
- Avisos de validación: 120 sesiones regulares incompletas (2781 velas ausentes; incluye medias jornadas y festivos con Globex abierto)
- Calendario: XNYS (exchange_calendars)
- Velas de 1 h válidas: 51,481 (descartadas por incompletas: 268); pivotes confirmados: {'highs': 6579, 'lows': 6757}
- Periodos (60/20/20 por sesiones): desarrollo 2018-01-02 → 2023-04-03, validacion 2023-04-04 → 2025-01-02, test 2025-01-03 → 2026-10-02

## Resultados: estrategia completa frente a sin filtro 1H (solo cambia el filtro)

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa | total | 2184 | 1881 | 303 | 0.290 | -0.415 | 0.547 | -10,238.12 | 3,550.12 | 4,996.00 | 10,764.00 | 0.213 | 13 | 28.00 | 0.010 |
| completa | desarrollo | 1307 | 1096 | 211 | 0.289 | -0.445 | 0.524 | -7,930.24 | 2,822.24 | 3,957.00 | 8,477.96 | 0.168 | 13 | 29.86 | 0.012 |
| completa | validacion | 439 | 382 | 57 | 0.281 | -0.447 | 0.541 | -1,793.64 | 540.64 | 783.00 | 2,151.76 | 0.051 | 6 | 26.14 | 0.009 |
| completa | test | 438 | 403 | 35 | 0.314 | -0.179 | 0.749 | -514.24 | 187.24 | 256.00 | 692.92 | 0.017 | 5 | 19.86 | 0.004 |
| sin_filtro_1h | total | 2184 | 1170 | 1014 | 0.272 | -0.444 | 0.532 | -27,399.08 | 9,383.08 | 13,221.00 | 27,564.96 | 0.549 | 17 | 24.33 | 0.029 |
| sin_filtro_1h | desarrollo | 1307 | 617 | 690 | 0.275 | -0.441 | 0.534 | -21,128.44 | 7,633.44 | 10,706.00 | 21,314.68 | 0.425 | 17 | 26.24 | 0.036 |
| sin_filtro_1h | validacion | 439 | 231 | 208 | 0.279 | -0.456 | 0.535 | -4,070.36 | 1,288.36 | 1,852.00 | 4,070.36 | 0.141 | 12 | 23.34 | 0.028 |
| sin_filtro_1h | test | 438 | 322 | 116 | 0.241 | -0.442 | 0.508 | -2,200.28 | 461.28 | 663.00 | 2,200.28 | 0.089 | 10 | 14.78 | 0.010 |

## Pruebas de estrés de costes y sensibilidad

| version | periodo | sesiones_validas | sesiones_sin_operacion | operaciones | acierto | expectativa_R | profit_factor | resultado_neto | comisiones | slippage | dd_max_usd | dd_max_pct | racha_perdedora_max | duracion_media_min | exposicion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completa · costes slippage_2_ticks | total | 2184 | 1882 | 302 | 0.278 | -0.487 | 0.493 | -11,203.76 | 2,850.76 | 8,092.00 | 11,416.08 | 0.227 | 13 | 29.32 | 0.010 |
| completa · costes slippage_2_ticks | desarrollo | 1307 | 1096 | 211 | 0.280 | -0.531 | 0.468 | -8,705.28 | 2,259.28 | 6,404.00 | 8,938.96 | 0.178 | 13 | 31.64 | 0.013 |
| completa · costes slippage_2_ticks | validacion | 439 | 382 | 57 | 0.246 | -0.497 | 0.497 | -1,900.76 | 432.76 | 1,254.00 | 2,175.20 | 0.053 | 6 | 26.93 | 0.009 |
| completa · costes slippage_2_ticks | test | 438 | 404 | 34 | 0.324 | -0.198 | 0.693 | -597.72 | 158.72 | 434.00 | 652.96 | 0.017 | 5 | 18.97 | 0.004 |
| sin_filtro_1h · costes slippage_2_ticks | total | 2184 | 1178 | 1006 | 0.250 | -0.561 | 0.442 | -30,433.08 | 7,058.08 | 20,194.00 | 30,433.08 | 0.609 | 21 | 26.43 | 0.031 |
| sin_filtro_1h · costes slippage_2_ticks | desarrollo | 1307 | 618 | 689 | 0.255 | -0.556 | 0.451 | -23,637.84 | 5,816.84 | 16,566.00 | 23,663.92 | 0.473 | 21 | 28.70 | 0.039 |
| sin_filtro_1h · costes slippage_2_ticks | validacion | 439 | 231 | 208 | 0.236 | -0.611 | 0.388 | -4,926.52 | 927.52 | 2,724.00 | 4,926.52 | 0.187 | 16 | 24.69 | 0.030 |
| sin_filtro_1h · costes slippage_2_ticks | test | 438 | 329 | 109 | 0.239 | -0.499 | 0.450 | -1,868.72 | 313.72 | 904.00 | 1,868.72 | 0.087 | 13 | 15.37 | 0.010 |
| completa · costes slippage_3_ticks_comision_x2 | total | 2184 | 1882 | 302 | 0.245 | -0.708 | 0.379 | -13,543.12 | 4,325.12 | 9,351.00 | 13,614.24 | 0.272 | 13 | 30.88 | 0.011 |
| completa · costes slippage_3_ticks_comision_x2 | desarrollo | 1307 | 1096 | 211 | 0.237 | -0.779 | 0.348 | -10,683.36 | 3,427.36 | 7,413.00 | 10,806.64 | 0.216 | 13 | 33.41 | 0.014 |
| completa · costes slippage_3_ticks_comision_x2 | validacion | 439 | 382 | 57 | 0.228 | -0.698 | 0.391 | -2,217.76 | 649.76 | 1,431.00 | 2,346.32 | 0.060 | 7 | 28.16 | 0.009 |
| completa · costes slippage_3_ticks_comision_x2 | test | 438 | 404 | 34 | 0.324 | -0.287 | 0.636 | -642.00 | 248.00 | 507.00 | 642.00 | 0.017 | 5 | 19.71 | 0.004 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | total | 2184 | 1190 | 994 | 0.216 | -0.811 | 0.319 | -33,746.76 | 9,825.76 | 21,471.00 | 33,746.76 | 0.675 | 21 | 28.14 | 0.033 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | desarrollo | 1307 | 618 | 689 | 0.221 | -0.818 | 0.319 | -27,594.92 | 8,255.92 | 18,003.00 | 27,607.04 | 0.552 | 21 | 31.01 | 0.042 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | validacion | 439 | 233 | 206 | 0.199 | -0.851 | 0.305 | -4,514.00 | 1,178.00 | 2,619.00 | 4,514.00 | 0.201 | 16 | 25.75 | 0.031 |
| sin_filtro_1h · costes slippage_3_ticks_comision_x2 | test | 438 | 339 | 99 | 0.222 | -0.681 | 0.358 | -1,637.84 | 391.84 | 849.00 | 1,637.84 | 0.092 | 12 | 13.18 | 0.008 |
| sensibilidad: riesgo 0.50% | total | 2184 | 1879 | 305 | 0.289 | -0.419 | 0.541 | -19,215.00 | 6,603.00 | 9,284.00 | 20,233.80 | 0.397 | 13 | 28.87 | 0.010 |
| sensibilidad: riesgo 1.00% | total | 2184 | 1879 | 305 | 0.289 | -0.419 | 0.550 | -31,158.88 | 11,205.88 | 15,710.00 | 33,248.24 | 0.639 | 13 | 28.87 | 0.010 |
| sensibilidad: tamaño fijo 1 contrato | total | 2184 | 1879 | 305 | 0.289 | -0.419 | 0.566 | -1,480.20 | 378.20 | 535.00 | 1,533.80 | 0.031 | 13 | 28.87 | 0.010 |

## Bootstrap (completa)
- iid: R total p5/p50/p95 = -164.5 / -126.3 / -84.9; drawdown máx. en R p50/p95 = 129.8 / 167.3; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 161.5
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Bootstrap (sin_filtro_1h)
- iid: R total p5/p50/p95 = -520.7 / -448.9 / -377.9; drawdown máx. en R p50/p95 = 452.4 / 522.8; P(R total < 0) = 100.0%
- bloques de 5: P(R total < 0) = 100.0%; dd máx. R p95 = 521.3
- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora la dependencia entre operaciones; no captura cambios de régimen.

## Desglose (completa)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 55 | -1,593.68 | -0.323 | 0.327 |
| 2019 | 42 | -937.80 | -0.305 | 0.381 |
| 2020 | 31 | -1,153.92 | -0.397 | 0.290 |
| 2021 | 35 | -1,959.64 | -0.637 | 0.200 |
| 2022 | 38 | -1,706.40 | -0.586 | 0.237 |
| 2023 | 33 | -1,855.20 | -0.676 | 0.212 |
| 2024 | 34 | -517.24 | -0.286 | 0.324 |
| 2025 | 26 | -552.76 | -0.231 | 0.308 |
| 2026 | 9 | 38.52 | -0.027 | 0.333 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 34 | -1,461.44 | -0.474 | 0.294 |
| 2 | 29 | -94.52 | -0.021 | 0.414 |
| 3 | 22 | -868.56 | -0.541 | 0.273 |
| 4 | 19 | -887.76 | -0.640 | 0.211 |
| 5 | 20 | -1,480.84 | -0.964 | 0.100 |
| 6 | 23 | 99.80 | 0.007 | 0.435 |
| 7 | 19 | 245.04 | 0.145 | 0.474 |
| 8 | 38 | -1,141.68 | -0.352 | 0.316 |
| 9 | 24 | -1,205.24 | -0.578 | 0.208 |
| 10 | 23 | -237.48 | -0.112 | 0.348 |
| 11 | 26 | -1,563.28 | -0.725 | 0.192 |
| 12 | 26 | -1,642.16 | -0.764 | 0.192 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 55 | -2,507.40 | -0.538 | 0.236 |
| Monday | 64 | -2,431.40 | -0.434 | 0.281 |
| Thursday | 59 | -1,819.60 | -0.393 | 0.271 |
| Tuesday | 66 | -1,270.04 | -0.274 | 0.364 |
| Wednesday | 59 | -2,209.68 | -0.460 | 0.288 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 133 | -5,304.20 | -0.490 | 0.256 |
| largo | 170 | -4,933.92 | -0.356 | 0.318 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 15 | 600.80 | 0.410 | 0.867 |
| objetivo | 73 | 11,402.56 | 1.85 | 1.00 |
| objetivo_hueco | 2 | 274.24 | 1.81 | 1.00 |
| stop | 212 | -22,400.36 | -1.27 | 0.000 |
| stop_hueco | 1 | -115.36 | -1.37 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 106 | -3,969.60 | -0.487 | 0.255 |
| baja | 51 | -2,237.88 | -0.498 | 0.294 |
| media | 129 | -3,955.88 | -0.374 | 0.302 |
| sin_historial | 17 | -74.76 | -0.033 | 0.412 |

## Desglose (sin_filtro_1h)

### Por año

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 2018 | 169 | -5,861.28 | -0.420 | 0.296 |
| 2019 | 147 | -4,711.16 | -0.447 | 0.286 |
| 2020 | 115 | -2,891.04 | -0.341 | 0.287 |
| 2021 | 111 | -2,387.64 | -0.331 | 0.306 |
| 2022 | 117 | -3,939.24 | -0.579 | 0.222 |
| 2023 | 117 | -3,849.56 | -0.629 | 0.222 |
| 2024 | 121 | -1,507.16 | -0.364 | 0.306 |
| 2025 | 81 | -1,331.52 | -0.393 | 0.259 |
| 2026 | 36 | -920.48 | -0.571 | 0.194 |

### Por mes

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| 1 | 91 | -3,880.12 | -0.691 | 0.209 |
| 2 | 84 | -1,565.32 | -0.288 | 0.321 |
| 3 | 80 | -3,868.08 | -0.659 | 0.200 |
| 4 | 82 | -2,367.72 | -0.486 | 0.256 |
| 5 | 87 | -2,921.56 | -0.586 | 0.230 |
| 6 | 80 | -1,316.80 | -0.308 | 0.312 |
| 7 | 91 | -1,350.04 | -0.277 | 0.330 |
| 8 | 98 | -368.12 | -0.112 | 0.367 |
| 9 | 78 | -2,164.28 | -0.438 | 0.269 |
| 10 | 75 | -1,681.96 | -0.324 | 0.307 |
| 11 | 83 | -2,956.52 | -0.549 | 0.241 |
| 12 | 85 | -2,958.56 | -0.645 | 0.212 |

### Por dia semana

| session | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| Friday | 190 | -6,635.12 | -0.532 | 0.232 |
| Monday | 198 | -6,455.12 | -0.483 | 0.268 |
| Thursday | 202 | -5,613.68 | -0.458 | 0.262 |
| Tuesday | 205 | -2,245.72 | -0.247 | 0.346 |
| Wednesday | 219 | -6,449.44 | -0.505 | 0.251 |

### Por direccion

| side | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| corto | 457 | -13,191.92 | -0.472 | 0.265 |
| largo | 557 | -14,207.16 | -0.422 | 0.278 |

### Por motivo salida

| exit_reason | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| cierre_obligatorio | 35 | 828.84 | 0.352 | 0.714 |
| objetivo | 246 | 29,555.88 | 1.86 | 1.00 |
| objetivo_hueco | 5 | 622.00 | 1.81 | 1.00 |
| stop | 725 | -58,049.60 | -1.27 | 0.000 |
| stop_hueco | 3 | -356.20 | -1.47 | 0.000 |

### Por regimen volatilidad

| vol_regime | operaciones | neto_usd | R_medio | acierto |
|---|---|---|---|---|
| alta | 386 | -9,535.20 | -0.431 | 0.267 |
| baja | 172 | -5,744.68 | -0.534 | 0.262 |
| media | 406 | -10,999.92 | -0.448 | 0.271 |
| sin_historial | 50 | -1,119.28 | -0.201 | 0.360 |

## Archivos
- `operaciones_*.csv`: cada operación (sesgo, OR, ruptura, retesteo, entrada, stop, objetivo, contratos, riesgo, salida, bruto, comisiones, slippage, neto en USD y R, avisos)
- `sesiones_*.csv` y `sesiones_excluidas_y_descartadas_*.csv`: estado y motivo de cada sesión
- `resumen.csv`, `bootstrap.json`, `manifest.json` (configuración, datos y versión del código)
- `capital_y_drawdown.png`, `distribucion_R.png`