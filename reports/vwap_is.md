# Tendencia VWAP en MNQ y MGC — periodo IS (2015-01-01 → 2023-01-01)

## Variantes

| variante        | costes     |   operaciones |   beneficio_neto |   costes_totales |   drawdown_max |   profit_factor |   pct_aciertos |   pct_dias_ganadores |   expectativa_R |   peor_dia |   peor_momento_intradia |   rechazadas_sin_presupuesto |   evaluaciones |   % aprobadas |   % suspendidas |   % caducadas |   dias medios hasta aprobar |
|:----------------|:-----------|--------------:|-----------------:|-----------------:|---------------:|----------------:|---------------:|---------------------:|----------------:|-----------:|------------------------:|-----------------------------:|---------------:|--------------:|----------------:|--------------:|----------------------------:|
| VWAP_MNQ_atr0.1 | con_costes |          1764 |        -18644.7  |          16108.5 |      -29182    |            0.88 |           34.7 |                 34.7 |          -0.068 |    -149.98 |                 -149.98 |                            4 |           1972 |             0 |             0.8 |          99.2 |                         nan |
| VWAP_MNQ_atr0.1 | sin_costes |          1764 |          4857.17 |              0   |      -11242.2  |            1.03 |           34.7 |                 34.7 |           0.03  |    -149.98 |                 -149.98 |                            4 |            nan |           nan |           nan   |         nan   |                         nan |
| VWAP_MNQ_atr0.2 | con_costes |          1651 |        -13614.8  |           8937   |      -20871.8  |            0.89 |           37.1 |                 37.1 |          -0.053 |    -149.99 |                 -149.99 |                          117 |           1972 |             0 |             0.1 |          99.9 |                         nan |
| VWAP_MNQ_atr0.2 | sin_costes |          1660 |          -148.06 |              0   |      -10415    |            1    |           37.3 |                 37.3 |           0.009 |    -149.99 |                 -149.99 |                          108 |            nan |           nan |           nan   |         nan   |                         nan |
| VWAP_MGC_atr0.1 | con_costes |          1825 |        -26868.2  |          21564   |      -27644.9  |            0.83 |           36.8 |                 36.8 |          -0.101 |    -156    |                 -156    |                            0 |           1919 |             0 |             0.9 |          99.1 |                         nan |
| VWAP_MGC_atr0.1 | sin_costes |          1825 |         22259.2  |              0   |       -3668.01 |            1.14 |           37.2 |                 37.2 |           0.092 |    -160    |                 -160    |                            0 |            nan |           nan |           nan   |         nan   |                         nan |
| VWAP_MGC_atr0.2 | con_costes |          1825 |         -7913.28 |          12805.5 |      -11956.7  |            0.94 |           39.8 |                 39.8 |          -0.03  |    -149.94 |                 -149.94 |                            0 |           1919 |             0 |             0.2 |          99.8 |                         nan |
| VWAP_MGC_atr0.2 | sin_costes |          1825 |         23127.2  |              0   |       -3467    |            1.17 |           41.3 |                 41.3 |           0.092 |    -150    |                 -150    |                            0 |            nan |           nan |           nan   |         nan   |                         nan |

## Promedio de las 4 variantes (riesgo repartido)

- Beneficio neto: -17334 $
- Drawdown máximo: -20584 $
- % días ganadores (con operaciones): 45.9 %

## Correlación diaria entre variantes

|                 |   VWAP_MNQ_atr0.1 |   VWAP_MNQ_atr0.2 |   VWAP_MGC_atr0.1 |   VWAP_MGC_atr0.2 |
|:----------------|------------------:|------------------:|------------------:|------------------:|
| VWAP_MNQ_atr0.1 |              1    |              0.58 |              0.06 |              0.06 |
| VWAP_MNQ_atr0.2 |              0.58 |              1    |              0.04 |              0.03 |
| VWAP_MGC_atr0.1 |              0.06 |              0.04 |              1    |              0.62 |
| VWAP_MGC_atr0.2 |              0.06 |              0.03 |              0.62 |              1    |
