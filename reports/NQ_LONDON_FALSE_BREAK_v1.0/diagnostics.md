# Diagnóstico: NQ_LONDON_FALSE_BREAK_v1.0 (desarrollo, 8.21 años)

## Auditoría de look-ahead

| punto                                                                                       | resultado   | detalle                    |
|:--------------------------------------------------------------------------------------------|:------------|:---------------------------|
| Rango: 4 velas 08:00-08:45 de Londres, congelado a las 09:00 (antes de cualquier señal)     | OK          | 861 operaciones; fallos: 0 |
| Primer break / falsa ruptura recalculados con datos cortados en la vela de señal (<= 11:30) | OK          | 861 operaciones; fallos: 0 |
| Entrada: apertura de la vela 15m siguiente, antes de las 12:00                              | OK          | 861 operaciones; fallos: 0 |
| SL: extremo de la vela de la falsa ruptura ± 0,10 × ATR(14) calculado hasta su cierre       | OK          | 861 operaciones; fallos: 0 |
| TP = entrada ± 2R con la entrada real                                                       | OK          | 861 operaciones; fallos: 0 |
| Salida por tiempo: cierre de la última vela anterior a las 12:00; nada abierto después      | OK          | 861 operaciones; fallos: 0 |
| Truncamiento global (6 cortes en sábado): entradas anteriores idénticas                     | OK          | sin diferencias            |

## Estado de cada día (escenario B)

| estado                      |    n |
|:----------------------------|-----:|
| NO_FALSE_BREAK              | 1166 |
| TRADED                      |  861 |
| POSITION_SIZE_BELOW_MINIMUM |   52 |
| RANGE_INCOMPLETE            |   14 |
| BOTH_SIDES_SAME_BAR         |    5 |

## Primer extremo atacado (días con rango válido)

| extremo   |   n |
|:----------|----:|
| HIGH      | 983 |
| LOW       | 937 |
| nan       | 173 |
| BOTH      |   5 |

## Rango × profundidad: R medio (escenario B)

| range_tercile   |   prof. baja |   prof. media |   prof. alta |
|:----------------|-------------:|--------------:|-------------:|
| rango bajo      |       -0.915 |        -0.54  |       -0.596 |
| rango medio     |       -0.39  |        -0.569 |       -0.061 |
| rango alto      |       -0.255 |        -0.291 |       -0.152 |

Número de operaciones:

| range_tercile   |   prof. baja |   prof. media |   prof. alta |
|:----------------|-------------:|--------------:|-------------:|
| rango bajo      |           66 |            97 |          124 |
| rango medio     |           94 |            91 |          102 |
| rango alto      |          127 |            99 |           61 |

## Correlación de Spearman (escenario B)

|                   |   range_pct |   break_depth_ratio |     r |
|:------------------|------------:|--------------------:|------:|
| range_pct         |       1     |              -0.27  | 0.266 |
| break_depth_ratio |      -0.27  |               1     | 0.065 |
| r                 |       0.266 |               0.065 | 1     |

## Fuera de muestra

BLOQUEADO: no se ha ejecutado (decisión del usuario).
