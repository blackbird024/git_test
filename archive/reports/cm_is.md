# Momentum de cierre en MNQ — periodo IS (2015-01-01 → 2023-01-01)

## Variantes

| variante   | costes     |   operaciones |   beneficio_neto |   costes_totales |   drawdown_max |   profit_factor |   pct_aciertos |   pct_dias_ganadores |   expectativa_R |   peor_dia |   peor_momento_intradia |   rechazadas_sin_presupuesto |   evaluaciones |   % aprobadas |   % suspendidas |   % caducadas |   dias medios hasta aprobar |
|:-----------|:-----------|--------------:|-----------------:|-----------------:|---------------:|----------------:|---------------:|---------------------:|----------------:|-----------:|------------------------:|-----------------------------:|---------------:|--------------:|----------------:|--------------:|----------------------------:|
| CM_atr0.1  | con_costes |          1979 |        -39997.9  |            21636 |      -40393.9  |            0.7  |           38.5 |                 38.5 |          -0.148 |       -150 |                    -150 |                            0 |           1978 |             0 |             0.2 |          99.8 |                         nan |
| CM_atr0.1  | sin_costes |          1979 |         -6362.74 |                0 |       -7917.92 |            0.95 |           42.8 |                 42.8 |          -0.025 |       -150 |                    -150 |                            0 |            nan |           nan |           nan   |         nan   |                         nan |
| CM_atr0.2  | con_costes |          1907 |        -18981.6  |            11250 |      -19388.1  |            0.74 |           43.6 |                 43.6 |          -0.074 |       -150 |                    -150 |                           72 |           1978 |             0 |             0   |         100   |                         nan |
| CM_atr0.2  | sin_costes |          1911 |          -158.93 |                0 |       -4021.68 |            1    |           49.3 |                 49.3 |          -0.001 |       -150 |                    -150 |                           68 |            nan |           nan |           nan   |         nan   |                         nan |

## Promedio de las 2 variantes (riesgo repartido)

- Beneficio neto: -29490 $
- Drawdown máximo: -29786 $
- % días ganadores (con operaciones): 39.4 %

## Correlación diaria entre variantes

|           |   CM_atr0.1 |   CM_atr0.2 |
|:----------|------------:|------------:|
| CM_atr0.1 |        1    |        0.75 |
| CM_atr0.2 |        0.75 |        1    |
