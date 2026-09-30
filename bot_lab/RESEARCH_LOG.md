# RESEARCH_LOG — Trading Bot Lab

Registro de todas las hipótesis probadas en el laboratorio: las negativas no se ocultan.

Todas se registraron el 30-sep-2026 (ver `CRITERIOS.md` y `research/hypotheses/`) y usan esta partición:

| Tramo | Periodo |
|---|---|
| TRAIN | 2015-01-02 → 2022-01-18 (excluido) |
| VALIDATION | 2022-01-18 → 2024-05-23 (excluido) |
| TEST | 2024-05-23 → 2026-09-28 |

El TEST está reservado para estas reglas, pero **no es fuera de muestra puro**.

**Variantes ejecutadas en el cribado: 70** (más las vecindades y el walk-forward del finalista).

**Hipótesis previas del proyecto sobre NQ** (auditoría y `archive/`): unas 25 ideas y más de 60 variantes.

## BOT 13 — VWAP mean reversion
```text
strategy_id:        BOT13
hypothesis:         Cuando NQ se aleja significativamente del VWAP de la sesión, el precio tiende a volver hacia el VWAP.
date_created:       2026-09-30
parameters_tested:  entrada, k, medida, objetivo, stop, vwap
number_of_variants: 11
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE. TRAIN: 2560 op., expectativa -1.82 $, PF 0.88, t -2.17
selected_variant:   13.04 k2.0
reason_for_selection: mayor t en TRAIN (-2.17) entre 11 variantes con ≥ 100 operaciones
```

## BOT 14 — Opening range breakout
```text
strategy_id:        BOT14
hypothesis:         La ruptura del rango inicial de una sesión captura la expansión de volatilidad posterior.
date_created:       2026-09-30
parameters_tested:  filtro, n, salida, sesion, stop
number_of_variants: 14
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE. TRAIN: 871 op., expectativa 3.79 $, PF 1.12, t 1.13
selected_variant:   14.13 base + filtro compresión
reason_for_selection: mayor t en TRAIN (1.13) entre 14 variantes con ≥ 100 operaciones
```

## BOT 15 — Trend following
```text
strategy_id:        BOT15
hypothesis:         Cuando NQ presenta una tendencia suficientemente fuerte, las rupturas a su favor tienen expectativa positiva.
date_created:       2026-09-30
parameters_tested:  ema, ruptura, salida, stop_atr, tendencia
number_of_variants: 6
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE. TRAIN: 1907 op., expectativa 1.32 $, PF 1.05, t 0.70
selected_variant:   15.06 salida trailing 3 ATR
reason_for_selection: mayor t en TRAIN (0.70) entre 6 variantes con ≥ 100 operaciones
```

## BOT 16 — Momentum breakout
```text
strategy_id:        BOT16
hypothesis:         Una expansión repentina de volatilidad con ruptura del rango reciente continúa durante cierto tiempo.
date_created:       2026-09-30
parameters_tested:  filtro_vol, m, minutos, n, salida
number_of_variants: 9
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE. TRAIN: 3102 op., expectativa -1.62 $, PF 0.90, t -1.76
selected_variant:   16.09 + volumen relativo > 1.5
reason_for_selection: mayor t en TRAIN (-1.76) entre 9 variantes con ≥ 100 operaciones
```

## BOT 17 — Pullback trend
```text
strategy_id:        BOT17
hypothesis:         En una tendencia establecida, entrar tras un retroceso ofrece mejor relación riesgo/beneficio que perseguir la ruptura.
date_created:       2026-09-30
parameters_tested:  ema_corta, ema_larga, retroceso, salida
number_of_variants: 4
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE. TRAIN: 2740 op., expectativa 0.12 $, PF 1.00, t 0.07
selected_variant:   17.04 EMA200 + VWAP, salida 15:55
reason_for_selection: mayor t en TRAIN (0.07) entre 4 variantes con ≥ 100 operaciones
```

## BOT 18 — RSI(2) extremo + filtro de tendencia
```text
strategy_id:        BOT18
hypothesis:         La reversión tras un extremo de RSI(2) funciona mejor cuando el mercado no está en una tendencia extrema en contra.
date_created:       2026-09-30
parameters_tested:  filtro, max_dias, umbral
number_of_variants: 8
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE. TRAIN: 134 op., expectativa 43.87 $, PF 1.41, t 1.42
selected_variant:   18.1A RSI<5/>95 puro
reason_for_selection: mayor t en TRAIN (1.42) entre 3 variantes con ≥ 30 operaciones
```

## BOT 19 — VWAP + régimen
```text
strategy_id:        BOT19
hypothesis:         La reversión al VWAP funciona en rango y falla en tendencia; en tendencia funciona la continuación a favor del VWAP.
date_created:       2026-09-30
parameters_tested:  estrategia, medida, regimen
number_of_variants: 6
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE. TRAIN: 1295 op., expectativa -0.97 $, PF 0.97, t -0.43
selected_variant:   19.03 Tendencia VWAP solo en TENDENCIA (ADX)
reason_for_selection: mayor t en TRAIN (-0.43) entre 4 variantes con ≥ 100 operaciones
```

## BOT 21 — Hora del día (deriva nocturna)
```text
strategy_id:        BOT21
hypothesis:         Los rendimientos de los futuros de índices de EE. UU. se concentran fuera del horario regular, sobre todo en torno a la apertura europea (Boyarchenko, Larsen y Whelan, 2023).
date_created:       2026-09-30
parameters_tested:  cruza_medianoche, desde, hasta
number_of_variants: 2
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE (falla VALIDATION). TRAIN: 1766 op., expectativa 4.90 $, PF 1.14, t 1.62; VALIDATION: 587 op., expectativa -5.35 $, PF 0.93
selected_variant:   21.1 largo 18:00→09:25 NY
reason_for_selection: mayor t en TRAIN (1.62) entre 2 variantes con ≥ 100 operaciones
```

## BOT 23 — Niveles del día anterior
```text
strategy_id:        BOT23
hypothesis:         El máximo, el mínimo y el cierre de la sesión regular anterior son zonas de liquidez donde el precio reacciona de forma medible.
date_created:       2026-09-30
parameters_tested:  atr_k, min_hueco, modelo, zona
number_of_variants: 4
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE. TRAIN: 850 op., expectativa -2.87 $, PF 0.83, t -2.01
selected_variant:   23.1 ruptura PDH/PDL
reason_for_selection: mayor t en TRAIN (-2.01) entre 3 variantes con ≥ 100 operaciones
```

## BOT 24 — Rango nocturno → NY
```text
strategy_id:        BOT24
hypothesis:         La relación entre el rango nocturno y la apertura de NY contiene información sobre expansión o reversión.
date_created:       2026-09-30
parameters_tested:  atr_k, modelo
number_of_variants: 3
data_period:        NQ 1 min Databento 2015-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (abierto solo para el finalista)
result:             B — PROMISING (clasificación automática tras abrir el TEST). TRAIN: 1312 op., expectativa 4.86 $, PF 1.16, t 1.69; VALIDATION: 457 op., expectativa 4.53 $, PF 1.06
selected_variant:   24.3 VWAP + punto medio a las 10:00
reason_for_selection: mayor t en TRAIN (1.69) entre 3 variantes con ≥ 100 operaciones
```

## BOT 26 — Spread estadístico oro/plata
```text
strategy_id:        BOT26
hypothesis:         Los extremos del z-score del spread normalizado oro/plata revierten.
date_created:       2026-09-30
parameters_tested:  max_dias, ventana, z
number_of_variants: 3
data_period:        GC/SI diarios Databento 2010-2026
train_period:       2015-01-02 → 2022-01-18
validation_period:  2022-01-18 → 2024-05-23
test_period:        2024-05-23 → 2026-09-28 (no abierto: no pasó a finalista)
result:             E — NEGATIVE. TRAIN: 74 op., expectativa -20.82 $, PF 0.96, t -0.14
selected_variant:   26.3 z ±2.0
reason_for_selection: mayor t en TRAIN (-0.14) entre 3 variantes con ≥ 30 operaciones
```

## BOT 20 / 21 (parte 1) / 22 — investigación sin estrategia
Regímenes, deriva por franja horaria y por día de la semana. Solo TRAIN y solo informativo: no se ha creado ninguna estrategia a partir de estos resultados. Ver `reports/FINAL_REPORT.md`.

## BOT 25 y BOT 26 (NQ/ES) — pendientes
No hay datos de 1 min de ES en el proyecto. Descargarlos cuesta 15,06 $ en Databento (consultado el 30-sep, sin descargar), por encima del límite de 0,50 $ que exige preguntar. Quedan sin probar.
