# Estudio cm (2015-01-02 → 2026-09-25)

Configuración: `config/close_momentum.yaml`. Desarrollo: hasta 2023-03-06; fuera de muestra: desde 2023-03-06.

Criterios (todos): profit factor > 1.15, t > 2.0, neto positivo en desarrollo y fuera de muestra.

## Variantes

| variante           |   operaciones |   beneficio_neto |   beneficio_bruto |   comisiones |   profit_factor |   pct_acierto |   media_por_op |   expectativa_R |   drawdown_max |   racha_perdedora_max |     t |   neto_desarrollo |   t_desarrollo |   neto_oos |   t_oos |   neto_con_1tick_en_salida |   cuentas_quemadas | primera_quema   |   prob_quemar_% |   operacion_mediana_al_quemar |   dd_cerrado_p50 |   dd_cerrado_p95 | CUMPLE   |
|:-------------------|--------------:|-----------------:|------------------:|-------------:|----------------:|--------------:|---------------:|----------------:|---------------:|----------------------:|------:|------------------:|---------------:|-----------:|--------:|---------------------------:|-------------------:|:----------------|----------------:|------------------------------:|-----------------:|-----------------:|:---------|
| CM_stop0.1ATR_150$ |          2867 |           -38899 |             -9845 |        29054 |            0.8  |          38.6 |          -13.6 |          -0.121 |         -40626 |                    14 | -5.2  |            -32878 |          -5.32 |      -6021 |   -1.32 |                     -42899 |                 33 | 2015-04-20      |             100 |                            72 |            40150 |            42756 | NO       |
| CM_stop0.1ATR_250$ |          2887 |           -50598 |            -12638 |        37960 |            0.83 |          38.7 |          -17.5 |          -0.12  |         -54134 |                    14 | -5.19 |            -39810 |          -5.32 |     -10789 |   -1.32 |                     -55834 |                 63 | 2015-04-20      |             100 |                            37 |            53112 |            57776 | NO       |

## Beneficio neto por año ($)

|   date |   CM_stop0.1ATR_150$ |   CM_stop0.1ATR_250$ |
|-------:|---------------------:|---------------------:|
|   2015 |                -8746 |                -9017 |
|   2016 |                -5809 |                -6494 |
|   2017 |                -7682 |                -7707 |
|   2018 |                  688 |                 1133 |
|   2019 |                -5530 |                -8959 |
|   2020 |                 2910 |                 5424 |
|   2021 |                -6221 |               -10004 |
|   2022 |                -1849 |                -3059 |
|   2023 |                -3881 |                -7731 |
|   2024 |                 -825 |                -2354 |
|   2025 |                -1235 |                -1563 |
|   2026 |                 -717 |                 -266 |

## Días operados y motivos para no operar

| status                             |   CM_stop0.1ATR_150$ |   CM_stop0.1ATR_250$ |
|:-----------------------------------|---------------------:|---------------------:|
| manana_plana                       |                    7 |                    7 |
| operada                            |                 2867 |                 2887 |
| riesgo_de_1_contrato_excede_limite |                   20 |                    0 |
| sin_atr                            |                   14 |                   14 |
