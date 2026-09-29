# Diagnóstico: GOLD_SWING_MINIMAL_v1.0 (desarrollo, 8.21 años)

## Auditoría de look-ahead

| punto                                                                                         | resultado   | detalle                     |
|:----------------------------------------------------------------------------------------------|:------------|:----------------------------|
| EMA 50 y dirección 4H recalculadas solo con velas 4H cerradas (en el retroceso y en la señal) | OK          | 2337 operaciones; fallos: 0 |
| Retroceso válido, vigente (sin otro retroceso ni señal antes) y dentro de las 5 velas         | OK          | 2337 operaciones; fallos: 0 |
| Señal: cierre 1H más allá del máximo/mínimo de la vela anterior                               | OK          | 2337 operaciones; fallos: 0 |
| Entrada: apertura de la vela 1H siguiente a la señal                                          | OK          | 2337 operaciones; fallos: 0 |
| SL: extremo del retroceso ± 0,10 × ATR(14) calculado hasta el cierre de la señal              | OK          | 2337 operaciones; fallos: 0 |
| TP = entrada ± 2R con la entrada real                                                         | OK          | 2337 operaciones; fallos: 0 |
| Truncamiento global (6 cortes en sábado): entradas anteriores idénticas                       | OK          | sin diferencias             |

## Señales (escenario B)

| estado             |    n |
|:-------------------|-----:|
| IGNORED_TRADE_OPEN | 3771 |
| TAKEN              | 2337 |
| ENTRY_BEYOND_STOP  |    2 |

## Fuera de muestra

NO EJECUTADO: el desarrollo no cumple los criterios registrados.
