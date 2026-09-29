# VWAP_15M_2R_v1.0: cruce del VWAP en velas de 15 min, objetivo 1:2 (MNQ)

*Ficha escrita el 29-sep-2026, ANTES de ejecutar ningún backtest. Idea del usuario: "comprar en el Nasdaq cuando el
precio está por encima del VWAP en 15m y viceversa, buscar un ratio 1:2". Los detalles que el usuario no fijó se
eligen aquí con la opción más estándar y no se cambiarán según el resultado.*

## Reglas exactas
Datos de 1 minuto de NQ en UTC; reglas en **America/New_York** (Italia: +6 h casi todo el año).

| Elemento | Regla |
|---|---|
| VWAP | VWAP de la sesión regular desde las 09:30 NY (precio típico × volumen, acumulado; `vwap_sesion` de `OR_VWAP_v1.0`) |
| Velas | 15 min desde las 09:30 NY (09:30, 09:45, ...), construidas desde 1M; solo velas cerradas |
| Señal LARGO | Una vela de 15 min **cierra por encima del VWAP** y la vela de 15 min anterior cerró **por debajo o igual** (cruce al alza). "Estar por encima" sin cruce no es señal: si no, se entraría en cada vela |
| Señal CORTO | Simétrico: cierre por debajo del VWAP tras un cierre por encima o igual |
| Primera señal posible | Cierre de la vela de 09:45–10:00 (la de 09:30 no tiene vela anterior en la sesión) |
| Última señal | Vela que cierra a las 15:00 NY |
| Entrada | Apertura de la vela de 1M siguiente al cierre de la vela de 15 min, con deslizamiento (motor estándar `ejecutar`) |
| Stop | Largo: **mínimo de la vela de señal**. Corto: **máximo de la vela de señal**. Fijo |
| Objetivo | **2R** desde la entrada real (ratio 1:2) |
| Salida por tiempo | 15:55 NY |
| Posiciones | Una a la vez. Tras cerrar, se puede entrar con la siguiente señal (cruce en una vela posterior a la salida) |
| Tamaño | 1 MNQ fijo (2 $/punto) |
| Costes | Estándar: 1 $ por contrato y lado; 1 tick de deslizamiento (2 en la apertura de NY) |
| Días | Se excluyen fines de semana y sesiones ilíquidas previsibles |

Parámetros (ninguno optimizado): velas de 15 min, 2R, stop en el extremo de la vela de señal.

## Periodo y criterio
Desarrollo: sesiones anteriores al 22-mar-2023. Fuera de muestra sin tocar en este paso.
Pasa si, **después de costes**: profit factor > 1 **y** R medio > 0 con **t ≥ 2**. Si no: rechazada, sin ajustes.

## Sesgos
1. Familia muy probada en el proyecto: `OR_VWAP_v1.0` y `OR_LONDON_VWAP_v1.0` (rupturas con filtro de VWAP) ya se
   rechazaron. Los cruces del VWAP en rango lateral generan muchas señales falsas.
2. Stop en la vela de señal: si la vela es muy pequeña, el stop queda muy cerca y los costes pesan más en R.
3. Velas de 1M: si stop y objetivo caen en la misma vela, pérdida.

## Resultado del desarrollo (sesiones < 22-mar-2023): añadido tras ejecutar
| Variante | Operaciones | Acierto | PF | R medio | t | Neto (1 MNQ) |
|---|---|---|---|---|---|---|
| **OFICIAL (con costes)** | 3.254 | 36,9 % | 1,02 | **−0,087** | **−3,75** | +2.314 $ |
| Sin costes | 3.266 | 38,5 % | 1,12 | +0,035 | 1,52 | +12.390 $ |

**Veredicto: RECHAZADA.** Con costes pierde de forma significativa en R (t −3,75): con un objetivo de 2R hace falta
acertar más del 33 % y lo justo que acierta (37 %) no cubre los costes, que pesan mucho porque el stop (la vela de
15 min) suele ser pequeño. El +2.314 $ en dólares sale de 2020 (+6.756 $); 2015-2019 pierden todos. ~1,6 operaciones
al día. Look-ahead: OK. Fuera de muestra sin tocar. Informe: `reports/VWAP_15M_2R_v1.0/`.
