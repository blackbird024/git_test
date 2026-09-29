# Diagnóstico: GOLD_SWING_SIMPLE_v1.0 (desarrollo)

## Auditoría de look-ahead

| punto                                                                                | resultado                       | detalle                                                                                                            |
|:-------------------------------------------------------------------------------------|:--------------------------------|:-------------------------------------------------------------------------------------------------------------------|
| Datos: nada del fuera de muestra                                                     | OK                              | última vela 2023-03-21 20:59:00+00:00 (corte: sesión 2023-03-22)                                                   |
| Swing 1H confirmado (cierre de i+2) antes de empezar la vela del barrido             | OK                              | 41 operaciones; fallos: 0                                                                                          |
| Dirección 4H recalculada solo con velas 4H cerradas al cierre del barrido = la usada | OK                              | 41 operaciones; fallos: 0                                                                                          |
| Barrido recalculado con datos cortados en la vela del barrido = el usado             | OK                              | 41 operaciones; fallos: 0                                                                                          |
| Orden temporal: barrido < confirmación < FVG <= entrada en 15m                       | OK                              | 41 operaciones; fallos: 0                                                                                          |
| FVG con las velas 1H b, b+1 y b+2 ya cerradas                                        | OK                              | 41 operaciones; fallos: 0                                                                                          |
| Stop con la vela del barrido y el ATR(14) calculado solo hasta ese cierre            | OK                              | 41 operaciones; fallos: 0                                                                                          |
| Truncamiento global (6 cortes en sábado): entradas anteriores idénticas              | OK                              | sin diferencias                                                                                                    |
| Entrada 15m                                                                          | OK (por construcción y pruebas) | orden activa desde el cierre de la vela 3; solo velas de 15m que empiezan después; tests/test_gold_swing_simple.py |

## Destino de todos los barridos 1H (escenario B)

| estado            |    n |
|:------------------|-----:|
| NOT_ALIGNED       | 2043 |
| NO_CONFIRMATION   |  689 |
| NO_FVG            |  113 |
| ENTERED           |   41 |
| CANCEL_NEW_SWEEP  |   29 |
| TRADE_OPEN        |   18 |
| CANCEL_4H_CHANGED |    6 |
| EXPIRED_24H       |    5 |

## Fuera de muestra

NO EJECUTADO: el desarrollo no cumple los criterios registrados.
