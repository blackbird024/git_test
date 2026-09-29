# VWAP_15M_2R_v1.0: desarrollo (sesiones < 22-mar-2023, 1 MNQ)

| variante   |   operaciones |   acierto_% |   profit_factor |   R_medio |     t |   neto_$ |   drawdown_max_$ |   racha_perdedora | cumple_criterio   |
|:-----------|--------------:|------------:|----------------:|----------:|------:|---------:|-----------------:|------------------:|:------------------|
| OFICIAL    |          3254 |        36.9 |            1.02 |    -0.087 | -3.75 |     2314 |            -7298 |                13 | False             |
| sin_costes |          3266 |        38.5 |            1.12 |     0.035 |  1.52 |    12390 |            -4430 |                12 | False             |

Por año (OFICIAL):

|      |   operaciones |   acierto_% |   profit_factor |   R_medio |     t |   neto_$ |   racha_perdedora |
|-----:|--------------:|------------:|----------------:|----------:|------:|---------:|------------------:|
| 2015 |           432 |        34.3 |            0.76 |    -0.202 | -3.21 |    -1555 |                13 |
| 2016 |           403 |        34.5 |            0.82 |    -0.224 | -3.53 |    -1070 |                11 |
| 2017 |           405 |        34.6 |            0.77 |    -0.233 | -3.62 |    -1176 |                13 |
| 2018 |           404 |        34.9 |            0.81 |    -0.116 | -1.79 |    -2235 |                 9 |
| 2019 |           382 |        38   |            0.93 |    -0.054 | -0.81 |     -553 |                 8 |
| 2020 |           419 |        42   |            1.37 |     0.116 |  1.7  |     6756 |                12 |
| 2021 |           362 |        37   |            1.05 |    -0.046 | -0.67 |      920 |                11 |
| 2022 |           364 |        39.6 |            1.02 |     0.073 |  1.04 |      680 |                 8 |
| 2023 |            83 |        41   |            1.12 |    -0.016 | -0.11 |      545 |                 6 |

Días por estado:
- OFICIAL: {'dias': 2084, 'operaciones_por_dia': 1.56}
- sin_costes: {'dias': 2084, 'operaciones_por_dia': 1.57}

Auditoría de look-ahead: OK

Criterio (solo la variante OFICIAL decide): PF > 1 y R medio > 0 con t ≥ 2 después de costes.