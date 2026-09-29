# SMC_KZ_NQ_v1.0: desarrollo (sesiones < 22-mar-2023, 1 MNQ, costes estándar)

| variante              |   operaciones |   acierto_% |   profit_factor |   R_medio |     t |   neto_$ |   drawdown_max_$ |   racha_perdedora |   PF_antes_costes |   R_medio_antes_costes | veredicto   |
|:----------------------|--------------:|------------:|----------------:|----------:|------:|---------:|-----------------:|------------------:|------------------:|-----------------------:|:------------|
| A_original_0930_1530  |            17 |        41.2 |            0.82 |     0.085 |  0.28 |     -120 |             -230 |                 2 |              0.87 |                  0.136 | RECHAZADA   |
| B_london_kz_0200_0500 |            10 |        30   |            1.13 |    -0.526 | -1.77 |       13 |             -102 |                 7 |              1.38 |                 -0.383 | RECHAZADA   |
| C_ny_kz_0700_1000     |             8 |        25   |            0.35 |    -0.47  | -0.96 |     -184 |             -224 |                 4 |              0.38 |                 -0.347 | RECHAZADA   |

Días por motivo:
- A_original_0930_1530: {'sin_patron': 2053, 'limite_no_llenado': 9, 'recompensa_menor_que_1R': 7, 'operada': 17}
- B_london_kz_0200_0500: {'sin_patron': 2071, 'operada': 10, 'recompensa_menor_que_1R': 3, 'limite_no_llenado': 2}
- C_ny_kz_0700_1000: {'sin_patron': 2059, 'operada': 8, 'limite_no_llenado': 10, 'recompensa_menor_que_1R': 9}

Criterio: PF > 1 y R medio > 0 con t ≥ 2 después de costes, por variante. Fuera de muestra sin tocar.