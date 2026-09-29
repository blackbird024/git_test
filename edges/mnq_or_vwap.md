# MNQ — Opening Range + VWAP (Strategy Version: OR_VWAP_v1.0)

*Ficha escrita el 29-sep-2026, ANTES de ejecutar ningún backtest de esta versión.*

## Hipótesis
En la sesión regular de Nueva York, una ruptura del rango de los primeros 15 minutos, confirmada por el cierre de
una vela de 1 minuto y alineada con el VWAP de la sesión (por encima para largos, por debajo para cortos), tiende a
continuar lo suficiente como para alcanzar 2R antes que el stop estructural (el otro extremo del rango).

## Racional de mercado
- Los primeros 15 minutos concentran la reacción a las noticias de la noche y la apertura del contado: el rango
  resume el "acuerdo inicial" del mercado.
- El VWAP de la sesión es la referencia de precio medio de los grandes participantes; estar por encima indica que
  los compradores del día van ganando (y al revés).
- Una ruptura en la dirección del VWAP indicaría un desequilibrio de órdenes a favor.

## Contexto honesto (conocimiento previo)
En este proyecto ya se probaron varias ORB en NQ (rango de 5/15/30 min, stop en el otro lado o por ATR, 1,5R/2R/tiempo,
filtros de rango): **ninguna tuvo ventaja tras costes** (la mejor: PF 1,10, t 1,28, salida por tiempo). Lo nuevo aquí es
el **filtro del VWAP**, las velas de 1 minuto y el tope de riesgo de 40 puntos. Además, el periodo fuera de muestra de
NQ (desde el 22-mar-2023) **ya se vio** en aquellos estudios de ORB: para esta familia de estrategias no es un fuera de
muestra "virgen". Se informa para que el resultado se interprete con esa cautela.

## Reglas exactas (v1.0)
Datos: velas de 1 minuto de NQ (Databento, contrato continuo), en UTC; reglas en **America/New_York** (el cambio de hora
se gestiona con la zona horaria, sin desfases fijos). Se opera como MNQ: 2 $ por punto, tick 0,25 (0,50 $).

| Elemento | Regla |
|---|---|
| Rango de apertura | Velas que empiezan de 09:30 a 09:44 NY (15 velas). `OR_high` = máximo, `OR_low` = mínimo. Congelados desde las 09:45 |
| Día válido | Las 15 velas del rango presentes (en NQ en sesión regular no faltan minutos); si no, no se opera |
| VWAP | VWAP de la sesión regular: desde la vela de las 09:30 NY. Precio típico (máximo + mínimo + cierre) / 3, ponderado por el volumen de cada vela de 1 minuto; acumulado. En cada vela se usa el VWAP que incluye esa vela (ya cerrada) |
| Señal LARGO | Primera vela que empieza entre las 09:45 y las 15:53 NY con **cierre > OR_high** (estrictamente) y **cierre > VWAP** |
| Señal CORTO | Primera vela del mismo tramo con **cierre < OR_low** y **cierre < VWAP** |
| Si hay ruptura sin VWAP a favor | No es señal; se sigue buscando en las velas siguientes |
| Entrada | Apertura de la vela siguiente a la señal (nunca dentro de la vela), con deslizamiento |
| Operaciones | Máximo 1 al día (la primera señal válida, en cualquier sentido) |
| Stop | LARGO: `OR_low`. CORTO: `OR_high`. Fijo: sin trailing, sin break-even |
| Objetivo | `R = |entrada − stop|` con la entrada real; objetivo = entrada ± **2R** |
| Salida por tiempo | Apertura de la vela de las **15:55 NY** |
| Filtro de distancia | Si `R > 40 puntos`, se rechaza la operación (y no se busca otra ese día) |
| Tamaño | `riesgo = saldo × 0,5 %`; `contratos = floor(riesgo / (R × 2 $))`; si < 1, no hay señal |
| Stop y objetivo en la misma vela | Pérdida (motor estándar del proyecto) |

## Parámetros (fijos en v1.0; no se optimizan)
Rango de 15 min, objetivo 2R, salida a las 15:55, tope de 40 puntos, riesgo del 0,5 %.

## Costes
- Comisión: 1 $ por contrato y lado (valor estándar del proyecto).
- Deslizamiento: **escenario 1 = 1 tick** por entrada y por salida a mercado (stop y tiempo); **escenario 2 = 2 ticks**.
  El objetivo es una orden límite, sin deslizamiento. Se informa también **antes de costes**.

## Periodo
Desarrollo: sesiones del 2-ene-2015 al 21-mar-2023. Fuera de muestra: desde el 22-mar-2023, bloqueado hasta terminar el
desarrollo.

## Problema conocido ANTES de ejecutar: el tope de 40 puntos
El ancho del rango depende del nivel de precio (NQ pasó de ~4.400 a ~30.500 puntos). Ancho mediano del rango de 15 min
en desarrollo: 15-18 puntos en 2015-2017, 58-97 puntos en 2020-2022. Con 40 puntos fijos, el filtro deja pasar el 96-98 %
de los días en 2015-2017 y solo el 2-21 % en 2020-2023. En consecuencia:
- la muestra de desarrollo estaría dominada por 2015-2019;
- en el fuera de muestra (NQ a 12.000-30.000) habría muy pocas operaciones y no se podría evaluar.
**Decisión pendiente del usuario antes de ejecutar** (se documentará aquí la opción elegida):
(a) mantener 40 puntos, sabiendo lo anterior; o (b) crear una v1.0 con un tope relativo definido AHORA (por ejemplo, un
porcentaje del precio equivalente a 40 puntos en el nivel medio del periodo), antes de ver ningún resultado.

## Criterios de evaluación (fijados antes de ejecutar)
No basta con beneficio > 0. Se reporta PF, expectativa, t, drawdown, número de operaciones, estabilidad por año, y
resultado antes y después de costes. Criterio para avanzar tras el desarrollo: después de costes (escenario 1),
**PF > 1 y R medio > 0 con t ≥ 2**, y el diagnóstico A-H sin señales de alarma graves. Si falla: se reporta que falló, sin
cambiar reglas para salvarla (cualquier cambio sería una versión nueva, v1.1, con su propia ficha).

## Posibles fuentes de sesgo
1. Conocimiento previo de la familia ORB en NQ (ver arriba) y fuera de muestra ya visto para esa familia.
2. Tope de 40 puntos no estacionario (ver arriba).
3. Deslizamiento en rupturas: el precio se mueve rápido justo al romper; se prueba con 1 y 2 ticks.
4. Velas de 1 minuto: si se tocan stop y objetivo en la misma vela, pérdida (conservador).
5. Sizing con capitalización: el tamaño depende del saldo, así que el orden de las operaciones afecta al resultado en $;
   por eso se reporta también en R.
