# Diagnóstico — OR_VWAP_v1.0 (desarrollo 2015-01-01 → 2023-03-21)

## Auditoría de look-ahead (variante oficial REL_0.45PCT, escenario 1)

| punto                                                                              | resultado   | detalle                                                                                        |
|:-----------------------------------------------------------------------------------|:------------|:-----------------------------------------------------------------------------------------------|
| Datos: nada del fuera de muestra                                                   | OK          | última vela cargada 2023-03-21 23:59:00+00:00 < 2023-03-22 00:00:00+00:00                      |
| OR: máximo/mínimo de 09:30-09:44 NY, cerrado antes de la señal                     | OK          | 999 operaciones revisadas; fallos: 0                                                           |
| VWAP: recalculado solo con velas hasta la señal = VWAP usado                       | OK          | 999 operaciones revisadas; fallos: 0                                                           |
| Señal: idéntica con los datos cortados en la vela de señal                         | OK          | 999 operaciones revisadas; fallos: 0                                                           |
| Entrada: apertura de la vela siguiente + deslizamiento                             | OK          | 999 operaciones revisadas; fallos: 0                                                           |
| Stop (extremo opuesto del OR) y objetivo (2R) fijados en la entrada                | OK          | 999 operaciones revisadas; fallos: 0                                                           |
| Salida: primera vela que toca stop/objetivo; misma vela = pérdida; tiempo en 15:55 | OK          | 999 operaciones revisadas; fallos: 0                                                           |
| Saldo usado para el tamaño = saldo antes de la operación                           | OK          | 999 operaciones revisadas; fallos: 0                                                           |
| Tamaño = position_sizing.contratos(saldo, 0,5 %, R, 2 $)                           | OK          | 999 operaciones revisadas; fallos: 0                                                           |
| Sesiones recortadas (cierre a las 13:00 NY): salida en la última vela              | AVISO       | 28 operaciones; no es look-ahead (horario publicado de antemano), pero las reglas no lo prevén |
| Truncamiento global (6 cortes en sábado, 2016-2022)                                | OK          | señales anteriores a cada corte idénticas                                                      |
| Estado de Apex                                                                     | N/A         | este backtest no usa estado de Apex (la simulación de Apex es una fase posterior)              |

## Estados por día (todas las combinaciones)

| variant     |   scenario |   days_NO_SIGNAL |   days_OR_INCOMPLETE |   days_RISK_ABOVE_CAP |   days_TRADED |   days_POSITION_SIZE_BELOW_MINIMUM |
|:------------|-----------:|-----------------:|---------------------:|----------------------:|--------------:|-----------------------------------:|
| REL_0.45PCT |          0 |                6 |                    3 |                  1067 |          1008 |                                  0 |
| REL_0.45PCT |          1 |                6 |                    3 |                  1076 |           999 |                                  0 |
| REL_0.45PCT |          2 |                6 |                    3 |                  1095 |           980 |                                  0 |
| FIXED_40PTS |          0 |                6 |                    3 |                   924 |          1151 |                                  0 |
| FIXED_40PTS |          1 |                6 |                    3 |                   925 |          1150 |                                  0 |
| FIXED_40PTS |          2 |                6 |                    3 |                   927 |          1148 |                                  0 |
| NO_CAP      |          0 |                6 |                    3 |                     0 |          2011 |                                 64 |
| NO_CAP      |          1 |                6 |                    3 |                     0 |          1766 |                                309 |
| NO_CAP      |          2 |                6 |                    3 |                     0 |          1617 |                                458 |

## Distribución de R (variante oficial)

| r             |   escenario 0 |   escenario 1 |   escenario 2 |
|:--------------|--------------:|--------------:|--------------:|
| [-inf, -1.25) |             0 |             3 |             5 |
| [-1.25, -1.0) |             0 |           484 |           479 |
| [-1.0, -0.75) |           496 |            11 |            11 |
| [-0.75, -0.5) |            21 |            25 |            28 |
| [-0.5, -0.25) |            32 |            29 |            31 |
| [-0.25, 0.0)  |            41 |            44 |            43 |
| [0.0, 0.25)   |            35 |            41 |            42 |
| [0.25, 0.5)   |            48 |            46 |            44 |
| [0.5, 1.0)    |            62 |            59 |            57 |
| [1.0, 1.5)    |            53 |            46 |            44 |
| [1.5, 1.9)    |            18 |            33 |            30 |
| [1.9, inf)    |           202 |           178 |           166 |

|   scenario |   count |   mean |   std |    min |     5% |    25% |    50% |   75% |   95% |   max |
|-----------:|--------:|-------:|------:|-------:|-------:|-------:|-------:|------:|------:|------:|
|          0 |    1008 |  0.04  | 1.214 | -1     | -1     | -1     | -0.659 | 1.173 | 2     | 2     |
|          1 |     999 | -0.037 | 1.216 | -1.625 | -1.116 | -1.067 | -0.725 | 1.059 | 1.965 | 1.986 |
|          2 |     980 | -0.076 | 1.206 | -1.667 | -1.14  | -1.081 | -0.806 | 0.941 | 1.966 | 1.986 |
