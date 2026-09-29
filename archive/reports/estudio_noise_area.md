# Estudio noise_area (2015-01-02 → 2026-09-25)

Configuración: `config/noise_area.yaml`. Desarrollo: hasta 2023-03-06; fuera de muestra: desde 2023-03-06.

Criterios (todos): profit factor > 1.15, t > 2.0, neto positivo en desarrollo y fuera de muestra.

## Variantes

| variante                                 |   operaciones |   beneficio_neto |   beneficio_bruto |   comisiones |   profit_factor |   pct_acierto |   media_por_op |   expectativa_R |   drawdown_max |   racha_perdedora_max |    t |   neto_desarrollo |   t_desarrollo |   neto_oos |   t_oos |   neto_con_1tick_en_salida |   cuentas_quemadas | primera_quema   |   prob_quemar_% |   operacion_mediana_al_quemar |   dd_cerrado_p50 |   dd_cerrado_p95 | CUMPLE   |
|:-----------------------------------------|--------------:|-----------------:|------------------:|-------------:|----------------:|--------------:|---------------:|----------------:|---------------:|----------------------:|-----:|------------------:|---------------:|-----------:|--------:|---------------------------:|-------------------:|:----------------|----------------:|------------------------------:|-----------------:|-----------------:|:---------|
| ZonaRuido_MNQ_comoEstudio_volObjetivo    |          2687 |            48090 |             74782 |        26692 |            1.15 |          37.6 |           17.9 |           0.022 |         -12188 |                    14 | 2.19 |             24483 |           1.29 |      23606 |    2.11 |                      48090 |                 88 | 2015-04-29      |             100 |                            23 |            11535 |            18047 | NO       |
| ZonaRuido_MNQ_comoEstudio_1contrato_fijo |          2713 |            20138 |             25564 |         5426 |            1.19 |          37.6 |            7.4 |           0.021 |          -3602 |                    14 | 2.15 |              9090 |           1.3  |      11048 |    2.03 |                      20138 |                  6 | 2025-07-16      |             100 |                           227 |             4164 |             6567 | SÍ       |
| ZonaRuido_MNQ_stopDuro_volObjetivo       |          3920 |            24805 |             63857 |        39052 |            1.09 |          21.4 |            6.3 |           0.007 |         -15881 |                    25 | 1.2  |             10946 |           0.56 |      13859 |    1.42 |                      24805 |                 69 | 2015-04-08      |             100 |                            45 |            11877 |            18733 | NO       |
| ZonaRuido_MNQ_stopDuro_1contrato_fijo    |          3954 |            14784 |             22692 |         7908 |            1.17 |          21.4 |            3.7 |           0.007 |          -2617 |                    25 | 1.22 |              8059 |           0.56 |       6725 |    1.44 |                      14784 |                  5 | 2021-01-04      |             100 |                           524 |             3476 |             5439 | NO       |

## Beneficio neto por año ($)

|   date |   ZonaRuido_MNQ_comoEstudio_volObjetivo |   ZonaRuido_MNQ_comoEstudio_1contrato_fijo |   ZonaRuido_MNQ_stopDuro_volObjetivo |   ZonaRuido_MNQ_stopDuro_1contrato_fijo |
|-------:|----------------------------------------:|-------------------------------------------:|-------------------------------------:|----------------------------------------:|
|   2015 |                                    2698 |                                        110 |                                -2912 |                                    -470 |
|   2016 |                                   -5540 |                                       -614 |                                -6681 |                                    -656 |
|   2017 |                                   -2595 |                                       -226 |                                -5332 |                                    -557 |
|   2018 |                                   17101 |                                       3447 |                                14096 |                                    3002 |
|   2019 |                                   -3275 |                                       -342 |                                -5755 |                                    -638 |
|   2020 |                                    6697 |                                       1149 |                                 6095 |                                     783 |
|   2021 |                                    2346 |                                       1404 |                                 3977 |                                    1538 |
|   2022 |                                    6136 |                                       3964 |                                 6993 |                                    4907 |
|   2023 |                                   12086 |                                       3722 |                                 8107 |                                    2783 |
|   2024 |                                    7016 |                                       2078 |                                 6765 |                                    2439 |
|   2025 |                                    3891 |                                       3904 |                                 -468 |                                     321 |
|   2026 |                                    1529 |                                       1544 |                                  -81 |                                    1333 |

## Días operados y motivos para no operar

| status               |   ZonaRuido_MNQ_comoEstudio_volObjetivo |   ZonaRuido_MNQ_comoEstudio_1contrato_fijo |   ZonaRuido_MNQ_stopDuro_volObjetivo |   ZonaRuido_MNQ_stopDuro_1contrato_fijo |
|:---------------------|----------------------------------------:|-------------------------------------------:|-------------------------------------:|----------------------------------------:|
| capital_insuficiente |                                      41 |                                          0 |                                   41 |                                       0 |
| operada              |                                    1692 |                                       1709 |                                 1692 |                                    1709 |
| sin_historia         |                                      11 |                                         11 |                                   11 |                                      11 |
| sin_senal            |                                    1164 |                                       1188 |                                 1164 |                                    1188 |
