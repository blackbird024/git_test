# FINAL REPORT — VWAP + EMAs, velas de 15 minutos

*Generado el 2026-09-29 21:07 UTC con `python generate_report.py` a partir de ejecuciones reales (`run_backtest.py`, `optimize.py`). Presenta resultados; no designa una estrategia ganadora. Ningún resultado histórico implica rentabilidad futura.*

## 1. Datos utilizados
| instrumento   | fuente de precio                                                         | fuente de volumen (VWAP)                       | timeframe origen   | desde      | hasta      |   filas |   duplicadas |   inválidas |   sesiones válidas |   sesiones excluidas |   % minutos presentes en sesión |   contratos |
|:--------------|:-------------------------------------------------------------------------|:-----------------------------------------------|:-------------------|:-----------|:-----------|--------:|-------------:|------------:|-------------------:|---------------------:|--------------------------------:|------------:|
| MNQ           | NQ (Databento GLBX.MDP3, contrato continuo NQ.v.0; mismo precio que MNQ) | volumen negociado del futuro NQ en CME (1 min) | 0 days 00:01:00    | 2015-01-01 | 2026-09-29 | 4088229 |            0 |           0 |               2924 |                  103 |                           98.51 |          48 |
| NQ            | NQ (Databento GLBX.MDP3, NQ.v.0)                                         | volumen negociado del futuro NQ en CME (1 min) | 0 days 00:01:00    | 2015-01-01 | 2026-09-29 | 4088229 |            0 |           0 |               2924 |                  103 |                           98.51 |          48 |
| MGC           | GC (Databento GLBX.MDP3, contrato continuo GC.v.0; mismo precio que MGC) | volumen negociado del futuro GC en CME (1 min) | 0 days 00:01:00    | 2015-01-01 | 2026-09-29 | 4090435 |            0 |           0 |               2896 |                  134 |                           98.84 |          60 |
| GC            | GC (Databento GLBX.MDP3, GC.v.0)                                         | volumen negociado del futuro GC en CME (1 min) | 0 days 00:01:00    | 2015-01-01 | 2026-09-29 | 4090435 |            0 |           0 |               2896 |                  134 |                           98.84 |          60 |

- **XAUUSD: sin datos** — No hay archivos que coincidan con '../data/mt5/XAUUSD*.csv'. No se ha inventado nada; ver `data/README.md` para añadirlo.

- MNQ/MGC usan el precio de NQ/GC (mismo subyacente y cotización). NQ/GC son referencias con 1 contrato fijo y 500.000 $ de capital.

## 2. Período estudiado
|     | train                   | validation              | test                    |
|:----|:------------------------|:------------------------|:------------------------|
| MNQ | 2015-01-02 → 2022-01-13 | 2022-01-14 → 2024-05-17 | 2024-05-20 → 2026-09-28 |
| NQ  | 2015-01-02 → 2022-01-13 | 2022-01-14 → 2024-05-17 | 2024-05-20 → 2026-09-28 |
| MGC | 2015-01-02 → 2022-02-10 | 2022-02-11 → 2024-06-05 | 2024-06-06 → 2026-09-28 |
| GC  | 2015-01-02 → 2022-02-10 | 2022-02-11 → 2024-06-05 | 2024-06-06 → 2026-09-28 |

Particiones por número de sesiones válidas (60/20/20). El test solo se usa en `optimize.py`; registro en `results/TEST_LOG.md`. **Aviso NQ:** en proyectos anteriores de este repositorio ya se estudiaron reglas de VWAP en NQ con datos desde 2023; el test de MNQ/NQ no es completamente "virgen" para la familia VWAP, aunque estas reglas concretas no se habían probado.

## 3. Supuestos
- Todo con velas de 15 min (`intrabar: 15m`): el VWAP se acumula con las velas de 15 min de la sesión (precio típico × volumen) y se reinicia al inicio de la sesión de cada instrumento; stop y target se comprueban con el máximo y el mínimo de cada vela de 15 min; **si una vela toca stop y target, se asume el stop**; si abre más allá del stop, se ejecuta en la apertura.
- Señal al cierre de la vela; ejecución a mercado en la apertura de la siguiente. Target = orden límite, solo si el precio lo supera en 1 tick. Una posición por instrumento; sin pyramiding, martingala ni overnight.
- EMAs 20/50/200 y ATR(14) sobre las velas de 15 min de la sesión, continuas entre días y reiniciadas en cada cambio de contrato (no se ajusta el continuo hacia atrás).
- Riesgo: 0.5 % del capital actual por operación; contratos = floor(riesgo / (stop × valor del punto)); límite diario 2.0 %, 3 pérdidas seguidas, 6 operaciones/día.

## 4. Costes
|        |   tick_size |   point_value |   commission_per_side |   slippage_ticks |   spread_ticks | session            | eod_exit   |
|:-------|------------:|--------------:|----------------------:|-----------------:|---------------:|:-------------------|:-----------|
| MNQ    |        0.25 |             2 |                  0.85 |                1 |              0 | ['09:30', '16:00'] | 15:45      |
| NQ     |        0.25 |            20 |                  2.5  |                1 |              0 | ['09:30', '16:00'] | 15:45      |
| MGC    |        0.1  |            10 |                  0.85 |                1 |              0 | ['03:00', '13:30'] | 13:15      |
| GC     |        0.1  |           100 |                  2.5  |                1 |              0 | ['03:00', '13:30'] | 13:15      |
| XAUUSD |        0.01 |           100 |                  3.5  |                5 |             20 | ['03:00', '13:30'] | 13:15      |

Resultados siempre **netos** (bruto, costes y neto por separado). Escenario de costes dobles (deslizamiento ×2) en el apartado 16.

## 5. Reglas exactas
- **Modelos:** A cierre vs VWAP; B + cierre vs EMA200; C + EMA50 vs EMA200 y cierre vs EMA200; D = C + cierre vs EMA20 (EMA20 solo como filtro de timing).
- **Entradas:** `state` (condición cumplida al cierre y sin posición); `breakout` (el cierre cruza el VWAP y la vela confirma: cierre > apertura en largos); `pullback` (la vela anterior cerró del lado bueno, la actual retrocede hasta max(VWAP, EMA20) y cierra de nuevo a favor y con cuerpo a favor).
- **Filtros de tendencia (uno a uno):** pendiente de la EMA200 (4 velas) a favor; pendiente del VWAP a favor.
- **Stops:** ATR(14) × 1,0 / 1,5 / 2,0; estructura (mínimo/máximo de las últimas 5 velas ∓ 1 tick).
- **Take profit:** 1 / 1,5 / 2 / 2,5 / 3 R o sin TP.
- **Salidas:** A VWAP (cierre al otro lado), B EMA20, C trailing ATR (2 × ATR desde el mejor cierre), D TP/SL fijo (TP 2R si no se indica), E parcial 50 % en 1R + stop a la entrada + trailing, F tiempo (30/60/90/120/180 min). Todas con stop inicial y cierre forzado de sesión.
- **Baseline:** modelo A, entrada state, stop 1.5 × ATR, sin TP, salida vwap.

## 6-9. Baseline VWAP → +EMA200 → +EMA50/200 → +EMA20 (mismo resto de reglas)
Train y validation salen de `run_backtest.py`; test de `optimize.py` (una ejecución). Δ = cambio de la expectativa neta en R respecto al modelo anterior de la secuencia.

### MNQ
| configuración       | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:--------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| modelo A (baseline) | train      |     4607 |         27.6 |        -0.0271 |               0.0467 | -1.64 |           0.889 |    -25144 |     -58    |    -0.73 |
| modelo A (baseline) | validation |     1679 |         28.8 |         0.0308 |               0.0525 |  1.1  |           1.084 |     10536 |      -7.7  |     0.75 |
| modelo A (baseline) | test       |     1540 |         31   |         0.0193 |               0.0375 |  0.6  |           1.047 |      5499 |     -11.64 |     0.42 |
| modelo B (baseline) | train      |     3286 |         29.3 |        -0.0161 |               0.0532 | -0.88 |           0.937 |    -12956 |     -35.17 |    -0.38 |
| modelo B (baseline) | validation |     1110 |         32.4 |         0.0488 |               0.0703 |  1.51 |           1.117 |      9946 |      -6.4  |     0.9  |
| modelo B (baseline) | test       |      953 |         32.6 |         0.0081 |               0.026  |  0.23 |           1.034 |      2350 |     -10.21 |     0.27 |
| modelo C (baseline) | train      |     2841 |         29.4 |        -0.0321 |               0.0397 | -1.72 |           0.879 |    -19336 |     -42.72 |    -0.75 |
| modelo C (baseline) | validation |      961 |         31.6 |         0.0343 |               0.0561 |  1.05 |           1.068 |      4746 |      -9.07 |     0.52 |
| modelo C (baseline) | test       |      808 |         32.8 |        -0.0028 |               0.0157 | -0.08 |           1.027 |      1502 |     -12.75 |     0.2  |
| modelo D (baseline) | train      |     2516 |         30.5 |        -0.0344 |               0.0373 | -1.72 |           0.875 |    -18582 |     -39.97 |    -0.75 |
| modelo D (baseline) | validation |      854 |         31.7 |         0.0135 |               0.0353 |  0.38 |           1.029 |      1901 |     -12.53 |     0.24 |
| modelo D (baseline) | test       |      698 |         34.8 |        -0.0138 |               0.0049 | -0.36 |           0.984 |      -772 |     -13.44 |    -0.06 |

Expectativa neta (R) y aporte de cada paso:

| configuración       |   train |   validation |    test |   Δ train |   Δ validation |   Δ test |
|:--------------------|--------:|-------------:|--------:|----------:|---------------:|---------:|
| modelo A (baseline) | -0.0271 |       0.0308 |  0.0193 |  nan      |       nan      | nan      |
| modelo B (baseline) | -0.0161 |       0.0488 |  0.0081 |    0.011  |         0.018  |  -0.0112 |
| modelo C (baseline) | -0.0321 |       0.0343 | -0.0028 |   -0.016  |        -0.0145 |  -0.0109 |
| modelo D (baseline) | -0.0344 |       0.0135 | -0.0138 |   -0.0023 |        -0.0208 |  -0.011  |

![MNQ modelos](MNQ_modelos_periodos.png)

### MGC
| configuración       | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:--------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| modelo A (baseline) | train      |     4248 |         19.3 |        -0.1414 |               0.0194 | -7.66 |           0.677 |    -46171 |     -92.87 |    -2.74 |
| modelo A (baseline) | validation |     2195 |         22.3 |        -0.0686 |               0.0191 | -2.71 |           0.789 |    -25615 |     -54.29 |    -1.82 |
| modelo A (baseline) | test       |     1912 |         22   |        -0.0452 |               0.0003 | -1.68 |           0.839 |    -16502 |     -42.39 |    -1.18 |
| modelo B (baseline) | train      |     3907 |         20.7 |        -0.1203 |               0.0341 | -5.57 |           0.773 |    -43921 |     -89.71 |    -1.99 |
| modelo B (baseline) | validation |     1625 |         22.8 |        -0.0642 |               0.0276 | -1.88 |           0.822 |    -19162 |     -45.19 |    -1.18 |
| modelo B (baseline) | test       |     1469 |         23   |        -0.06   |              -0.0141 | -1.99 |           0.826 |    -15336 |     -31.76 |    -1.22 |
| modelo C (baseline) | train      |     3970 |         21.1 |        -0.1033 |               0.0441 | -4.79 |           0.798 |    -42143 |     -86.56 |    -1.75 |
| modelo C (baseline) | validation |     1487 |         22.5 |        -0.0514 |               0.0408 | -1.42 |           0.837 |    -15962 |     -44.63 |    -0.97 |
| modelo C (baseline) | test       |     1357 |         22.5 |        -0.0658 |              -0.0194 | -2.09 |           0.808 |    -15372 |     -31.36 |    -1.27 |
| modelo D (baseline) | train      |     3639 |         22.4 |        -0.11   |               0.0399 | -4.67 |           0.805 |    -41761 |     -86.02 |    -1.68 |
| modelo D (baseline) | validation |     1367 |         23   |        -0.0488 |               0.0444 | -1.21 |           0.863 |    -13858 |     -43.59 |    -0.76 |
| modelo D (baseline) | test       |     1249 |         23.5 |        -0.0572 |              -0.0105 | -1.64 |           0.834 |    -13862 |     -28.77 |    -1.13 |

Expectativa neta (R) y aporte de cada paso:

| configuración       |   train |   validation |    test |   Δ train |   Δ validation |   Δ test |
|:--------------------|--------:|-------------:|--------:|----------:|---------------:|---------:|
| modelo A (baseline) | -0.1414 |      -0.0686 | -0.0452 |  nan      |       nan      | nan      |
| modelo B (baseline) | -0.1203 |      -0.0642 | -0.06   |    0.0211 |         0.0044 |  -0.0148 |
| modelo C (baseline) | -0.1033 |      -0.0514 | -0.0658 |    0.017  |         0.0128 |  -0.0058 |
| modelo D (baseline) | -0.11   |      -0.0488 | -0.0572 |   -0.0067 |         0.0026 |   0.0086 |

![MGC modelos](MGC_modelos_periodos.png)

### NQ
| configuración       | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:--------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| modelo A (baseline) | train      |     5063 |         28   |         0.0087 |               0.047  |  0.56 |           1.069 |     72662 |      -6.28 |     0.5  |
| modelo A (baseline) | validation |     1740 |         29.4 |         0.0444 |               0.0562 |  1.63 |           1.15  |    119868 |      -4.24 |     1.23 |
| modelo A (baseline) | test       |     1727 |         30.6 |         0.0264 |               0.0358 |  0.91 |           0.995 |     -5862 |     -19.2  |     0.01 |
| modelo B (baseline) | train      |     3378 |         30   |         0.015  |               0.0528 |  0.84 |           1.064 |     43846 |      -4.74 |     0.4  |
| modelo B (baseline) | validation |     1147 |         32.8 |         0.0584 |               0.0702 |  1.86 |           1.221 |    118034 |      -3.23 |     1.55 |
| modelo B (baseline) | test       |     1101 |         31.4 |         0.0177 |               0.0268 |  0.54 |           1.064 |     47832 |      -8.32 |     0.47 |
| modelo C (baseline) | train      |     2971 |         30.2 |         0.001  |               0.0396 |  0.06 |           1.03  |     17578 |      -3.92 |     0.18 |
| modelo C (baseline) | validation |      997 |         32   |         0.0417 |               0.0535 |  1.31 |           1.175 |     79294 |      -3.7  |     1.14 |
| modelo C (baseline) | test       |      951 |         31.8 |         0.0098 |               0.0191 |  0.3  |           1.051 |     31700 |     -10.49 |     0.36 |
| modelo D (baseline) | train      |     2604 |         31.2 |         0.0014 |               0.0403 |  0.07 |           1.059 |     30611 |      -3.24 |     0.32 |
| modelo D (baseline) | validation |      881 |         32   |         0.0239 |               0.0357 |  0.69 |           1.117 |     50670 |      -4.7  |     0.79 |
| modelo D (baseline) | test       |      831 |         33.3 |         0.0001 |               0.0094 |  0    |           1.022 |     12516 |     -12.62 |     0.17 |

Expectativa neta (R) y aporte de cada paso:

| configuración       |   train |   validation |   test |   Δ train |   Δ validation |   Δ test |
|:--------------------|--------:|-------------:|-------:|----------:|---------------:|---------:|
| modelo A (baseline) |  0.0087 |       0.0444 | 0.0264 |  nan      |       nan      | nan      |
| modelo B (baseline) |  0.015  |       0.0584 | 0.0177 |    0.0063 |         0.014  |  -0.0087 |
| modelo C (baseline) |  0.001  |       0.0417 | 0.0098 |   -0.014  |        -0.0167 |  -0.0079 |
| modelo D (baseline) |  0.0014 |       0.0239 | 0.0001 |    0.0004 |        -0.0178 |  -0.0097 |

![NQ modelos](NQ_modelos_periodos.png)

### GC
| configuración       | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:--------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| modelo A (baseline) | train      |     6437 |         21.9 |        -0.0652 |               0.0257 | -4.5  |           0.846 |   -102922 |     -22.02 |    -1.18 |
| modelo A (baseline) | validation |     2218 |         23.3 |        -0.0386 |               0.0207 | -1.52 |           0.888 |    -35811 |      -9.53 |    -0.99 |
| modelo A (baseline) | test       |     2201 |         23.8 |        -0.0413 |              -0.0138 | -1.89 |           0.837 |   -121730 |     -29.5  |    -1.21 |
| modelo B (baseline) | train      |     4779 |         22.6 |        -0.0624 |               0.0308 | -3.34 |           0.859 |    -77866 |     -17.32 |    -0.99 |
| modelo B (baseline) | validation |     1633 |         23.6 |        -0.0356 |               0.0264 | -1.05 |           0.879 |    -31310 |      -7.94 |    -0.95 |
| modelo B (baseline) | test       |     1629 |         24.1 |        -0.0512 |              -0.0225 | -1.91 |           0.821 |   -109145 |     -22.43 |    -1.29 |
| modelo C (baseline) | train      |     4332 |         22.6 |        -0.0477 |               0.0464 | -2.38 |           0.899 |    -50497 |     -14.05 |    -0.66 |
| modelo C (baseline) | validation |     1489 |         23.2 |        -0.0219 |               0.0404 | -0.61 |           0.905 |    -22284 |      -7.57 |    -0.67 |
| modelo C (baseline) | test       |     1516 |         23.4 |        -0.0534 |              -0.0246 | -1.89 |           0.803 |   -110297 |     -22.54 |    -1.4  |
| modelo D (baseline) | train      |     3965 |         23.8 |        -0.0534 |               0.0423 | -2.42 |           0.896 |    -50944 |     -13.6  |    -0.68 |
| modelo D (baseline) | validation |     1367 |         23.7 |        -0.0186 |               0.0444 | -0.46 |           0.911 |    -20694 |      -8.18 |    -0.61 |
| modelo D (baseline) | test       |     1370 |         24.2 |        -0.0481 |              -0.0187 | -1.51 |           0.832 |    -91539 |     -19.12 |    -1.18 |

Expectativa neta (R) y aporte de cada paso:

| configuración       |   train |   validation |    test |   Δ train |   Δ validation |   Δ test |
|:--------------------|--------:|-------------:|--------:|----------:|---------------:|---------:|
| modelo A (baseline) | -0.0652 |      -0.0386 | -0.0413 |  nan      |       nan      | nan      |
| modelo B (baseline) | -0.0624 |      -0.0356 | -0.0512 |    0.0028 |         0.003  |  -0.0099 |
| modelo C (baseline) | -0.0477 |      -0.0219 | -0.0534 |    0.0147 |         0.0137 |  -0.0022 |
| modelo D (baseline) | -0.0534 |      -0.0186 | -0.0481 |   -0.0057 |         0.0033 |   0.0053 |

![GC modelos](GC_modelos_periodos.png)

### Comparación entre instrumentos (sin ordenar por "mejor")
|                                              |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:---------------------------------------------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| ('MNQ', 'modelo A (baseline)', 'train')      |     4607 |         27.6 |        -0.0271 |               0.0467 | -1.64 |           0.889 |    -25144 |     -58    |    -0.73 |
| ('MNQ', 'modelo A (baseline)', 'validation') |     1679 |         28.8 |         0.0308 |               0.0525 |  1.1  |           1.084 |     10536 |      -7.7  |     0.75 |
| ('MNQ', 'modelo A (baseline)', 'test')       |     1540 |         31   |         0.0193 |               0.0375 |  0.6  |           1.047 |      5499 |     -11.64 |     0.42 |
| ('MNQ', 'modelo B (baseline)', 'train')      |     3286 |         29.3 |        -0.0161 |               0.0532 | -0.88 |           0.937 |    -12956 |     -35.17 |    -0.38 |
| ('MNQ', 'modelo B (baseline)', 'validation') |     1110 |         32.4 |         0.0488 |               0.0703 |  1.51 |           1.117 |      9946 |      -6.4  |     0.9  |
| ('MNQ', 'modelo B (baseline)', 'test')       |      953 |         32.6 |         0.0081 |               0.026  |  0.23 |           1.034 |      2350 |     -10.21 |     0.27 |
| ('MNQ', 'modelo C (baseline)', 'train')      |     2841 |         29.4 |        -0.0321 |               0.0397 | -1.72 |           0.879 |    -19336 |     -42.72 |    -0.75 |
| ('MNQ', 'modelo C (baseline)', 'validation') |      961 |         31.6 |         0.0343 |               0.0561 |  1.05 |           1.068 |      4746 |      -9.07 |     0.52 |
| ('MNQ', 'modelo C (baseline)', 'test')       |      808 |         32.8 |        -0.0028 |               0.0157 | -0.08 |           1.027 |      1502 |     -12.75 |     0.2  |
| ('MNQ', 'modelo D (baseline)', 'train')      |     2516 |         30.5 |        -0.0344 |               0.0373 | -1.72 |           0.875 |    -18582 |     -39.97 |    -0.75 |
| ('MNQ', 'modelo D (baseline)', 'validation') |      854 |         31.7 |         0.0135 |               0.0353 |  0.38 |           1.029 |      1901 |     -12.53 |     0.24 |
| ('MNQ', 'modelo D (baseline)', 'test')       |      698 |         34.8 |        -0.0138 |               0.0049 | -0.36 |           0.984 |      -772 |     -13.44 |    -0.06 |
| ('MGC', 'modelo A (baseline)', 'train')      |     4248 |         19.3 |        -0.1414 |               0.0194 | -7.66 |           0.677 |    -46171 |     -92.87 |    -2.74 |
| ('MGC', 'modelo A (baseline)', 'validation') |     2195 |         22.3 |        -0.0686 |               0.0191 | -2.71 |           0.789 |    -25615 |     -54.29 |    -1.82 |
| ('MGC', 'modelo A (baseline)', 'test')       |     1912 |         22   |        -0.0452 |               0.0003 | -1.68 |           0.839 |    -16502 |     -42.39 |    -1.18 |
| ('MGC', 'modelo B (baseline)', 'train')      |     3907 |         20.7 |        -0.1203 |               0.0341 | -5.57 |           0.773 |    -43921 |     -89.71 |    -1.99 |
| ('MGC', 'modelo B (baseline)', 'validation') |     1625 |         22.8 |        -0.0642 |               0.0276 | -1.88 |           0.822 |    -19162 |     -45.19 |    -1.18 |
| ('MGC', 'modelo B (baseline)', 'test')       |     1469 |         23   |        -0.06   |              -0.0141 | -1.99 |           0.826 |    -15336 |     -31.76 |    -1.22 |
| ('MGC', 'modelo C (baseline)', 'train')      |     3970 |         21.1 |        -0.1033 |               0.0441 | -4.79 |           0.798 |    -42143 |     -86.56 |    -1.75 |
| ('MGC', 'modelo C (baseline)', 'validation') |     1487 |         22.5 |        -0.0514 |               0.0408 | -1.42 |           0.837 |    -15962 |     -44.63 |    -0.97 |
| ('MGC', 'modelo C (baseline)', 'test')       |     1357 |         22.5 |        -0.0658 |              -0.0194 | -2.09 |           0.808 |    -15372 |     -31.36 |    -1.27 |
| ('MGC', 'modelo D (baseline)', 'train')      |     3639 |         22.4 |        -0.11   |               0.0399 | -4.67 |           0.805 |    -41761 |     -86.02 |    -1.68 |
| ('MGC', 'modelo D (baseline)', 'validation') |     1367 |         23   |        -0.0488 |               0.0444 | -1.21 |           0.863 |    -13858 |     -43.59 |    -0.76 |
| ('MGC', 'modelo D (baseline)', 'test')       |     1249 |         23.5 |        -0.0572 |              -0.0105 | -1.64 |           0.834 |    -13862 |     -28.77 |    -1.13 |
| ('NQ', 'modelo A (baseline)', 'train')       |     5063 |         28   |         0.0087 |               0.047  |  0.56 |           1.069 |     72662 |      -6.28 |     0.5  |
| ('NQ', 'modelo A (baseline)', 'validation')  |     1740 |         29.4 |         0.0444 |               0.0562 |  1.63 |           1.15  |    119868 |      -4.24 |     1.23 |
| ('NQ', 'modelo A (baseline)', 'test')        |     1727 |         30.6 |         0.0264 |               0.0358 |  0.91 |           0.995 |     -5862 |     -19.2  |     0.01 |
| ('NQ', 'modelo B (baseline)', 'train')       |     3378 |         30   |         0.015  |               0.0528 |  0.84 |           1.064 |     43846 |      -4.74 |     0.4  |
| ('NQ', 'modelo B (baseline)', 'validation')  |     1147 |         32.8 |         0.0584 |               0.0702 |  1.86 |           1.221 |    118034 |      -3.23 |     1.55 |
| ('NQ', 'modelo B (baseline)', 'test')        |     1101 |         31.4 |         0.0177 |               0.0268 |  0.54 |           1.064 |     47832 |      -8.32 |     0.47 |
| ('NQ', 'modelo C (baseline)', 'train')       |     2971 |         30.2 |         0.001  |               0.0396 |  0.06 |           1.03  |     17578 |      -3.92 |     0.18 |
| ('NQ', 'modelo C (baseline)', 'validation')  |      997 |         32   |         0.0417 |               0.0535 |  1.31 |           1.175 |     79294 |      -3.7  |     1.14 |
| ('NQ', 'modelo C (baseline)', 'test')        |      951 |         31.8 |         0.0098 |               0.0191 |  0.3  |           1.051 |     31700 |     -10.49 |     0.36 |
| ('NQ', 'modelo D (baseline)', 'train')       |     2604 |         31.2 |         0.0014 |               0.0403 |  0.07 |           1.059 |     30611 |      -3.24 |     0.32 |
| ('NQ', 'modelo D (baseline)', 'validation')  |      881 |         32   |         0.0239 |               0.0357 |  0.69 |           1.117 |     50670 |      -4.7  |     0.79 |
| ('NQ', 'modelo D (baseline)', 'test')        |      831 |         33.3 |         0.0001 |               0.0094 |  0    |           1.022 |     12516 |     -12.62 |     0.17 |
| ('GC', 'modelo A (baseline)', 'train')       |     6437 |         21.9 |        -0.0652 |               0.0257 | -4.5  |           0.846 |   -102922 |     -22.02 |    -1.18 |
| ('GC', 'modelo A (baseline)', 'validation')  |     2218 |         23.3 |        -0.0386 |               0.0207 | -1.52 |           0.888 |    -35811 |      -9.53 |    -0.99 |
| ('GC', 'modelo A (baseline)', 'test')        |     2201 |         23.8 |        -0.0413 |              -0.0138 | -1.89 |           0.837 |   -121730 |     -29.5  |    -1.21 |
| ('GC', 'modelo B (baseline)', 'train')       |     4779 |         22.6 |        -0.0624 |               0.0308 | -3.34 |           0.859 |    -77866 |     -17.32 |    -0.99 |
| ('GC', 'modelo B (baseline)', 'validation')  |     1633 |         23.6 |        -0.0356 |               0.0264 | -1.05 |           0.879 |    -31310 |      -7.94 |    -0.95 |
| ('GC', 'modelo B (baseline)', 'test')        |     1629 |         24.1 |        -0.0512 |              -0.0225 | -1.91 |           0.821 |   -109145 |     -22.43 |    -1.29 |
| ('GC', 'modelo C (baseline)', 'train')       |     4332 |         22.6 |        -0.0477 |               0.0464 | -2.38 |           0.899 |    -50497 |     -14.05 |    -0.66 |
| ('GC', 'modelo C (baseline)', 'validation')  |     1489 |         23.2 |        -0.0219 |               0.0404 | -0.61 |           0.905 |    -22284 |      -7.57 |    -0.67 |
| ('GC', 'modelo C (baseline)', 'test')        |     1516 |         23.4 |        -0.0534 |              -0.0246 | -1.89 |           0.803 |   -110297 |     -22.54 |    -1.4  |
| ('GC', 'modelo D (baseline)', 'train')       |     3965 |         23.8 |        -0.0534 |               0.0423 | -2.42 |           0.896 |    -50944 |     -13.6  |    -0.68 |
| ('GC', 'modelo D (baseline)', 'validation')  |     1367 |         23.7 |        -0.0186 |               0.0444 | -0.46 |           0.911 |    -20694 |      -8.18 |    -0.61 |
| ('GC', 'modelo D (baseline)', 'test')        |     1370 |         24.2 |        -0.0481 |              -0.0187 | -1.51 |           0.832 |    -91539 |     -19.12 |    -1.18 |

### Tipos de entrada, filtros de tendencia y franjas (train y validation)
#### MNQ
| variante            | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:--------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| modelo A / state    | train      |     4607 |         27.6 |        -0.0271 |               0.0467 | -1.64 |           0.889 |    -25144 |     -58    |    -0.73 |
| modelo A / state    | validation |     1679 |         28.8 |         0.0308 |               0.0525 |  1.1  |           1.084 |     10536 |      -7.7  |     0.75 |
| modelo A / breakout | train      |     3348 |         25.2 |        -0.0505 |               0.0233 | -2.97 |           0.828 |    -26747 |     -58.16 |    -1.1  |
| modelo A / breakout | validation |     1280 |         28   |         0.0368 |               0.0578 |  1.21 |           1.124 |     10440 |      -8.03 |     0.85 |
| modelo A / pullback | train      |     2870 |         29.3 |        -0.0515 |               0.0234 | -2.52 |           0.828 |    -26149 |     -57.23 |    -1.03 |
| modelo A / pullback | validation |     1048 |         31.3 |         0.018  |               0.039  |  0.53 |           1.049 |      3900 |     -11.05 |     0.4  |
| modelo B / state    | train      |     3286 |         29.3 |        -0.0161 |               0.0532 | -0.88 |           0.937 |    -12956 |     -35.17 |    -0.38 |
| modelo B / state    | validation |     1110 |         32.4 |         0.0488 |               0.0703 |  1.51 |           1.117 |      9946 |      -6.4  |     0.9  |
| modelo B / breakout | train      |     2201 |         26.5 |        -0.043  |               0.0268 | -2.26 |           0.843 |    -19242 |     -39.45 |    -0.98 |
| modelo B / breakout | validation |      751 |         31.4 |         0.0347 |               0.0559 |  1.02 |           1.112 |      5407 |      -6.38 |     0.71 |
| modelo B / pullback | train      |     1706 |         31.4 |        -0.0314 |               0.0391 | -1.25 |           0.884 |    -13224 |     -35.58 |    -0.57 |
| modelo B / pullback | validation |      566 |         34.1 |         0.0478 |               0.0694 |  1.06 |           1.13  |      5470 |      -5.53 |     0.71 |
| modelo C / state    | train      |     2841 |         29.4 |        -0.0321 |               0.0397 | -1.72 |           0.879 |    -19336 |     -42.72 |    -0.75 |
| modelo C / state    | validation |      961 |         31.6 |         0.0343 |               0.0561 |  1.05 |           1.068 |      4746 |      -9.07 |     0.52 |
| modelo C / breakout | train      |     1939 |         26.3 |        -0.0594 |               0.0135 | -3.04 |           0.783 |    -21786 |     -44.98 |    -1.28 |
| modelo C / breakout | validation |      664 |         31.2 |         0.0474 |               0.0689 |  1.29 |           1.141 |      5996 |      -6.06 |     0.81 |
| modelo C / pullback | train      |     1452 |         31   |        -0.0507 |               0.022  | -1.91 |           0.822 |    -16886 |     -37.2  |    -0.9  |
| modelo C / pullback | validation |      477 |         33.3 |         0.0063 |               0.0282 |  0.14 |           1.041 |      1409 |      -6.32 |     0.24 |
| modelo D / state    | train      |     2516 |         30.5 |        -0.0344 |               0.0373 | -1.72 |           0.875 |    -18582 |     -39.97 |    -0.75 |
| modelo D / state    | validation |      854 |         31.7 |         0.0135 |               0.0353 |  0.38 |           1.029 |      1901 |     -12.53 |     0.24 |
| modelo D / breakout | train      |     1494 |         25.9 |        -0.0785 |              -0.0058 | -3.67 |           0.729 |    -21565 |     -44.84 |    -1.51 |
| modelo D / breakout | validation |      520 |         30.2 |         0.0138 |               0.0352 |  0.34 |           1.047 |      1570 |      -5.97 |     0.27 |
| modelo D / pullback | train      |     1309 |         32.6 |        -0.047  |               0.0267 | -1.66 |           0.835 |    -14636 |     -34.95 |    -0.78 |
| modelo D / pullback | validation |      433 |         33.7 |        -0.0053 |               0.0166 | -0.11 |           1.004 |       147 |      -7.99 |     0.05 |

| variante     | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:-------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| sin filtro   | train      |     4607 |         27.6 |        -0.0271 |               0.0467 | -1.64 |           0.889 |    -25144 |     -58    |    -0.73 |
| sin filtro   | validation |     1679 |         28.8 |         0.0308 |               0.0525 |  1.1  |           1.084 |     10536 |      -7.7  |     0.75 |
| ema200_slope | train      |     3161 |         28.8 |        -0.0293 |               0.0408 | -1.62 |           0.89  |    -20211 |     -43.66 |    -0.74 |
| ema200_slope | validation |     1086 |         32.9 |         0.0406 |               0.062  |  1.32 |           1.112 |      8842 |      -7.31 |     0.86 |
| vwap_slope   | train      |     3435 |         31.2 |        -0.0269 |               0.0411 | -1.61 |           0.889 |    -20839 |     -48.38 |    -0.77 |
| vwap_slope   | validation |     1195 |         33.4 |         0.0371 |               0.0573 |  1.22 |           1.114 |     10250 |      -8.13 |     0.9  |

Desglose del baseline por franja horaria:

|    | periodo    | franja      |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|---:|:-----------|:------------|---------:|----------:|---------------:|-------------:|------:|
|  0 | train      | 09:30-11:30 |     3399 |    -25616 |        -0.0378 |         26.7 | -1.82 |
|  1 | train      | 11:30-13:30 |      736 |      1342 |         0.0046 |         27   |  0.15 |
|  2 | train      | 13:30-16:00 |      472 |      -869 |         0.0001 |         35.4 |  0    |
|  0 | validation | 09:30-11:30 |     1214 |      6627 |         0.0349 |         29.4 |  1.05 |
|  1 | validation | 11:30-13:30 |      279 |      3597 |         0.0513 |         26.5 |  0.87 |
|  2 | validation | 13:30-16:00 |      186 |       312 |        -0.0263 |         28.5 | -0.28 |

Solo operando en una ventana:

| variante         | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:-----------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| solo 09:30-11:30 | train      |     3385 |         26.7 |        -0.0373 |               0.0405 | -1.8  |           0.858 |    -26005 |     -54.83 |    -0.85 |
| solo 11:30-13:30 | train      |     2829 |         29.4 |        -0.0287 |               0.0342 | -1.71 |           0.886 |    -17060 |     -38.82 |    -0.73 |
| solo 13:30-16:00 | train      |     2677 |         36.4 |        -0.0567 |               0.0251 | -3.41 |           0.807 |    -26124 |     -53.32 |    -1.36 |
| solo 09:30-11:30 | validation |     1208 |         29.5 |         0.0375 |               0.0597 |  1.12 |           1.079 |      7408 |      -6.4  |     0.65 |
| solo 11:30-13:30 | validation |      957 |         30.2 |         0.0363 |               0.0553 |  1.18 |           1.106 |      7067 |     -12.7  |     0.78 |
| solo 13:30-16:00 | validation |      949 |         41.4 |         0.0638 |               0.0875 |  1.84 |           1.156 |     11628 |      -5.33 |     1.05 |

#### NQ
| variante            | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:--------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| modelo A / state    | train      |     5063 |         28   |         0.0087 |               0.047  |  0.56 |           1.069 |     72662 |      -6.28 |     0.5  |
| modelo A / state    | validation |     1740 |         29.4 |         0.0444 |               0.0562 |  1.63 |           1.15  |    119868 |      -4.24 |     1.23 |
| modelo A / breakout | train      |     3950 |         26.1 |        -0.0099 |               0.0264 | -0.64 |           1.056 |     43739 |      -7.32 |     0.35 |
| modelo A / breakout | validation |     1356 |         28.3 |         0.0414 |               0.0528 |  1.42 |           1.092 |     55854 |      -9.37 |     0.68 |
| modelo A / pullback | train      |     3289 |         30   |        -0.015  |               0.0224 | -0.81 |           1.018 |     14052 |      -6.71 |     0.13 |
| modelo A / pullback | validation |     1096 |         31.7 |         0.0283 |               0.0397 |  0.86 |           1.091 |     52553 |      -5.84 |     0.68 |
| modelo B / state    | train      |     3378 |         30   |         0.015  |               0.0528 |  0.84 |           1.064 |     43846 |      -4.74 |     0.4  |
| modelo B / state    | validation |     1147 |         32.8 |         0.0584 |               0.0702 |  1.86 |           1.221 |    118034 |      -3.23 |     1.55 |
| modelo B / breakout | train      |     2327 |         27.5 |        -0.0092 |               0.0279 | -0.5  |           1.022 |      9399 |      -3.1  |     0.12 |
| modelo B / breakout | validation |      794 |         32   |         0.0404 |               0.0519 |  1.24 |           1.189 |     64620 |      -3.27 |     1.1  |
| modelo B / pullback | train      |     1762 |         31.6 |        -0.0006 |               0.0375 | -0.03 |           1.031 |     12293 |      -3.79 |     0.16 |
| modelo B / pullback | validation |      590 |         34.7 |         0.0603 |               0.072  |  1.37 |           1.206 |     60453 |      -2.92 |     1.07 |
| modelo C / state    | train      |     2971 |         30.2 |         0.001  |               0.0396 |  0.06 |           1.03  |     17578 |      -3.92 |     0.18 |
| modelo C / state    | validation |      997 |         32   |         0.0417 |               0.0535 |  1.31 |           1.175 |     79294 |      -3.7  |     1.14 |
| modelo C / breakout | train      |     2084 |         27.4 |        -0.0257 |               0.0125 | -1.38 |           1.004 |      1647 |      -3.95 |     0.03 |
| modelo C / breakout | validation |      706 |         31.6 |         0.0507 |               0.0622 |  1.44 |           1.206 |     62584 |      -3.05 |     1.11 |
| modelo C / pullback | train      |     1507 |         31.3 |        -0.018  |               0.0212 | -0.69 |           1.004 |      1314 |      -4.26 |     0.03 |
| modelo C / pullback | validation |      499 |         33.9 |         0.013  |               0.0248 |  0.29 |           1.085 |     21335 |      -3.92 |     0.44 |
| modelo D / state    | train      |     2604 |         31.2 |         0.0014 |               0.0403 |  0.07 |           1.059 |     30611 |      -3.24 |     0.32 |
| modelo D / state    | validation |      881 |         32   |         0.0239 |               0.0357 |  0.69 |           1.117 |     50670 |      -4.7  |     0.79 |
| modelo D / breakout | train      |     1597 |         27   |        -0.0435 |              -0.0052 | -2.13 |           0.938 |    -18461 |      -6.58 |    -0.25 |
| modelo D / breakout | validation |      551 |         30.7 |         0.0192 |               0.0307 |  0.49 |           1.113 |     28097 |      -3.19 |     0.59 |
| modelo D / pullback | train      |     1349 |         32.8 |        -0.0138 |               0.0261 | -0.5  |           1.057 |     16750 |      -3.89 |     0.23 |
| modelo D / pullback | validation |      451 |         34.4 |         0.0033 |               0.0152 |  0.07 |           1.073 |     17301 |      -4.5  |     0.38 |

| variante     | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:-------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| sin filtro   | train      |     5063 |         28   |         0.0087 |               0.047  |  0.56 |           1.069 |     72662 |      -6.28 |     0.5  |
| sin filtro   | validation |     1740 |         29.4 |         0.0444 |               0.0562 |  1.63 |           1.15  |    119868 |      -4.24 |     1.23 |
| ema200_slope | train      |     3301 |         29.6 |         0.0051 |               0.0428 |  0.29 |           1.027 |     18215 |      -5.75 |     0.18 |
| ema200_slope | validation |     1120 |         33.3 |         0.0486 |               0.0603 |  1.62 |           1.191 |     97991 |      -3.13 |     1.35 |
| vwap_slope   | train      |     3645 |         31.6 |         0.0045 |               0.0404 |  0.28 |           1.072 |     58045 |      -4.67 |     0.48 |
| vwap_slope   | validation |     1231 |         33.5 |         0.0471 |               0.0581 |  1.59 |           1.136 |     86651 |      -4.99 |     1.09 |

Desglose del baseline por franja horaria:

|    | periodo    | franja      |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|---:|:-----------|:------------|---------:|----------:|---------------:|-------------:|------:|
|  0 | train      | 09:30-11:30 |     3839 |     47451 |         0.0043 |         27.9 |  0.23 |
|  1 | train      | 11:30-13:30 |      801 |     13950 |         0.0097 |         24.3 |  0.34 |
|  2 | train      | 13:30-16:00 |      423 |     11261 |         0.0465 |         35.5 |  1.13 |
|  0 | validation | 09:30-11:30 |     1288 |    100212 |         0.0479 |         30.4 |  1.5  |
|  1 | validation | 11:30-13:30 |      269 |     25151 |         0.0506 |         24.9 |  0.86 |
|  2 | validation | 13:30-16:00 |      183 |     -5494 |         0.0113 |         29.5 |  0.12 |

Solo operando en una ventana:

| variante         | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:-----------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| solo 09:30-11:30 | train      |     3839 |         27.9 |         0.0043 |               0.0435 |  0.23 |           1.057 |     47451 |      -5.75 |     0.37 |
| solo 11:30-13:30 | train      |     2964 |         30.1 |         0.0054 |               0.039  |  0.33 |           1.073 |     45928 |      -5.34 |     0.44 |
| solo 13:30-16:00 | train      |     2854 |         37.4 |        -0.0217 |               0.0214 | -1.36 |           0.997 |     -1464 |      -7.29 |    -0    |
| solo 09:30-11:30 | validation |     1288 |         30.4 |         0.0479 |               0.0598 |  1.5  |           1.163 |    100212 |      -3.79 |     1.14 |
| solo 11:30-13:30 | validation |      998 |         30.2 |         0.043  |               0.0533 |  1.44 |           1.154 |     75962 |      -5.8  |     1.09 |
| solo 13:30-16:00 | validation |      958 |         41.9 |         0.0759 |               0.089  |  2.21 |           1.183 |     74842 |      -3.93 |     1.27 |

#### MGC
| variante            | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:--------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| modelo A / state    | train      |     4248 |         19.3 |        -0.1414 |               0.0194 | -7.66 |           0.677 |    -46171 |     -92.87 |    -2.74 |
| modelo A / state    | validation |     2195 |         22.3 |        -0.0686 |               0.0191 | -2.71 |           0.789 |    -25615 |     -54.29 |    -1.82 |
| modelo A / breakout | train      |     3989 |         18.3 |        -0.1357 |               0.0292 | -6.64 |           0.713 |    -45356 |     -91.48 |    -2.43 |
| modelo A / breakout | validation |     1957 |         22   |        -0.0827 |               0.0089 | -3.13 |           0.765 |    -26775 |     -55.28 |    -2.14 |
| modelo A / pullback | train      |     4327 |         22.6 |        -0.0989 |               0.0505 | -4.32 |           0.766 |    -42981 |     -85.96 |    -1.64 |
| modelo A / pullback | validation |     1612 |         24.6 |        -0.0638 |               0.0279 | -1.86 |           0.849 |    -19718 |     -42.71 |    -1.2  |
| modelo B / state    | train      |     3907 |         20.7 |        -0.1203 |               0.0341 | -5.57 |           0.773 |    -43921 |     -89.71 |    -1.99 |
| modelo B / state    | validation |     1625 |         22.8 |        -0.0642 |               0.0276 | -1.88 |           0.822 |    -19162 |     -45.19 |    -1.18 |
| modelo B / breakout | train      |     3637 |         20   |        -0.1045 |               0.0456 | -4.53 |           0.797 |    -40614 |     -83.65 |    -1.62 |
| modelo B / breakout | validation |     1329 |         22.4 |        -0.0594 |               0.0358 | -1.62 |           0.837 |    -15427 |     -40.61 |    -1.03 |
| modelo B / pullback | train      |     2781 |         25.1 |        -0.0787 |               0.0608 | -2.74 |           0.843 |    -31681 |     -65.75 |    -0.97 |
| modelo B / pullback | validation |      944 |         25.6 |        -0.0577 |               0.0343 | -1.21 |           0.862 |    -11629 |     -28.54 |    -0.79 |
| modelo C / state    | train      |     3970 |         21.1 |        -0.1033 |               0.0441 | -4.79 |           0.798 |    -42143 |     -86.56 |    -1.75 |
| modelo C / state    | validation |     1487 |         22.5 |        -0.0514 |               0.0408 | -1.42 |           0.837 |    -15962 |     -44.63 |    -0.97 |
| modelo C / breakout | train      |     3288 |         20.3 |        -0.1082 |               0.0423 | -4.52 |           0.789 |    -40133 |     -82.96 |    -1.68 |
| modelo C / breakout | validation |     1217 |         22.5 |        -0.0491 |               0.0465 | -1.24 |           0.862 |    -12921 |     -35.34 |    -0.83 |
| modelo C / pullback | train      |     2404 |         25.1 |        -0.083  |               0.0572 | -2.72 |           0.83  |    -30758 |     -63.31 |    -1.01 |
| modelo C / pullback | validation |      805 |         25.1 |        -0.0439 |               0.0488 | -0.8  |           0.887 |     -8467 |     -25.65 |    -0.56 |
| modelo D / state    | train      |     3639 |         22.4 |        -0.11   |               0.0399 | -4.67 |           0.805 |    -41761 |     -86.02 |    -1.68 |
| modelo D / state    | validation |     1367 |         23   |        -0.0488 |               0.0444 | -1.21 |           0.863 |    -13858 |     -43.59 |    -0.76 |
| modelo D / breakout | train      |     2893 |         22.3 |        -0.0907 |               0.0555 | -3.48 |           0.823 |    -35380 |     -75.1  |    -1.31 |
| modelo D / breakout | validation |     1045 |         22.8 |        -0.0849 |               0.0107 | -2.14 |           0.778 |    -16920 |     -43.42 |    -1.38 |
| modelo D / pullback | train      |     2223 |         25.6 |        -0.0869 |               0.0555 | -2.62 |           0.831 |    -30274 |     -63.57 |    -0.97 |
| modelo D / pullback | validation |      740 |         26.1 |        -0.028  |               0.0657 | -0.46 |           0.919 |     -5931 |     -24.98 |    -0.35 |

| variante     | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:-------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| sin filtro   | train      |     4248 |         19.3 |        -0.1414 |               0.0194 | -7.66 |           0.677 |    -46171 |     -92.87 |    -2.74 |
| sin filtro   | validation |     2195 |         22.3 |        -0.0686 |               0.0191 | -2.71 |           0.789 |    -25615 |     -54.29 |    -1.82 |
| ema200_slope | train      |     4117 |         20.5 |        -0.1113 |               0.038  | -5.3  |           0.784 |    -43457 |     -88.52 |    -1.88 |
| ema200_slope | validation |     1600 |         23   |        -0.0601 |               0.0318 | -1.76 |           0.836 |    -17455 |     -42.77 |    -1.05 |
| vwap_slope   | train      |     4158 |         20.1 |        -0.12   |               0.0437 | -5.1  |           0.768 |    -44744 |     -90.46 |    -1.87 |
| vwap_slope   | validation |     1769 |         21.7 |        -0.1148 |              -0.0198 | -3.56 |           0.764 |    -29405 |     -58.98 |    -2.12 |

Desglose del baseline por franja horaria:

|    | periodo    | franja                   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|---:|:-----------|:-------------------------|---------:|----------:|---------------:|-------------:|------:|
|  0 | train      | apertura NY 08:20-09:30  |      236 |     -6028 |        -0.2666 |         18.6 | -3.08 |
|  1 | train      | europea 03:00-08:20      |     3641 |    -37170 |        -0.134  |         18.8 | -6.63 |
|  2 | train      | resto NY 11:30-13:30     |       86 |      -265 |        -0.0856 |         32.6 | -1.33 |
|  3 | train      | solapamiento 09:30-11:30 |      285 |     -2708 |        -0.1492 |         22.1 | -2.52 |
|  0 | validation | apertura NY 08:20-09:30  |      149 |      1603 |         0.0194 |         22.1 |  0.12 |
|  1 | validation | europea 03:00-08:20      |     1854 |    -26252 |        -0.0828 |         21.3 | -3.18 |
|  2 | validation | resto NY 11:30-13:30     |       28 |      -107 |         0.0408 |         39.3 |  0.39 |
|  3 | validation | solapamiento 09:30-11:30 |      164 |      -859 |        -0.006  |         30.5 | -0.07 |

Solo operando en una ventana:

| variante                      | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:------------------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| solo europea 03:00-08:20      | train      |     4074 |         19.2 |        -0.1307 |               0.0263 | -6.84 |           0.683 |    -45171 |     -91.33 |    -2.42 |
| solo apertura NY 08:20-09:30  | train      |     2856 |         22.9 |        -0.1096 |               0.0481 | -3.22 |           0.858 |    -38105 |     -81.9  |    -1.14 |
| solo solapamiento 09:30-11:30 | train      |     2978 |         28.5 |        -0.1094 |               0.0222 | -4.73 |           0.775 |    -39079 |     -81.53 |    -1.84 |
| solo resto NY 11:30-13:30     | train      |     2311 |         37.5 |        -0.1066 |              -0.0017 | -8.36 |           0.611 |    -33246 |     -66.78 |    -3.04 |
| solo europea 03:00-08:20      | validation |     1854 |         21.3 |        -0.0832 |               0.0057 | -3.19 |           0.735 |    -25852 |     -55    |    -2.13 |
| solo apertura NY 08:20-09:30  | validation |      989 |         21.8 |        -0.0338 |               0.0715 | -0.53 |           0.932 |     -9269 |     -28.85 |    -0.37 |
| solo solapamiento 09:30-11:30 | validation |     1146 |         29.5 |        -0.039  |               0.0415 | -0.96 |           0.904 |    -11218 |     -26.15 |    -0.72 |
| solo resto NY 11:30-13:30     | validation |      788 |         40.6 |        -0.0642 |              -0.0007 | -3.04 |           0.747 |    -10120 |     -23.23 |    -2.01 |

#### GC
| variante            | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:--------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| modelo A / state    | train      |     6437 |         21.9 |        -0.0652 |               0.0257 | -4.5  |           0.846 |   -102922 |     -22.02 |    -1.18 |
| modelo A / state    | validation |     2218 |         23.3 |        -0.0386 |               0.0207 | -1.52 |           0.888 |    -35811 |      -9.53 |    -0.99 |
| modelo A / breakout | train      |     5761 |         20.6 |        -0.0613 |               0.0333 | -3.7  |           0.848 |    -96369 |     -20.21 |    -1.13 |
| modelo A / breakout | validation |     1976 |         23   |        -0.0512 |               0.0107 | -1.94 |           0.901 |    -29513 |      -7.92 |    -0.85 |
| modelo A / pullback | train      |     4783 |         23.9 |        -0.0489 |               0.0459 | -2.34 |           0.847 |    -94132 |     -18.83 |    -1.16 |
| modelo A / pullback | validation |     1616 |         25.2 |        -0.0342 |               0.0277 | -1    |           0.961 |    -10700 |      -5.83 |    -0.29 |
| modelo B / state    | train      |     4779 |         22.6 |        -0.0624 |               0.0308 | -3.34 |           0.859 |    -77866 |     -17.32 |    -0.99 |
| modelo B / state    | validation |     1633 |         23.6 |        -0.0356 |               0.0264 | -1.05 |           0.879 |    -31310 |      -7.94 |    -0.95 |
| modelo B / breakout | train      |     3930 |         21.5 |        -0.0449 |               0.0516 | -2.05 |           0.888 |    -51374 |     -13.24 |    -0.71 |
| modelo B / breakout | validation |     1331 |         22.9 |        -0.0288 |               0.0355 | -0.79 |           0.944 |    -11732 |      -5.18 |    -0.38 |
| modelo B / pullback | train      |     2794 |         26.2 |        -0.0333 |               0.0606 | -1.17 |           0.888 |    -43084 |     -10.58 |    -0.68 |
| modelo B / pullback | validation |      944 |         26.4 |        -0.0279 |               0.0343 | -0.59 |           0.93  |    -11985 |      -4.07 |    -0.43 |
| modelo C / state    | train      |     4332 |         22.6 |        -0.0477 |               0.0464 | -2.38 |           0.899 |    -50497 |     -14.05 |    -0.66 |
| modelo C / state    | validation |     1489 |         23.2 |        -0.0219 |               0.0404 | -0.61 |           0.905 |    -22284 |      -7.57 |    -0.67 |
| modelo C / breakout | train      |     3544 |         21.8 |        -0.0462 |               0.0507 | -2.02 |           0.904 |    -39874 |     -12.23 |    -0.57 |
| modelo C / breakout | validation |     1219 |         23   |        -0.0185 |               0.0461 | -0.47 |           0.964 |     -6896 |      -3.76 |    -0.22 |
| modelo C / pullback | train      |     2415 |         26.4 |        -0.0369 |               0.0575 | -1.21 |           0.903 |    -31643 |      -8.41 |    -0.53 |
| modelo C / pullback | validation |      805 |         26   |        -0.0138 |               0.0488 | -0.25 |           0.945 |     -8167 |      -3.78 |    -0.3  |
| modelo D / state    | train      |     3965 |         23.8 |        -0.0534 |               0.0423 | -2.42 |           0.896 |    -50944 |     -13.6  |    -0.68 |
| modelo D / state    | validation |     1367 |         23.7 |        -0.0186 |               0.0444 | -0.46 |           0.911 |    -20694 |      -8.18 |    -0.61 |
| modelo D / breakout | train      |     2961 |         23.1 |        -0.0457 |               0.0515 | -1.79 |           0.905 |    -34460 |     -10.44 |    -0.53 |
| modelo D / breakout | validation |     1045 |         23.3 |        -0.0539 |               0.0107 | -1.36 |           0.872 |    -22393 |      -6.82 |    -0.87 |
| modelo D / pullback | train      |     2232 |         26.7 |        -0.0399 |               0.056  | -1.21 |           0.892 |    -34293 |      -9.2  |    -0.58 |
| modelo D / pullback | validation |      740 |         26.8 |         0.0024 |               0.0657 |  0.04 |           0.979 |     -2960 |      -3.58 |    -0.1  |

| variante     | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:-------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| sin filtro   | train      |     6437 |         21.9 |        -0.0652 |               0.0257 | -4.5  |           0.846 |   -102922 |     -22.02 |    -1.18 |
| sin filtro   | validation |     2218 |         23.3 |        -0.0386 |               0.0207 | -1.52 |           0.888 |    -35811 |      -9.53 |    -0.99 |
| ema200_slope | train      |     4706 |         22.4 |        -0.0538 |               0.0391 | -2.84 |           0.88  |    -64510 |     -14.76 |    -0.83 |
| ema200_slope | validation |     1607 |         23.9 |        -0.0311 |               0.0309 | -0.92 |           0.879 |    -30197 |      -7.51 |    -0.92 |
| vwap_slope   | train      |     5238 |         21.6 |        -0.0465 |               0.051  | -2.23 |           0.88  |    -83805 |     -17.65 |    -0.88 |
| vwap_slope   | validation |     1778 |         22.3 |        -0.0855 |              -0.0214 | -2.66 |           0.849 |    -48562 |     -10.82 |    -1.34 |

Desglose del baseline por franja horaria:

|    | periodo    | franja                   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|---:|:-----------|:-------------------------|---------:|----------:|---------------:|-------------:|------:|
|  0 | train      | apertura NY 08:20-09:30  |      380 |    -13112 |        -0.1434 |         18.9 | -1.95 |
|  1 | train      | europea 03:00-08:20      |     5483 |    -87451 |        -0.0632 |         21.4 | -4.04 |
|  2 | train      | resto NY 11:30-13:30     |      119 |       842 |        -0.0128 |         37.8 | -0.26 |
|  3 | train      | solapamiento 09:30-11:30 |      455 |     -3201 |        -0.0376 |         26.6 | -0.75 |
|  0 | validation | apertura NY 08:20-09:30  |      153 |     -1424 |         0.0629 |         22.9 |  0.41 |
|  1 | validation | europea 03:00-08:20      |     1868 |    -38510 |        -0.0529 |         22.3 | -2.02 |
|  2 | validation | resto NY 11:30-13:30     |       30 |       170 |         0.0289 |         40   |  0.29 |
|  3 | validation | solapamiento 09:30-11:30 |      167 |      3953 |         0.0172 |         31.7 |  0.21 |

Solo operando en una ventana:

| variante                      | periodo    |   trades |   win_rate_% |   expectancy_R |   expectancy_R_gross |   t_R |   profit_factor |   net_pnl |   max_dd_% |   sharpe |
|:------------------------------|:-----------|---------:|-------------:|---------------:|---------------------:|------:|----------------:|----------:|-----------:|---------:|
| solo europea 03:00-08:20      | train      |     5483 |         21.4 |        -0.0632 |               0.0284 | -4.04 |           0.836 |    -87451 |     -18.24 |    -1.13 |
| solo apertura NY 08:20-09:30  | train      |     2906 |         23.3 |        -0.0528 |               0.0524 | -1.57 |           0.916 |    -43275 |     -12.18 |    -0.55 |
| solo solapamiento 09:30-11:30 | train      |     3350 |         29.6 |        -0.0539 |               0.0289 | -2.5  |           0.939 |    -35134 |     -13.78 |    -0.43 |
| solo resto NY 11:30-13:30     | train      |     2372 |         39   |        -0.0669 |               0.0026 | -5.28 |           0.803 |    -53250 |     -11.7  |    -1.3  |
| solo europea 03:00-08:20      | validation |     1868 |         22.3 |        -0.0529 |               0.0072 | -2.02 |           0.841 |    -38510 |     -10.15 |    -1.25 |
| solo apertura NY 08:20-09:30  | validation |      989 |         22.2 |         0.0004 |               0.0715 |  0.01 |           1.003 |       733 |      -4.97 |     0.04 |
| solo solapamiento 09:30-11:30 | validation |     1146 |         30.1 |        -0.0129 |               0.0415 | -0.32 |           0.976 |     -6618 |      -3.65 |    -0.18 |
| solo resto NY 11:30-13:30     | validation |      788 |         41.4 |        -0.0436 |              -0.0007 | -2.06 |           0.839 |    -20871 |      -5.77 |    -1.14 |

## 10. Optimización secuencial y salidas (train optimiza, validation selecciona)
### MNQ
| etapa                 | opcion                  |   trades_train |   expectancy_R_train |   t_R_train |   expectancy_R_val |   t_R_val |   profit_factor_val |   max_dd_%_val | aceptada   |
|:----------------------|:------------------------|---------------:|---------------------:|------------:|-------------------:|----------:|--------------------:|---------------:|:-----------|
| 1 modelo              | (actual)                |           4607 |              -0.0271 |       -1.64 |             0.0308 |      1.1  |               1.084 |          -7.7  |            |
| 1 modelo              | modelo B                |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  | True       |
| 1 modelo              | modelo C                |           2841 |              -0.0321 |       -1.72 |             0.0343 |      1.05 |               1.068 |          -9.07 | False      |
| 1 modelo              | modelo D                |           2516 |              -0.0344 |       -1.72 |             0.0135 |      0.38 |               1.029 |         -12.53 | False      |
| 2 entrada             | (actual)                |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  |            |
| 2 entrada             | entrada breakout        |           2201 |              -0.043  |       -2.26 |             0.0347 |      1.02 |               1.112 |          -6.38 | False      |
| 2 entrada             | entrada pullback        |           1706 |              -0.0314 |       -1.25 |             0.0478 |      1.06 |               1.13  |          -5.53 | False      |
| 3 filtros (uno a uno) | (actual)                |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  |            |
| 3 filtros (uno a uno) | filtro ema200_slope     |           3137 |              -0.0299 |       -1.64 |             0.0363 |      1.17 |               1.095 |          -7.18 | False      |
| 3 filtros (uno a uno) | filtro vwap_slope       |           2225 |              -0.0232 |       -1.14 |             0.0598 |      1.56 |               1.146 |          -8.61 | False      |
| 4 stop                | (actual)                |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  |            |
| 4 stop                | stop atr 1.0            |           3411 |              -0.0321 |       -1.26 |             0.0566 |      1.28 |               1.089 |         -10.35 | False      |
| 4 stop                | stop atr 1.5            |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  | False      |
| 4 stop                | stop atr 2.0            |           3184 |              -0.0153 |       -1.07 |             0.0276 |      1.07 |               1.083 |          -4.19 | False      |
| 4 stop                | stop structure          |           3273 |              -0.0213 |       -1.02 |             0.053  |      1.56 |               1.107 |          -9.79 | False      |
| 5 take profit         | (actual)                |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  |            |
| 5 take profit         | TP 1.0                  |           4469 |              -0.0334 |       -2.89 |             0.0314 |      1.64 |               1.084 |          -7.41 | False      |
| 5 take profit         | TP 1.5                  |           3990 |              -0.0254 |       -1.84 |             0.0391 |      1.64 |               1.103 |          -7.25 | False      |
| 5 take profit         | TP 2.0                  |           3722 |              -0.0227 |       -1.49 |             0.0434 |      1.62 |               1.102 |          -6.52 | False      |
| 5 take profit         | TP 2.5                  |           3561 |              -0.0178 |       -1.1  |             0.049  |      1.69 |               1.121 |          -5.92 | False      |
| 5 take profit         | TP 3.0                  |           3449 |              -0.0204 |       -1.21 |             0.0458 |      1.53 |               1.113 |          -6.7  | False      |
| 5 take profit         | TP sin                  |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  | False      |
| 6 salida              | (actual)                |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  |            |
| 6 salida              | salida vwap             |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  | False      |
| 6 salida              | salida ema20            |           3247 |              -0.0194 |       -1.02 |             0.0274 |      0.82 |               1.053 |          -8.12 | False      |
| 6 salida              | salida atr_trailing     |           2762 |              -0.0175 |       -0.75 |             0.06   |      1.45 |               1.116 |          -7.84 | False      |
| 6 salida              | salida fixed            |           2902 |              -0.0268 |       -1.24 |             0.0564 |      1.49 |               1.102 |          -6.55 | False      |
| 6 salida              | salida partial_trailing |           2759 |              -0.031  |       -1.54 |             0.0538 |      1.49 |               1.109 |          -7.39 | False      |
| 6 salida              | salida time 30 min      |           5070 |              -0.0633 |       -7.67 |             0.0021 |      0.17 |               1.027 |          -7.23 | False      |
| 6 salida              | salida time 60 min      |           4855 |              -0.0471 |       -4.21 |             0.0342 |      1.94 |               1.113 |          -4.85 | False      |
| 6 salida              | salida time 90 min      |           4398 |              -0.0336 |       -2.48 |             0.0346 |      1.51 |               1.085 |          -7.99 | False      |
| 6 salida              | salida time 120 min     |           3858 |              -0.0361 |       -2.25 |             0.0394 |      1.46 |               1.075 |          -8.95 | False      |
| 6 salida              | salida time 180 min     |           3297 |              -0.0235 |       -1.21 |             0.0451 |      1.36 |               1.088 |          -6.69 | False      |
| 7 ventana horaria     | (actual)                |           3286 |              -0.0161 |       -0.88 |             0.0488 |      1.51 |               1.117 |          -6.4  |            |
| 7 ventana horaria     | solo 09:30-11:30        |           2136 |              -0.0032 |       -0.13 |             0.0608 |      1.39 |               1.144 |          -4.26 | True       |
| 7 ventana horaria     | solo 11:30-13:30        |           1714 |              -0.0043 |       -0.2  |             0.0756 |      1.87 |               1.213 |          -3.43 | True       |
| 7 ventana horaria     | solo 13:30-16:00        |           1690 |              -0.0326 |       -1.57 |             0.0801 |      1.93 |               1.194 |          -5.94 | False      |

Decisiones: modelo: **modelo B**; entrada: **(actual)**; filtros: **(actual)**; stop: **(actual)**; take profit: **(actual)**; salida: **(actual)**; ventana: **solo 11:30-13:30**

Configuración final: modelo B, entrada state, filtros ninguno, stop atr 1.5×ATR, TP None, salida vwap, ventana ['11:30', '13:30'].

### MGC
| etapa                 | opcion                        |   trades_train |   expectancy_R_train |   t_R_train |   expectancy_R_val |   t_R_val |   profit_factor_val |   max_dd_%_val | aceptada   |
|:----------------------|:------------------------------|---------------:|---------------------:|------------:|-------------------:|----------:|--------------------:|---------------:|:-----------|
| 1 modelo              | (actual)                      |           4248 |              -0.1414 |       -7.66 |            -0.0686 |     -2.71 |               0.789 |         -54.29 |            |
| 1 modelo              | modelo B                      |           3907 |              -0.1203 |       -5.57 |            -0.0642 |     -1.88 |               0.822 |         -45.19 | True       |
| 1 modelo              | modelo C                      |           3970 |              -0.1033 |       -4.79 |            -0.0514 |     -1.42 |               0.837 |         -44.63 | True       |
| 1 modelo              | modelo D                      |           3639 |              -0.11   |       -4.67 |            -0.0488 |     -1.21 |               0.863 |         -43.59 | False      |
| 2 entrada             | (actual)                      |           3970 |              -0.1033 |       -4.79 |            -0.0514 |     -1.42 |               0.837 |         -44.63 |            |
| 2 entrada             | entrada breakout              |           3288 |              -0.1082 |       -4.52 |            -0.0491 |     -1.24 |               0.862 |         -35.34 | False      |
| 2 entrada             | entrada pullback              |           2404 |              -0.083  |       -2.72 |            -0.0439 |     -0.8  |               0.887 |         -25.65 | True       |
| 3 filtros (uno a uno) | (actual)                      |           2404 |              -0.083  |       -2.72 |            -0.0439 |     -0.8  |               0.887 |         -25.65 |            |
| 3 filtros (uno a uno) | filtro ema200_slope           |           2345 |              -0.0813 |       -2.64 |            -0.0329 |     -0.6  |               0.917 |         -25.04 | True       |
| 3 filtros (uno a uno) | filtro vwap_slope             |           1736 |              -0.0835 |       -2.23 |             0.0007 |      0.01 |               0.976 |         -19.2  | False      |
| 3b filtros juntos     | (actual)                      |           2345 |              -0.0813 |       -2.64 |            -0.0329 |     -0.6  |               0.917 |         -25.04 |            |
| 3b filtros juntos     | filtros juntos                |           1695 |              -0.0798 |       -2.11 |             0.0085 |      0.12 |               0.988 |         -18.28 | True       |
| 4 stop                | (actual)                      |           1695 |              -0.0798 |       -2.11 |             0.0085 |      0.12 |               0.988 |         -18.28 |            |
| 4 stop                | stop atr 1.0                  |           1785 |              -0.137  |       -2.69 |            -0.0148 |     -0.15 |               0.955 |         -24.46 | False      |
| 4 stop                | stop atr 1.5                  |           1695 |              -0.0798 |       -2.11 |             0.0085 |      0.12 |               0.988 |         -18.28 | False      |
| 4 stop                | stop atr 2.0                  |           1660 |              -0.0633 |       -2.15 |             0.0074 |      0.13 |               1.03  |         -13.8  | False      |
| 4 stop                | stop structure                |           1660 |              -0.0687 |       -1.64 |             0.0145 |      0.19 |               1.018 |         -15.61 | True       |
| 5 take profit         | (actual)                      |           1660 |              -0.0687 |       -1.64 |             0.0145 |      0.19 |               1.018 |         -15.61 |            |
| 5 take profit         | TP 1.0                        |           1917 |              -0.1102 |       -5.86 |            -0.041  |     -1.25 |               0.886 |         -21.73 | False      |
| 5 take profit         | TP 1.5                        |           1808 |              -0.1047 |       -4.67 |            -0.0309 |     -0.79 |               0.92  |         -21    | False      |
| 5 take profit         | TP 2.0                        |           1767 |              -0.0964 |       -3.85 |            -0.0473 |     -1.08 |               0.886 |         -22.88 | False      |
| 5 take profit         | TP 2.5                        |           1722 |              -0.1051 |       -3.9  |            -0.0367 |     -0.77 |               0.915 |         -17.02 | False      |
| 5 take profit         | TP 3.0                        |           1715 |              -0.0929 |       -3.24 |            -0.0558 |     -1.12 |               0.869 |         -21.32 | False      |
| 5 take profit         | TP sin                        |           1660 |              -0.0687 |       -1.64 |             0.0145 |      0.19 |               1.018 |         -15.61 | False      |
| 6 salida              | (actual)                      |           1660 |              -0.0687 |       -1.64 |             0.0145 |      0.19 |               1.018 |         -15.61 |            |
| 6 salida              | salida vwap                   |           1660 |              -0.0687 |       -1.64 |             0.0145 |      0.19 |               1.018 |         -15.61 | False      |
| 6 salida              | salida ema20                  |           1860 |              -0.0696 |       -1.78 |            -0.0182 |     -0.25 |               0.946 |         -22.13 | False      |
| 6 salida              | salida atr_trailing           |           1693 |              -0.057  |       -1.44 |            -0.0139 |     -0.21 |               0.957 |         -20.5  | False      |
| 6 salida              | salida fixed                  |           1557 |              -0.0709 |       -2.25 |            -0.0386 |     -0.68 |               0.921 |         -18.99 | False      |
| 6 salida              | salida partial_trailing       |           1630 |              -0.0831 |       -2.85 |            -0.0373 |     -0.74 |               0.911 |         -16.6  | False      |
| 6 salida              | salida time 30 min            |           2104 |              -0.1442 |       -8.14 |            -0.1296 |     -4.86 |               0.616 |         -37.32 | False      |
| 6 salida              | salida time 60 min            |           2012 |              -0.1199 |       -5.11 |            -0.1173 |     -3.14 |               0.715 |         -36.76 | False      |
| 6 salida              | salida time 90 min            |           1902 |              -0.0967 |       -3.45 |            -0.0995 |     -2.32 |               0.79  |         -30.9  | False      |
| 6 salida              | salida time 120 min           |           1808 |              -0.0808 |       -2.51 |            -0.0672 |     -1.27 |               0.868 |         -25.11 | False      |
| 6 salida              | salida time 180 min           |           1666 |              -0.0721 |       -1.95 |            -0.0091 |     -0.14 |               0.969 |         -14.63 | False      |
| 7 ventana horaria     | (actual)                      |           1660 |              -0.0687 |       -1.64 |             0.0145 |      0.19 |               1.018 |         -15.61 |            |
| 7 ventana horaria     | solo europea 03:00-08:20      |            934 |              -0.0539 |       -0.82 |             0.0858 |      0.66 |               1.137 |         -10.45 | True       |
| 7 ventana horaria     | solo apertura NY 08:20-09:30  |            381 |              -0.2142 |       -3.36 |             0.0258 |      0.17 |               1.012 |          -8.18 | False      |
| 7 ventana horaria     | solo solapamiento 09:30-11:30 |            420 |              -0.0608 |       -0.95 |            -0.057  |     -0.63 |               0.863 |          -8.1  | False      |
| 7 ventana horaria     | solo resto NY 11:30-13:30     |            273 |              -0.2043 |       -4.18 |            -0.1174 |     -1.24 |               0.713 |          -6.84 | False      |

Decisiones: modelo: **modelo C**; entrada: **entrada pullback**; filtros: **filtro ema200_slope**; filtros juntos: **filtros juntos**; stop: **stop structure**; take profit: **(actual)**; salida: **(actual)**; ventana: **solo europea 03:00-08:20**

Configuración final: modelo C, entrada pullback, filtros ['ema200_slope', 'vwap_slope'], stop structure, TP None, salida vwap, ventana ['03:00', '08:20'].

- NQ: referencia; usa la configuración final de su micro (B, state, ...).
- GC: referencia; usa la configuración final de su micro (C, pullback, ...).
## 11. Train / Validation / Test (configuración final de cada instrumento)
### MNQ
|                      |        train |   validation |        test |
|:---------------------|-------------:|-------------:|------------:|
| trades               |    1714      |     552      |    409      |
| win_rate_%           |      32.3    |      34.8    |     35.2    |
| avg_win              |     198.9    |     242.3    |    147.1    |
| avg_loss             |     -97.5    |    -106.5    |    -97.2    |
| avg_rr               |       2.04   |       2.27   |      1.51   |
| expectancy_usd       |      -1.66   |      14.81   |    -11.2    |
| expectancy_R         |      -0.0043 |       0.0756 |     -0.0604 |
| expectancy_R_gross   |       0.0566 |       0.0945 |     -0.0434 |
| t_R                  |      -0.2    |       1.87   |     -1.56   |
| profit_factor        |       0.975  |       1.213  |      0.822  |
| gross_profit         |  110200      |   46513      |  21180      |
| gross_loss           | -113053      |  -38340      | -25760      |
| gross_pnl            |   18493      |   10452      |  -3300      |
| costs                |   21346      |    2279      |   1280      |
| net_pnl              |   -2853      |    8173      |  -4580      |
| max_dd               |  -10480      |   -2055      |  -5334      |
| max_dd_%             |     -20.96   |      -3.43   |    -10.53   |
| sharpe               |      -0.11   |       1.17   |     -0.98   |
| sortino              |      -0.18   |       2.11   |     -1.5    |
| calmar               |      -0.04   |       1.97   |     -0.38   |
| avg_trade            |      -1.66   |      14.81   |    -11.2    |
| median_trade         |     -51.15   |     -45.3    |    -44.7    |
| largest_win          |    1517      |     843      |    864      |
| largest_loss         |    -263      |    -304      |   -251      |
| max_consec_wins      |       6      |       4      |      4      |
| max_consec_losses    |      19      |      11      |      9      |
| avg_duration_min     |     128.3    |     125.8    |    126.2    |
| trades_per_day       |       0.98   |       0.94   |      0.7    |
| return_per_month_usd |     -34      |     282      |   -158      |
| months_positive_%    |      51.8    |      72.4    |     34.5    |
| longs                |    1140      |     303      |    311      |
| shorts               |     574      |     249      |     98      |

![periodos](MNQ_final_vs_modelos.png)

![equity](MNQ_equity_drawdown.png)

![R](MNQ_distribucion_R.png)

![mensual](MNQ_mensual.png)

![MAE/MFE](MNQ_mae_mfe.png)

![hora](MNQ_pnl_hora.png)

![día](MNQ_pnl_dia.png)

**Por año (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|         2015 |      248 |     -2424 |        -0.0393 |         32.3 | -0.73 |
|         2016 |      257 |     -5618 |        -0.1027 |         26.1 | -1.76 |
|         2017 |      248 |      1505 |         0.0358 |         32.3 |  0.55 |
|         2018 |      233 |      3610 |         0.092  |         36.1 |  1.3  |
|         2019 |      251 |     -4277 |        -0.0878 |         29.9 | -2.03 |
|         2020 |      226 |      3602 |         0.0807 |         36.3 |  1.44 |
|         2021 |      244 |      -333 |        -0.0154 |         33.6 | -0.32 |
|         2022 |      220 |      7068 |         0.1657 |         38.2 |  2.47 |
|         2023 |      238 |      2394 |         0.0389 |         31.9 |  0.63 |
|         2024 |      101 |      -209 |         0.0205 |         35.6 |  0.22 |

**Por mes (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|            1 |      211 |      5157 |         0.1166 |         37.4 |  1.78 |
|            2 |      217 |     -1221 |        -0.0103 |         31.8 | -0.18 |
|            3 |      147 |      1522 |         0.0527 |         34   |  0.63 |
|            4 |      223 |      2208 |         0.053  |         37.2 |  0.79 |
|            5 |      220 |     -3118 |        -0.0652 |         29.5 | -1.22 |
|            6 |      126 |      4186 |         0.1713 |         38.9 |  1.75 |
|            7 |      205 |      3133 |         0.0795 |         33.7 |  1.21 |
|            8 |      238 |     -4261 |        -0.0952 |         29.4 | -1.79 |
|            9 |      139 |     -2450 |        -0.089  |         27.3 | -1.35 |
|           10 |      210 |      -726 |        -0.014  |         32.4 | -0.22 |
|           11 |      202 |       707 |         0.03   |         33.2 |  0.47 |
|           12 |      128 |       184 |         0.0068 |         30.5 |  0.09 |

**Por día semana (train+validation):**

| entry_time   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:-------------|---------:|----------:|---------------:|-------------:|------:|
| jue          |      472 |      -843 |        -0.0025 |         31.1 | -0.06 |
| lun          |      425 |      1680 |         0.0109 |         33.2 |  0.26 |
| mar          |      468 |     -5978 |        -0.0634 |         29.9 | -1.59 |
| mié          |      452 |        38 |         0.0114 |         30.5 |  0.25 |
| vie          |      449 |     10422 |         0.1236 |         40.1 |  2.74 |

**Por hora (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|           11 |     1438 |     12719 |         0.0447 |         36.5 |  1.77 |
|           12 |      579 |     -4450 |        -0.0269 |         25.7 | -0.75 |
|           13 |      249 |     -2949 |        -0.0573 |         28.9 | -1.29 |

**Por franja (train+validation):**

| entry_min   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| 11:30-13:30 |     2266 |      5320 |         0.0152 |         32.9 |  0.79 |

**Por dirección (train+validation):**

| direction   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| long        |     1443 |      8773 |         0.0329 |         36.1 |  1.48 |
| short       |      823 |     -3453 |        -0.0159 |         27.3 | -0.45 |

**Por volatilidad (ATR entrada) (train+validation):**

| atr_entry      |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:---------------|---------:|----------:|---------------:|-------------:|------:|
| vol baja       |      567 |     -6547 |        -0.0489 |         31   | -1.24 |
| vol media-baja |      566 |     -2110 |        -0.0123 |         31.6 | -0.34 |
| vol media-alta |      566 |      6381 |         0.0544 |         34.3 |  1.36 |
| vol alta       |      567 |      7596 |         0.0676 |         34.7 |  1.83 |

**Por motivo de salida (train+validation):**

| exit_reason   |   trades |   net_pnl |   expectancy_R |   win_rate_% |     t_R |
|:--------------|---------:|----------:|---------------:|-------------:|--------:|
| fin_de_sesion |      797 |    153060 |         0.9603 |         91   |   30.31 |
| senal_vwap    |     1240 |    -99317 |        -0.3968 |          1.7 |  -60.76 |
| stop          |      229 |    -48423 |        -1.043  |          0   | -499.91 |

**Por año (test):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|         2024 |      139 |       179 |        -0.0031 |         35.3 | -0.04 |
|         2025 |      180 |     -3383 |        -0.1    |         34.4 | -1.85 |
|         2026 |       90 |     -1375 |        -0.0696 |         36.7 | -0.83 |

**Por franja (test):**

| entry_min   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| 11:30-13:30 |      409 |     -4580 |        -0.0604 |         35.2 | -1.56 |

**Por dirección (test):**

| direction   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| long        |      311 |     -1922 |         -0.035 |         37.3 | -0.8  |
| short       |       98 |     -2657 |         -0.141 |         28.6 | -1.68 |

![mejor](MNQ_ejemplo_mejor.png)

![peor](MNQ_ejemplo_peor.png)

![mediana](MNQ_ejemplo_mediana.png)

### MGC
|                      |        train |   validation |        test |
|:---------------------|-------------:|-------------:|------------:|
| trades               |     934      |     291      |    330      |
| win_rate_%           |      21.5    |      23.4    |     17.9    |
| avg_win              |     462.4    |     624.3    |    298.6    |
| avg_loss             |    -142.3    |    -167.5    |   -115      |
| avg_rr               |       3.25   |       3.73   |      2.6    |
| expectancy_usd       |     -12.12   |      17.54   |    -41.04   |
| expectancy_R         |      -0.0539 |       0.0858 |     -0.2253 |
| expectancy_R_gross   |       0.1137 |       0.2007 |     -0.1663 |
| t_R                  |      -0.82   |       0.66   |     -3.14   |
| profit_factor        |       0.891  |       1.137  |      0.565  |
| gross_profit         |   92952      |   42451      |  17615      |
| gross_loss           | -104272      |  -37346      | -31159      |
| gross_pnl            |   20933      |   13629      |  -9844      |
| costs                |   32253      |    8525      |   3700      |
| net_pnl              |  -11320      |    5104      | -13544      |
| max_dd               |  -14203      |   -5984      | -13544      |
| max_dd_%             |     -28.19   |     -10.45   |    -27.09   |
| sharpe               |      -0.27   |       0.42   |     -2.07   |
| sortino              |      -0.73   |       1.28   |     -3.75   |
| calmar               |      -0.13   |       0.41   |     -0.47   |
| avg_trade            |     -12.12   |      17.54   |    -41.04   |
| median_trade         |    -106.8    |    -122.8    |    -87.7    |
| largest_win          |    4974      |    4660      |   1976      |
| largest_loss         |    -339      |    -370      |   -257      |
| max_consec_wins      |       3      |       4      |      3      |
| max_consec_losses    |      24      |      15      |     25      |
| avg_duration_min     |     130.4    |     128.1    |    101.4    |
| trades_per_day       |       0.54   |       0.5    |      0.57   |
| return_per_month_usd |    -132      |     176      |   -484      |
| months_positive_%    |      37.2    |      34.5    |     25      |
| longs                |     506      |     143      |    200      |
| shorts               |     428      |     148      |    130      |

![periodos](MGC_final_vs_modelos.png)

![equity](MGC_equity_drawdown.png)

![R](MGC_distribucion_R.png)

![mensual](MGC_mensual.png)

![MAE/MFE](MGC_mae_mfe.png)

![hora](MGC_pnl_hora.png)

![día](MGC_pnl_dia.png)

**Por año (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|         2015 |      155 |     -3469 |        -0.0909 |         21.3 | -0.59 |
|         2016 |      141 |     -4452 |        -0.1468 |         21.3 | -0.96 |
|         2017 |      135 |      -214 |        -0.001  |         24.4 | -0.01 |
|         2018 |      109 |      3351 |         0.1606 |         22.9 |  0.57 |
|         2019 |      113 |     -5242 |        -0.2164 |         21.2 | -1.71 |
|         2020 |      146 |      3142 |         0.1054 |         22.6 |  0.56 |
|         2021 |      121 |     -3995 |        -0.176  |         18.2 | -1.12 |
|         2022 |      117 |      3578 |         0.1424 |         22.2 |  0.64 |
|         2023 |      136 |      4490 |         0.1379 |         22.1 |  0.71 |
|         2024 |       52 |     -3402 |        -0.249  |         25   | -1.72 |

**Por mes (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|            1 |      107 |     -9585 |        -0.4264 |         14   | -4.73 |
|            2 |       97 |     -2177 |        -0.083  |         19.6 | -0.4  |
|            3 |      122 |      1806 |         0.0697 |         30.3 |  0.46 |
|            4 |      102 |     -2156 |        -0.1159 |         18.6 | -0.7  |
|            5 |      108 |      3961 |         0.1876 |         26.9 |  0.72 |
|            6 |       88 |     -3051 |        -0.1563 |         21.6 | -1.05 |
|            7 |       99 |      -886 |        -0.0451 |         14.1 | -0.19 |
|            8 |       93 |     -1954 |        -0.0979 |         22.6 | -0.63 |
|            9 |      104 |      7846 |         0.3585 |         25   |  1.18 |
|           10 |      110 |      2287 |         0.1023 |         27.3 |  0.47 |
|           11 |      101 |      2897 |         0.1478 |         25.7 |  0.64 |
|           12 |       94 |     -5202 |        -0.2629 |         14.9 | -1.63 |

**Por día semana (train+validation):**

| entry_time   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:-------------|---------:|----------:|---------------:|-------------:|------:|
| jue          |      240 |     -3444 |        -0.0508 |         22.5 | -0.39 |
| lun          |      225 |     -6080 |        -0.114  |         20.9 | -1.13 |
| mar          |      256 |     17576 |         0.3183 |         27   |  1.8  |
| mié          |      235 |     -3650 |        -0.072  |         20.9 | -0.59 |
| vie          |      269 |    -10618 |        -0.1935 |         18.6 | -1.85 |

**Por hora (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|            4 |      394 |     -8787 |        -0.0866 |         21.3 | -1.25 |
|            5 |      306 |     11707 |         0.179  |         25.5 |  1.15 |
|            6 |      195 |     -1753 |        -0.0637 |         20   | -0.44 |
|            7 |      208 |     -3240 |        -0.0634 |         22.1 | -0.45 |
|            8 |      122 |     -4143 |        -0.1669 |         18   | -0.9  |

**Por franja (train+validation):**

| entry_min           |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:--------------------|---------:|----------:|---------------:|-------------:|------:|
| europea 03:00-08:20 |     1225 |     -6216 |        -0.0207 |           22 | -0.35 |

**Por dirección (train+validation):**

| direction   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| long        |      649 |      2953 |         0.0211 |         22.3 |  0.26 |
| short       |      576 |     -9169 |        -0.0677 |         21.5 | -0.79 |

**Por volatilidad (ATR entrada) (train+validation):**

| atr_entry      |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:---------------|---------:|----------:|---------------:|-------------:|------:|
| vol baja       |      307 |      7082 |         0.1198 |         23.8 |  0.84 |
| vol media-baja |      306 |    -14464 |        -0.2089 |         19   | -1.97 |
| vol media-alta |      306 |      1174 |         0.0204 |         21.9 |  0.17 |
| vol alta       |      306 |        -7 |        -0.0144 |         23.2 | -0.15 |

**Por motivo de salida (train+validation):**

| exit_reason   |   trades |   net_pnl |   expectancy_R |   win_rate_% |     t_R |
|:--------------|---------:|----------:|---------------:|-------------:|--------:|
| fin_de_sesion |       97 |    106033 |         5.1295 |        100   |   11.52 |
| senal_vwap    |      875 |    -48745 |        -0.2638 |         19.7 |  -11.22 |
| stop          |      253 |    -63504 |        -1.1543 |          0   | -217.99 |

**Por año (test):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|         2024 |       74 |     -4044 |        -0.2613 |         13.5 | -1.56 |
|         2025 |      164 |     -5982 |        -0.1936 |         18.3 | -1.83 |
|         2026 |       92 |     -3518 |        -0.2527 |         20.7 | -2.21 |

**Por franja (test):**

| entry_min           |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:--------------------|---------:|----------:|---------------:|-------------:|------:|
| europea 03:00-08:20 |      330 |    -13544 |        -0.2253 |         17.9 | -3.14 |

**Por dirección (test):**

| direction   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| long        |      200 |     -5869 |        -0.1448 |         19   | -1.45 |
| short       |      130 |     -7675 |        -0.3491 |         16.2 | -3.59 |

![mejor](MGC_ejemplo_mejor.png)

![peor](MGC_ejemplo_peor.png)

![mediana](MGC_ejemplo_mediana.png)

### NQ
|                      |        train |   validation |         test |
|:---------------------|-------------:|-------------:|-------------:|
| trades               |    1737      |     575      |     586      |
| win_rate_%           |      32.8    |      35      |      34.5    |
| avg_win              |     712.2    |    1852.4    |    1980      |
| avg_loss             |    -317.2    |    -757.4    |   -1108.1    |
| avg_rr               |       2.24   |       2.45   |       1.79   |
| expectancy_usd       |      20.34   |     154.88   |     -43.63   |
| expectancy_R         |       0.0204 |       0.0821 |      -0.0285 |
| expectancy_R_gross   |       0.0539 |       0.0923 |      -0.0207 |
| t_R                  |       0.95   |       2.09   |      -0.85   |
| profit_factor        |       1.096  |       1.314  |       0.94   |
| gross_profit         |  405220      |  372335      |  399960      |
| gross_loss           | -369889      | -283277      | -425527      |
| gross_pnl            |   61386      |   97683      |  -16777      |
| costs                |   26055      |    8625      |    8790      |
| net_pnl              |   35331      |   89058      |  -25567      |
| max_dd               |  -18663      |  -11365      |  -37229      |
| max_dd_%             |      -3.51   |      -2      |      -7.28   |
| sharpe               |       0.45   |       1.61   |      -0.3    |
| sortino              |       0.78   |       3.13   |      -0.51   |
| calmar               |       0.28   |       3.67   |      -0.31   |
| avg_trade            |      20.34   |     154.88   |     -43.63   |
| median_trade         |    -100      |    -350      |    -475      |
| largest_win          |    6460      |    7185      |   19135      |
| largest_loss         |   -4000      |   -2922      |   -6860      |
| max_consec_wins      |       6      |       4      |       4      |
| max_consec_losses    |      19      |      11      |      10      |
| avg_duration_min     |     127.8    |     125.5    |     126.5    |
| trades_per_day       |       0.99   |       0.98   |       1      |
| return_per_month_usd |     416      |    3071      |    -882      |
| months_positive_%    |      52.9    |      72.4    |      34.5    |
| longs                |    1140      |     303      |     362      |
| shorts               |     597      |     272      |     224      |

![periodos](NQ_final_vs_modelos.png)

![equity](NQ_equity_drawdown.png)

![R](NQ_distribucion_R.png)

![mensual](NQ_mensual.png)

![MAE/MFE](NQ_mae_mfe.png)

![hora](NQ_pnl_hora.png)

![día](NQ_pnl_dia.png)

**Por año (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|         2015 |      248 |      2304 |        -0.0025 |         32.7 | -0.05 |
|         2016 |      257 |     -5624 |        -0.0624 |         27.2 | -1.07 |
|         2017 |      248 |      3347 |         0.0819 |         33.9 |  1.27 |
|         2018 |      234 |     19433 |         0.1095 |         35.9 |  1.55 |
|         2019 |      251 |    -10817 |        -0.0657 |         29.9 | -1.52 |
|         2020 |      241 |     15022 |         0.0744 |         35.3 |  1.39 |
|         2021 |      250 |      1397 |        -0.0045 |         34.4 | -0.09 |
|         2022 |      244 |     80596 |         0.158  |         36.9 |  2.53 |
|         2023 |      238 |     10190 |         0.0482 |         32.8 |  0.78 |
|         2024 |      101 |      8542 |         0.03   |         36.6 |  0.32 |

**Por mes (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|            1 |      217 |     35814 |         0.1415 |         37.3 |  2.2  |
|            2 |      221 |      7032 |         0.0023 |         31.7 |  0.04 |
|            3 |      160 |      6124 |         0.0477 |         33.1 |  0.61 |
|            4 |      226 |     30061 |         0.0784 |         38.1 |  1.19 |
|            5 |      233 |     -4931 |        -0.0397 |         30.5 | -0.77 |
|            6 |      126 |     10665 |         0.1944 |         39.7 |  1.98 |
|            7 |      205 |     17316 |         0.1031 |         35.1 |  1.57 |
|            8 |      238 |     -1059 |        -0.0718 |         29.4 | -1.35 |
|            9 |      144 |     -1207 |        -0.0696 |         27.1 | -1.08 |
|           10 |      210 |     11319 |         0.0078 |         32.9 |  0.12 |
|           11 |      202 |     11336 |         0.0542 |         34.2 |  0.84 |
|           12 |      130 |      1919 |         0.0325 |         30.8 |  0.43 |

**Por día semana (train+validation):**

| entry_time   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:-------------|---------:|----------:|---------------:|-------------:|------:|
| jue          |      483 |     31571 |         0.0228 |         31.7 |  0.57 |
| lun          |      432 |     15714 |         0.0321 |         33.3 |  0.78 |
| mar          |      481 |    -30608 |        -0.0502 |         29.9 | -1.29 |
| mié          |      458 |     21205 |         0.0346 |         31   |  0.76 |
| vie          |      458 |     86507 |         0.1442 |         40.8 |  3.24 |

**Por hora (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|           11 |     1477 |     99520 |         0.0643 |         37   |  2.59 |
|           12 |      590 |     29573 |         0.0033 |         26.6 |  0.09 |
|           13 |      245 |     -4704 |        -0.0581 |         26.9 | -1.33 |

**Por franja (train+validation):**

| entry_min   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| 11:30-13:30 |     2312 |    124389 |         0.0357 |         33.3 |  1.89 |

**Por dirección (train+validation):**

| direction   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| long        |     1443 |    104486 |         0.0592 |         36.9 |  2.66 |
| short       |      869 |     19904 |        -0.0032 |         27.4 | -0.09 |

**Por volatilidad (ATR entrada) (train+validation):**

| atr_entry      |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:---------------|---------:|----------:|---------------:|-------------:|------:|
| vol baja       |      578 |      -990 |        -0.0046 |         32.2 | -0.12 |
| vol media-baja |      578 |      7953 |         0.0226 |         32.4 |  0.62 |
| vol media-alta |      578 |     35165 |         0.0555 |         34.9 |  1.42 |
| vol alta       |      578 |     82262 |         0.0694 |         33.7 |  1.9  |

**Por motivo de salida (train+validation):**

| exit_reason   |   trades |   net_pnl |   expectancy_R |   win_rate_% |      t_R |
|:--------------|---------:|----------:|---------------:|-------------:|---------:|
| fin_de_sesion |      806 |    763390 |         0.9855 |         91.7 |    31.45 |
| senal_vwap    |     1275 |   -439640 |        -0.3735 |          2.4 |   -58.34 |
| stop          |      231 |   -199361 |        -1.0194 |          0   | -1077.83 |

**Por año (test):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|         2024 |      148 |      6868 |         0.0131 |         35.8 |  0.18 |
|         2025 |      258 |     -5783 |        -0.0392 |         33.7 | -0.79 |
|         2026 |      180 |    -26652 |        -0.0474 |         34.4 | -0.81 |

**Por franja (test):**

| entry_min   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| 11:30-13:30 |      586 |    -25567 |        -0.0285 |         34.5 | -0.85 |

**Por dirección (test):**

| direction   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| long        |      362 |     -3815 |        -0.0155 |         37.8 | -0.39 |
| short       |      224 |    -21752 |        -0.0496 |         29   | -0.84 |

### GC
|                      |        train |   validation |         test |
|:---------------------|-------------:|-------------:|-------------:|
| trades               |     935      |     291      |     355      |
| win_rate_%           |      22.1    |      23.4    |      19.4    |
| avg_win              |     553.4    |     929.9    |    1587.5    |
| avg_loss             |    -185.2    |    -225.8    |    -544.2    |
| avg_rr               |       2.99   |       4.12   |       2.92   |
| expectancy_usd       |     -21.71   |      44.24   |    -129.87   |
| expectancy_R         |      -0.0006 |       0.1231 |      -0.1608 |
| expectancy_R_gross   |       0.1125 |       0.2007 |      -0.1239 |
| t_R                  |      -0.01   |       0.95   |      -2.32   |
| profit_factor        |       0.849  |       1.256  |       0.704  |
| gross_profit         |  114555      |   63230      |  109535      |
| gross_loss           | -134850      |  -50355      | -155640      |
| gross_pnl            |    3080      |   20150      |  -37230      |
| costs                |   23375      |    7275      |    8875      |
| net_pnl              |  -20295      |   12875      |  -46105      |
| max_dd               |  -20860      |   -6145      |  -57110      |
| max_dd_%             |      -4.17   |      -1.19   |     -11.42   |
| sharpe               |      -0.54   |       0.69   |      -1.13   |
| sortino              |      -1.11   |       1.94   |      -2.34   |
| calmar               |      -0.14   |       0.94   |      -0.36   |
| avg_trade            |     -21.71   |      44.24   |    -129.87   |
| median_trade         |    -125      |    -155      |    -335      |
| largest_win          |    3285      |    4555      |   12445      |
| largest_loss         |   -1065      |   -1075      |   -2055      |
| max_consec_wins      |       3      |       4      |       4      |
| max_consec_losses    |      24      |      15      |      25      |
| avg_duration_min     |     130.4    |     128.1    |     111.5    |
| trades_per_day       |       0.54   |       0.5    |       0.61   |
| return_per_month_usd |    -236      |     444      |   -1647      |
| months_positive_%    |      41.9    |      44.8    |      25      |
| longs                |     506      |     143      |     209      |
| shorts               |     429      |     148      |     146      |

![periodos](GC_final_vs_modelos.png)

![equity](GC_equity_drawdown.png)

![R](GC_distribucion_R.png)

![mensual](GC_mensual.png)

![MAE/MFE](GC_mae_mfe.png)

![hora](GC_pnl_hora.png)

![día](GC_pnl_dia.png)

**Por año (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|         2015 |      155 |     -3725 |        -0.0324 |         22.6 | -0.21 |
|         2016 |      141 |     -6195 |        -0.0914 |         22.7 | -0.6  |
|         2017 |      135 |      -625 |         0.0707 |         25.2 |  0.43 |
|         2018 |      109 |       245 |         0.2216 |         22.9 |  0.79 |
|         2019 |      113 |     -2405 |        -0.1539 |         22.1 | -1.22 |
|         2020 |      147 |       995 |         0.1307 |         22.4 |  0.69 |
|         2021 |      121 |     -7655 |        -0.134  |         18.2 | -0.85 |
|         2022 |      117 |      9555 |         0.1745 |         22.2 |  0.79 |
|         2023 |      136 |      6740 |         0.1819 |         22.1 |  0.93 |
|         2024 |       52 |     -4350 |        -0.2171 |         25   | -1.51 |

**Por mes (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|            1 |      107 |    -13335 |        -0.3769 |         14   | -4.19 |
|            2 |       97 |     -2975 |        -0.033  |         21.6 | -0.16 |
|            3 |      123 |     10455 |         0.1068 |         30.9 |  0.72 |
|            4 |      102 |     -5890 |        -0.0748 |         18.6 | -0.45 |
|            5 |      108 |       860 |         0.2367 |         26.9 |  0.91 |
|            6 |       88 |     -6400 |        -0.108  |         21.6 | -0.72 |
|            7 |       99 |        45 |         0.0017 |         14.1 |  0.01 |
|            8 |       93 |     -5715 |        -0.0459 |         23.7 | -0.29 |
|            9 |      104 |      3740 |         0.4144 |         26   |  1.36 |
|           10 |      110 |      5120 |         0.1512 |         28.2 |  0.69 |
|           11 |      101 |     10705 |         0.2027 |         25.7 |  0.87 |
|           12 |       94 |     -4030 |        -0.201  |         14.9 | -1.24 |

**Por día semana (train+validation):**

| entry_time   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:-------------|---------:|----------:|---------------:|-------------:|------:|
| jue          |      240 |     -2870 |        -0.0003 |         22.5 | -0    |
| lun          |      225 |     -2635 |        -0.0632 |         21.3 | -0.62 |
| mar          |      256 |     17360 |         0.3648 |         27   |  2.06 |
| mié          |      236 |     -5080 |        -0.0249 |         21.2 | -0.2  |
| vie          |      269 |    -14195 |        -0.1411 |         20.1 | -1.35 |

**Por hora (train+validation):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|            4 |      395 |     -7705 |        -0.0469 |         22   | -0.68 |
|            5 |      306 |     13820 |         0.2338 |         25.8 |  1.5  |
|            6 |      195 |     -2015 |        -0.0067 |         20.5 | -0.05 |
|            7 |      208 |     -2970 |        -0.0066 |         22.6 | -0.05 |
|            8 |      122 |     -8550 |        -0.1237 |         18   | -0.67 |

**Por franja (train+validation):**

| entry_min           |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:--------------------|---------:|----------:|---------------:|-------------:|------:|
| europea 03:00-08:20 |     1226 |     -7420 |         0.0288 |         22.4 |  0.49 |

**Por dirección (train+validation):**

| direction   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| long        |      649 |      4945 |         0.0703 |         22.8 |  0.86 |
| short       |      577 |    -12365 |        -0.018  |         22   | -0.21 |

**Por volatilidad (ATR entrada) (train+validation):**

| atr_entry      |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:---------------|---------:|----------:|---------------:|-------------:|------:|
| vol baja       |      307 |      5455 |         0.1931 |         24.4 |  1.35 |
| vol media-baja |      306 |    -11390 |        -0.1513 |         19.9 | -1.43 |
| vol media-alta |      306 |      3170 |         0.0629 |         22.2 |  0.51 |
| vol alta       |      307 |     -4655 |         0.0098 |         23.1 |  0.1  |

**Por motivo de salida (train+validation):**

| exit_reason   |   trades |   net_pnl |   expectancy_R |   win_rate_% |     t_R |
|:--------------|---------:|----------:|---------------:|-------------:|--------:|
| fin_de_sesion |       97 |    132005 |         5.1748 |        100   |   11.56 |
| senal_vwap    |      876 |    -76280 |        -0.2192 |         20.3 |   -9.31 |
| stop          |      253 |    -63145 |        -1.0857 |          0   | -369.07 |

**Por año (test):**

|   entry_time |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|-------------:|---------:|----------:|---------------:|-------------:|------:|
|         2024 |       74 |     -8900 |        -0.2323 |         14.9 | -1.38 |
|         2025 |      169 |    -28795 |        -0.1608 |         18.9 | -1.57 |
|         2026 |      112 |     -8410 |        -0.1137 |         23.2 | -1.02 |

**Por franja (test):**

| entry_min           |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:--------------------|---------:|----------:|---------------:|-------------:|------:|
| europea 03:00-08:20 |      355 |    -46105 |        -0.1608 |         19.4 | -2.32 |

**Por dirección (test):**

| direction   |   trades |   net_pnl |   expectancy_R |   win_rate_% |   t_R |
|:------------|---------:|----------:|---------------:|-------------:|------:|
| long        |      209 |    -25765 |        -0.1322 |         19.1 | -1.42 |
| short       |      146 |    -20340 |        -0.2017 |         19.9 | -1.95 |

## 12. Walk-forward (3 años → 1, stop×TP re-optimizado con elección suavizada; dentro de train+validation)
### MNQ
|   año_test | entreno                |   atr_multiplier | take_profit_R   |   R_entreno_suavizado |   trades |   expectancy_R |   t_R |   profit_factor |   net_pnl |
|-----------:|:-----------------------|-----------------:|:----------------|----------------------:|---------:|---------------:|------:|----------------:|----------:|
|       2018 | 2015-01-01..2017-12-31 |              2   | 3.0             |               -0.0354 |      233 |         0.0706 |  1.39 |           1.278 |      3313 |
|       2019 | 2016-01-01..2018-12-31 |              1.5 | sin             |                0.0009 |      251 |        -0.0878 | -2.03 |           0.75  |     -4197 |
|       2020 | 2017-01-01..2019-12-31 |              2   | sin             |                0.0061 |      215 |         0.0444 |  1    |           1.169 |      1665 |
|       2021 | 2018-01-01..2020-12-31 |              2   | sin             |                0.0185 |      229 |        -0.0242 | -0.62 |           0.918 |      -832 |
|       2022 | 2019-01-01..2021-12-31 |              2   | 2.5             |               -0.0138 |      159 |         0.1341 |  2.19 |           1.628 |      5143 |
|       2023 | 2020-01-01..2022-12-31 |              1   | sin             |                0.077  |      249 |         0.0518 |  0.61 |           1.117 |      3132 |
|       2024 | 2021-01-01..2023-12-31 |              1   | sin             |                0.0695 |      106 |         0.0066 |  0.05 |           1.03  |       335 |

Total fuera de muestra del walk-forward: 1442 operaciones, 0.0231 R, t 0.98, neto 8,559 $.

![wf](MNQ_walk_forward.png)

### MGC
|   año_test | entreno                |   atr_multiplier | take_profit_R   |   R_entreno_suavizado |   trades |   expectancy_R |   t_R |   profit_factor |   net_pnl |
|-----------:|:-----------------------|-----------------:|:----------------|----------------------:|---------:|---------------:|------:|----------------:|----------:|
|       2018 | 2015-01-01..2017-12-31 |                2 | 2.0             |               -0.0716 |      112 |        -0.0492 | -0.51 |           0.882 |     -1319 |
|       2019 | 2016-01-01..2018-12-31 |                2 | 2.0             |               -0.0657 |      112 |        -0.1242 | -1.42 |           0.722 |     -3040 |
|       2020 | 2017-01-01..2019-12-31 |                2 | sin             |               -0.0722 |      145 |        -0.0025 | -0.02 |           0.99  |      -113 |
|       2021 | 2018-01-01..2020-12-31 |                2 | sin             |               -0.0424 |      121 |        -0.1517 | -1.52 |           0.614 |     -3963 |
|       2022 | 2019-01-01..2021-12-31 |                2 | 1.0             |               -0.0659 |      124 |         0.0311 |  0.46 |           1.083 |       745 |
|       2023 | 2020-01-01..2022-12-31 |                2 | sin             |               -0.0358 |      135 |         0.0232 |  0.19 |           1.032 |       374 |
|       2024 | 2021-01-01..2023-12-31 |                1 | sin             |               -0.0146 |       53 |        -0.1648 | -0.63 |           0.737 |     -2136 |

Total fuera de muestra del walk-forward: 802 operaciones, -0.0497 R, t -1.21, neto -9,454 $.

![wf](MGC_walk_forward.png)

## 13. Monte Carlo (configuración final; solo robustez, no cambia la estrategia)
Barajado del orden (drawdown y rachas) y remuestreo con reemplazo (retorno), 2000 simulaciones. Supone operaciones independientes: los periodos malos reales pueden ser peores.

|                      |   n_sim |   trades |   retorno_usd_p5 |   retorno_usd_p50 |   retorno_usd_p95 |   prob_retorno_negativo_% |   max_dd_%_p50 |   max_dd_%_p95_peor |   racha_perdedora_p50 |   racha_perdedora_p95 |   prob_dd_mayor_5% |   prob_dd_mayor_10% |   prob_dd_mayor_20% |   prob_dd_mayor_30% |
|:---------------------|--------:|---------:|-----------------:|------------------:|------------------:|--------------------------:|---------------:|--------------------:|----------------------:|----------------------:|-------------------:|--------------------:|--------------------:|--------------------:|
| MNQ train+validation |    2000 |     2266 |         -8333.96 |           5744.51 |          19762.6  |                      25   |         -13.81 |              -21.35 |                    17 |                    23 |              100   |                91.8 |                 8.6 |                 0.2 |
| MNQ test             |    2000 |      409 |         -9504.68 |          -4603.23 |            262.82 |                      93.8 |         -11.54 |              -14.76 |                    12 |                    17 |              100   |                88.3 |                 0   |                 0   |
| MGC train+validation |    2000 |     1225 |        -30715.3  |          -7353.55 |          20087.5  |                      67.5 |         -33.55 |              -48.74 |                    24 |                    34 |              100   |               100   |                99.7 |                70.2 |
| MGC test             |    2000 |      330 |        -20242.5  |         -13631.1  |          -6393.74 |                      99.8 |         -28.5  |              -32.24 |                    22 |                    34 |              100   |               100   |               100   |                24.8 |
| NQ train+validation  |    2000 |     2312 |         43009.7  |         125958    |         205418    |                       0.5 |          -4.54 |               -7.21 |                    17 |                    23 |               35.6 |                 0.4 |                 0   |                 0   |
| NQ test              |    2000 |      586 |       -108356    |         -26641.5  |          61459.9  |                      68.2 |         -12.47 |              -17.59 |                    13 |                    19 |              100   |                84.3 |                 1.2 |                 0   |
| GC train+validation  |    2000 |     1226 |        -38210    |          -8910    |          24021    |                      67.2 |          -4.59 |               -6.67 |                    23 |                    33 |               35   |                 0   |                 0   |                 0   |
| GC test              |    2000 |      355 |        -88956.5  |         -46450    |          -2304    |                      95.9 |         -11    |              -13.86 |                    21 |                    31 |              100   |                76.8 |                 0   |                 0   |

## 14. Sensibilidad (train)
### MNQ (EMA con modelo C)
![ema](MNQ_sens_ema.png)

![atr](MNQ_sens_atr.png)

Rango de expectativa en la rejilla EMA: -0.0159 a -0.0003 R; rejilla ATR: -0.0139 a -0.0041 R.

### MGC (EMA con modelo C)
![ema](MGC_sens_ema.png)

![atr](MGC_sens_atr.png)

Rango de expectativa en la rejilla EMA: -0.0548 a -0.0212 R; rejilla ATR: -0.1843 a -0.0650 R.

## 15. Drawdown
| instrumento   | periodo    |   max_dd |   max_dd_% |   max_consec_losses |   calmar |
|:--------------|:-----------|---------:|-----------:|--------------------:|---------:|
| MNQ           | train      |   -10480 |     -20.96 |                  19 |    -0.04 |
| MNQ           | validation |    -2055 |      -3.43 |                  11 |     1.97 |
| MNQ           | test       |    -5334 |     -10.53 |                   9 |    -0.38 |
| MGC           | train      |   -14203 |     -28.19 |                  24 |    -0.13 |
| MGC           | validation |    -5984 |     -10.45 |                  15 |     0.41 |
| MGC           | test       |   -13544 |     -27.09 |                  25 |    -0.47 |
| NQ            | train      |   -18663 |      -3.51 |                  19 |     0.28 |
| NQ            | validation |   -11365 |      -2    |                  11 |     3.67 |
| NQ            | test       |   -37229 |      -7.28 |                  10 |    -0.31 |
| GC            | train      |   -20860 |      -4.17 |                  24 |    -0.14 |
| GC            | validation |    -6145 |      -1.19 |                  15 |     0.94 |
| GC            | test       |   -57110 |     -11.42 |                  25 |    -0.36 |

## 16. Riesgo por operación y costes dobles (configuración final)
### MNQ
|   risk_% | periodo    |   trades |   net_pnl |   max_dd |   max_dd_% |   sharpe |   calmar |
|---------:|:-----------|---------:|----------:|---------:|-----------:|---------:|---------:|
|     0.25 | train      |     1534 |     -2315 |    -5565 |     -11.13 |    -0.23 |    -0.06 |
|     0.25 | validation |      247 |      2906 |     -772 |      -1.5  |     1.05 |     1.64 |
|     0.25 | test       |      100 |      -435 |    -1100 |      -2.2  |    -0.31 |    -0.17 |
|     0.5  | train      |     1714 |     -2853 |   -10480 |     -20.96 |    -0.11 |    -0.04 |
|     0.5  | validation |      552 |      8173 |    -2055 |      -3.43 |     1.17 |     1.97 |
|     0.5  | test       |      409 |     -4580 |    -5334 |     -10.53 |    -0.98 |    -0.38 |
|     0.75 | train      |     1729 |     -7374 |   -14991 |     -29.98 |    -0.19 |    -0.08 |
|     0.75 | validation |      572 |     11308 |    -4993 |      -7.65 |     1.01 |     1.2  |
|     0.75 | test       |      539 |     -5793 |    -6781 |     -13.3  |    -0.7  |    -0.39 |
|     1    | train      |     1735 |     -8465 |   -19136 |     -38.27 |    -0.14 |    -0.07 |
|     1    | validation |      575 |     20673 |    -6612 |      -8.86 |     1.18 |     1.81 |
|     1    | test       |      572 |     -7699 |    -9101 |     -17.71 |    -0.67 |    -0.39 |

Con deslizamiento ×2: train: R -0.0298 (PF 0.896); validation: R 0.0678 (PF 1.184); test: R -0.0709 (PF 0.779)

### MGC
|   risk_% | periodo    |   trades |   net_pnl |   max_dd |   max_dd_% |   sharpe |   calmar |
|---------:|:-----------|---------:|----------:|---------:|-----------:|---------:|---------:|
|     0.25 | train      |      923 |     -5116 |    -6573 |     -13.09 |    -0.26 |    -0.12 |
|     0.25 | validation |      285 |      2477 |    -2643 |      -4.97 |     0.4  |     0.43 |
|     0.25 | test       |      270 |     -6828 |    -6828 |     -13.66 |    -2.14 |    -0.45 |
|     0.5  | train      |      934 |    -11320 |   -14203 |     -28.19 |    -0.27 |    -0.13 |
|     0.5  | validation |      291 |      5104 |    -5984 |     -10.45 |     0.42 |     0.41 |
|     0.5  | test       |      330 |    -13544 |   -13544 |     -27.09 |    -2.07 |    -0.47 |
|     0.75 | train      |      935 |    -17403 |   -20378 |     -40.31 |    -0.28 |    -0.15 |
|     0.75 | validation |      291 |      7350 |    -9558 |     -15.6  |     0.42 |     0.39 |
|     0.75 | test       |      344 |    -16964 |   -16964 |     -33.93 |    -1.64 |    -0.49 |
|     1    | train      |      934 |    -23074 |   -26289 |     -51.71 |    -0.29 |    -0.17 |
|     1    | validation |      291 |      9879 |   -13202 |     -20.25 |     0.44 |     0.4  |
|     1    | test       |      347 |    -22175 |   -22175 |     -44.35 |    -1.74 |    -0.51 |

Con deslizamiento ×2: train: R -0.1393 (PF 0.759); validation: R 0.0228 (PF 1.025); test: R -0.2518 (PF 0.537)

### NQ
|   risk_% | periodo    |   trades |   net_pnl |   max_dd |   max_dd_% |   sharpe |   calmar |
|---------:|:-----------|---------:|----------:|---------:|-----------:|---------:|---------:|
|     0.25 | train      |     1737 |     35331 |   -18663 |      -3.51 |     0.45 |     0.28 |
|     0.25 | validation |      575 |     89058 |   -11365 |      -2    |     1.61 |     3.67 |
|     0.25 | test       |      586 |    -25567 |   -37229 |      -7.28 |    -0.3  |    -0.31 |
|     0.5  | train      |     1737 |     35331 |   -18663 |      -3.51 |     0.45 |     0.28 |
|     0.5  | validation |      575 |     89058 |   -11365 |      -2    |     1.61 |     3.67 |
|     0.5  | test       |      586 |    -25567 |   -37229 |      -7.28 |    -0.3  |    -0.31 |
|     0.75 | train      |     1737 |     35331 |   -18663 |      -3.51 |     0.45 |     0.28 |
|     0.75 | validation |      575 |     89058 |   -11365 |      -2    |     1.61 |     3.67 |
|     0.75 | test       |      586 |    -25567 |   -37229 |      -7.28 |    -0.3  |    -0.31 |
|     1    | train      |     1737 |     35331 |   -18663 |      -3.51 |     0.45 |     0.28 |
|     1    | validation |      575 |     89058 |   -11365 |      -2    |     1.61 |     3.67 |
|     1    | test       |      586 |    -25567 |   -37229 |      -7.28 |    -0.3  |    -0.31 |

Con deslizamiento ×2: train: R -0.0017 (PF 1.048); validation: R 0.0745 (PF 1.287); test: R -0.0335 (PF 0.927)

### GC
|   risk_% | periodo    |   trades |   net_pnl |   max_dd |   max_dd_% |   sharpe |   calmar |
|---------:|:-----------|---------:|----------:|---------:|-----------:|---------:|---------:|
|     0.25 | train      |      935 |    -20295 |   -20860 |      -4.17 |    -0.54 |    -0.14 |
|     0.25 | validation |      291 |     12875 |    -6145 |      -1.19 |     0.69 |     0.94 |
|     0.25 | test       |      355 |    -46105 |   -57110 |     -11.42 |    -1.13 |    -0.36 |
|     0.5  | train      |      935 |    -20295 |   -20860 |      -4.17 |    -0.54 |    -0.14 |
|     0.5  | validation |      291 |     12875 |    -6145 |      -1.19 |     0.69 |     0.94 |
|     0.5  | test       |      355 |    -46105 |   -57110 |     -11.42 |    -1.13 |    -0.36 |
|     0.75 | train      |      935 |    -20295 |   -20860 |      -4.17 |    -0.54 |    -0.14 |
|     0.75 | validation |      291 |     12875 |    -6145 |      -1.19 |     0.69 |     0.94 |
|     0.75 | test       |      355 |    -46105 |   -57110 |     -11.42 |    -1.13 |    -0.36 |
|     1    | train      |      935 |    -20295 |   -20860 |      -4.17 |    -0.54 |    -0.14 |
|     1    | validation |      291 |     12875 |    -6145 |      -1.19 |     0.69 |     0.94 |
|     1    | test       |      355 |    -46105 |   -57110 |     -11.42 |    -1.13 |    -0.36 |

Con deslizamiento ×2: train: R -0.0898 (PF 0.739); validation: R 0.0586 (PF 1.129); test: R -0.1873 (PF 0.67)

## Lista de robustez (apartado 21) — configuración final
### MNQ
| criterio                                                                  | cumple   | valor             |
|:--------------------------------------------------------------------------|:---------|:------------------|
| expectativa neta > 0 en train                                             | False    | -0.0043           |
| expectativa neta > 0 en validation                                        | True     | 0.0756            |
| expectativa neta > 0 en test                                              | False    | -0.0604           |
| t >= 2 fuera de muestra (validation + test)                               | False    | 0.62              |
| años positivos (train+validation) >= 60 %                                 | False    | 50 %              |
| no depende de un solo día (mejor día < 10 % del neto de train+validation) | False    | 1517.0            |
| más de una franja con R > 0 (train+validation)                            | False    | 1                 |
| se mantiene con costes dobles (test)                                      | False    | -0.0709           |
| degradación validation -> test < 50 % de la expectativa                   | False    | 0.0756 -> -0.0604 |

### MGC
| criterio                                                                  | cumple   | valor             |
|:--------------------------------------------------------------------------|:---------|:------------------|
| expectativa neta > 0 en train                                             | False    | -0.0539           |
| expectativa neta > 0 en validation                                        | True     | 0.0858            |
| expectativa neta > 0 en test                                              | False    | -0.2253           |
| t >= 2 fuera de muestra (validation + test)                               | False    | -1.11             |
| años positivos (train+validation) >= 60 %                                 | False    | 40 %              |
| no depende de un solo día (mejor día < 10 % del neto de train+validation) | False    | 4974.0            |
| más de una franja con R > 0 (train+validation)                            | False    | 0                 |
| se mantiene con costes dobles (test)                                      | False    | -0.2518           |
| degradación validation -> test < 50 % de la expectativa                   | False    | 0.0858 -> -0.2253 |

### NQ
| criterio                                                                  | cumple   | valor             |
|:--------------------------------------------------------------------------|:---------|:------------------|
| expectativa neta > 0 en train                                             | True     | 0.0204            |
| expectativa neta > 0 en validation                                        | True     | 0.0821            |
| expectativa neta > 0 en test                                              | False    | -0.0285           |
| t >= 2 fuera de muestra (validation + test)                               | False    | 1.02              |
| años positivos (train+validation) >= 60 %                                 | True     | 80 %              |
| no depende de un solo día (mejor día < 10 % del neto de train+validation) | True     | 7185.0            |
| más de una franja con R > 0 (train+validation)                            | False    | 1                 |
| se mantiene con costes dobles (test)                                      | False    | -0.0335           |
| degradación validation -> test < 50 % de la expectativa                   | False    | 0.0821 -> -0.0285 |

### GC
| criterio                                                                  | cumple   | valor             |
|:--------------------------------------------------------------------------|:---------|:------------------|
| expectativa neta > 0 en train                                             | False    | -0.0006           |
| expectativa neta > 0 en validation                                        | True     | 0.1231            |
| expectativa neta > 0 en test                                              | False    | -0.1608           |
| t >= 2 fuera de muestra (validation + test)                               | False    | -0.47             |
| años positivos (train+validation) >= 60 %                                 | False    | 40 %              |
| no depende de un solo día (mejor día < 10 % del neto de train+validation) | False    | 4555.0            |
| más de una franja con R > 0 (train+validation)                            | False    | 1                 |
| se mantiene con costes dobles (test)                                      | False    | -0.1873           |
| degradación validation -> test < 50 % de la expectativa                   | False    | 0.1231 -> -0.1608 |

## 17. Limitaciones
- Precio y volumen de NQ/GC para MNQ/MGC: el micro tiene menos liquidez; el deslizamiento real puede ser mayor.
- Con velas de 15 min no se conoce el orden de los precios dentro de la vela: stop y target en la misma vela = stop (pesimista); trailing y parcial se evalúan con la vela completa.
- Sesión del oro definida en hora de Nueva York: 2-3 semanas al año la apertura de Londres cae una hora antes o después.
- Sin ejecuciones parciales, rechazos, caídas de conexión ni cambios de margen. XAUUSD sin datos.
- NQ/GC con 1 contrato fijo: sus resultados en $ no son comparables con los micro; en R sí (salvo el peso de los costes).

## 18. Posibles problemas de sobreajuste
- Variantes evaluadas (aprox., sin contar el test): **539**. Con este número, varias parecerán buenas en train o validation por azar.
- MNQ: expectativa neta de la configuración final train -0.0043 → validation 0.0756 → test -0.0604 R (t test -1.56).
- MGC: expectativa neta de la configuración final train -0.0539 → validation 0.0858 → test -0.2253 R (t test -3.14).
- NQ: expectativa neta de la configuración final train 0.0204 → validation 0.0821 → test -0.0285 R (t test -0.85).
- GC: expectativa neta de la configuración final train -0.0006 → validation 0.1231 → test -0.1608 R (t test -2.32).
- La selección por validation elige, por construcción, lo que mejor le fue en validation; la caída en test mide cuánto de eso era azar. Los modelos A–D sin optimizar sirven de control.