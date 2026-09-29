# OR_LONDON_VWAP_v1.0: desarrollo (sesiones < 22-mar-2023, 1 MNQ)

| variante                   |   operaciones |   acierto_% |   profit_factor |   R_medio |     t |   neto_$ |   drawdown_max_$ |   racha_perdedora | cumple_criterio   |
|:---------------------------|--------------:|------------:|----------------:|----------:|------:|---------:|-----------------:|------------------:|:------------------|
| OFICIAL_con_londres        |          1844 |        47.2 |            1.09 |     0     |  0.01 |     7650 |            -3050 |                11 | False             |
| sin_costes                 |          1844 |        48.8 |            1.16 |     0.038 |  1.9  |    13086 |            -2860 |                 9 | False             |
| control_sin_filtro_londres |          2031 |        45.3 |            1    |    -0.024 | -1.16 |      492 |            -8124 |                13 | False             |

Por año (OFICIAL):

|      |   operaciones |   acierto_% |   profit_factor |   R_medio |     t |   neto_$ |   racha_perdedora |
|-----:|--------------:|------------:|----------------:|----------:|------:|---------:|------------------:|
| 2015 |           229 |        45.4 |            0.89 |    -0.051 | -0.9  |     -520 |                 8 |
| 2016 |           224 |        40.6 |            0.84 |    -0.086 | -1.48 |     -754 |                 7 |
| 2017 |           221 |        44.8 |            0.87 |    -0.036 | -0.63 |     -518 |                 9 |
| 2018 |           236 |        44.1 |            1.08 |    -0.005 | -0.08 |      814 |                 9 |
| 2019 |           210 |        44.3 |            1.03 |    -0.004 | -0.06 |      192 |                 8 |
| 2020 |           225 |        52   |            0.99 |     0.053 |  0.89 |     -212 |                11 |
| 2021 |           221 |        53.8 |            1.21 |     0.078 |  1.42 |     2991 |                 5 |
| 2022 |           231 |        52.8 |            1.29 |     0.072 |  1.27 |     6459 |                 6 |
| 2023 |            47 |        46.8 |            0.82 |    -0.097 | -0.73 |     -802 |                 5 |

Días por estado:
- OFICIAL_con_londres: {'operada': 1844, 'sin_senal': 236, 'rango_incompleto': 7}
- sin_costes: {'operada': 1844, 'sin_senal': 236, 'rango_incompleto': 7}
- control_sin_filtro_londres: {'operada': 2031, 'rango_incompleto': 7, 'sin_senal': 49}

Auditoría de look-ahead: OK

Criterio (solo la variante OFICIAL decide): PF > 1 y R medio > 0 con t ≥ 2 después de costes.