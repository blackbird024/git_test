# Diagnóstico: GOLD_LONDON_FALSE_BREAK_v1.0 (desarrollo, 8.21 años)

## Auditoría de look-ahead

| punto                                                                                       | resultado   | detalle                    |
|:--------------------------------------------------------------------------------------------|:------------|:---------------------------|
| Rango: 4 velas 08:00-08:45 de Londres, congelado a las 09:00 (antes de cualquier señal)     | OK          | 930 operaciones; fallos: 0 |
| Primer break / falsa ruptura recalculados con datos cortados en la vela de señal (<= 11:30) | OK          | 930 operaciones; fallos: 0 |
| Entrada: apertura de la vela 15m siguiente, antes de las 12:00                              | OK          | 930 operaciones; fallos: 0 |
| SL: extremo de la vela de la falsa ruptura ± 0,10 × ATR(14) calculado hasta su cierre       | OK          | 930 operaciones; fallos: 0 |
| TP = entrada ± 2R con la entrada real                                                       | OK          | 930 operaciones; fallos: 0 |
| Salida por tiempo: cierre de la última vela anterior a las 12:00; nada abierto después      | OK          | 930 operaciones; fallos: 0 |
| Truncamiento global (6 cortes en sábado): entradas anteriores idénticas                     | OK          | sin diferencias            |

## Estado de cada día (escenario B)

| estado              |    n |
|:--------------------|-----:|
| NO_FALSE_BREAK      | 1150 |
| TRADED              |  930 |
| RANGE_INCOMPLETE    |   18 |
| BOTH_SIDES_SAME_BAR |    5 |

## Primer extremo atacado (días con rango válido)

| extremo   |   n |
|:----------|----:|
| HIGH      | 957 |
| LOW       | 950 |
| nan       | 191 |
| BOTH      |   5 |

## Rango × profundidad: R medio (escenario B)

| range_tercile   |   prof. baja |   prof. media |   prof. alta |
|:----------------|-------------:|--------------:|-------------:|
| rango bajo      |       -0.863 |        -0.485 |       -0.514 |
| rango medio     |       -0.211 |        -0.462 |       -0.228 |
| rango alto      |       -0.375 |        -0.221 |       -0.218 |

Número de operaciones:

| range_tercile   |   prof. baja |   prof. media |   prof. alta |
|:----------------|-------------:|--------------:|-------------:|
| rango bajo      |           75 |            92 |          143 |
| rango medio     |          101 |           104 |          105 |
| rango alto      |          135 |           114 |           61 |

## Correlación de Spearman (escenario B)

|                   |   range_pct |   break_depth_ratio |     r |
|:------------------|------------:|--------------------:|------:|
| range_pct         |       1     |              -0.286 | 0.206 |
| break_depth_ratio |      -0.286 |               1     | 0.09  |
| r                 |       0.206 |               0.09  | 1     |

## Fuera de muestra

BLOQUEADO: no se ha ejecutado (decisión del usuario).
