# ORB en MNQ — periodo IS (2015-01-01 → 2023-01-01)

## Variantes

| variante    | costes     |   operaciones |   beneficio_neto |   costes_totales |   drawdown_max |   profit_factor |   pct_aciertos |   pct_dias_ganadores |   expectativa_R |   peor_dia |   peor_momento_intradia |   rechazadas_sin_presupuesto |   evaluaciones |   % aprobadas |   % suspendidas |   % caducadas |   dias medios hasta aprobar |
|:------------|:-----------|--------------:|-----------------:|-----------------:|---------------:|----------------:|---------------:|---------------------:|----------------:|-----------:|------------------------:|-----------------------------:|---------------:|--------------:|----------------:|--------------:|----------------------------:|
| ORB5_range  | con_costes |          1781 |        -16121.5  |           9457.5 |      -19723.5  |            0.88 |           41   |                 41   |          -0.063 |       -150 |                    -150 |                          202 |           1978 |             0 |             1.4 |          98.6 |                         nan |
| ORB5_range  | sin_costes |          1793 |         -2214.75 |              0   |       -8028.5  |            0.98 |           41.3 |                 41.3 |          -0.002 |       -150 |                    -150 |                          190 |            nan |           nan |           nan   |         nan   |                         nan |
| ORB5_atr    | con_costes |          1811 |        -12504.5  |           8899.5 |      -15530    |            0.9  |           41   |                 41   |          -0.057 |       -150 |                    -150 |                          172 |           1978 |             0 |             0.9 |          99.1 |                         nan |
| ORB5_atr    | sin_costes |          1826 |           705.75 |              0   |       -5530.46 |            1.01 |           41.4 |                 41.4 |           0.001 |       -150 |                    -150 |                          157 |            nan |           nan |           nan   |         nan   |                         nan |
| ORB15_range | con_costes |          1512 |        -10664.8  |           6048   |      -13867.5  |            0.89 |           42.8 |                 42.8 |          -0.05  |       -150 |                    -150 |                          444 |           1978 |             0 |             0   |         100   |                         nan |
| ORB15_range | sin_costes |          1527 |         -1682.75 |              0   |       -7797.25 |            0.98 |           43.4 |                 43.4 |          -0.004 |       -150 |                    -150 |                          429 |            nan |           nan |           nan   |         nan   |                         nan |
| ORB15_atr   | con_costes |          1785 |        -12441.8  |           8755.5 |      -16537.4  |            0.9  |           41.6 |                 41.6 |          -0.048 |       -150 |                    -150 |                          171 |           1978 |             0 |             0   |         100   |                         nan |
| ORB15_atr   | sin_costes |          1798 |           640.53 |              0   |       -6931.87 |            1.01 |           41.8 |                 41.8 |           0.011 |       -150 |                    -150 |                          158 |            nan |           nan |           nan   |         nan   |                         nan |
| ORB30_range | con_costes |          1306 |         -9920.25 |           4495.5 |      -10661    |            0.86 |           43.1 |                 43.1 |          -0.064 |       -150 |                    -150 |                          562 |           1978 |             0 |             0   |         100   |                         nan |
| ORB30_range | sin_costes |          1316 |         -4780.75 |              0   |       -6597    |            0.93 |           43.9 |                 43.9 |          -0.025 |       -150 |                    -150 |                          552 |            nan |           nan |           nan   |         nan   |                         nan |
| ORB30_atr   | con_costes |          1704 |        -14549.4  |           8365.5 |      -17905.8  |            0.88 |           41.2 |                 41.2 |          -0.066 |       -150 |                    -150 |                          164 |           1978 |             0 |             0   |         100   |                         nan |
| ORB30_atr   | sin_costes |          1717 |         -3223.17 |              0   |       -8309.87 |            0.97 |           41.5 |                 41.5 |          -0.007 |       -150 |                    -150 |                          151 |            nan |           nan |           nan   |         nan   |                         nan |

## Promedio de las 6 variantes (riesgo repartido)

- Beneficio neto: -12700 $
- Drawdown máximo: -14909 $
- % días ganadores (con operaciones): 43.2 %

## Correlación diaria entre variantes

|             |   ORB5_range |   ORB5_atr |   ORB15_range |   ORB15_atr |   ORB30_range |   ORB30_atr |
|:------------|-------------:|-----------:|--------------:|------------:|--------------:|------------:|
| ORB5_range  |         1    |       0.76 |          0.47 |        0.44 |          0.27 |        0.23 |
| ORB5_atr    |         0.76 |       1    |          0.42 |        0.47 |          0.26 |        0.25 |
| ORB15_range |         0.47 |       0.42 |          1    |        0.7  |          0.65 |        0.5  |
| ORB15_atr   |         0.44 |       0.47 |          0.7  |        1    |          0.45 |        0.59 |
| ORB30_range |         0.27 |       0.26 |          0.65 |        0.45 |          1    |        0.62 |
| ORB30_atr   |         0.23 |       0.25 |          0.5  |        0.59 |          0.62 |        1    |
