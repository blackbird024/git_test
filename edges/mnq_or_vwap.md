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
| Filtro de distancia (OFICIAL) | Si `R > 0,45 % × precio de entrada`, se rechaza la operación (y no se busca otra ese día). Estado: `RISK_ABOVE_CAP` |
| Tamaño | Solo con `src/risk/position_sizing.py`: `riesgo = saldo × 0,5 %`; `contratos = floor(riesgo / (R × 2 $))`; si < 1, no se opera y se registra `POSITION_SIZE_BELOW_MINIMUM` |
| Stop y objetivo en la misma vela | Pérdida (motor estándar del proyecto) |

## Parámetros (fijos en v1.0; no se optimizan)
Rango de 15 min, objetivo 2R, salida a las 15:55, tope de riesgo del **0,45 % del precio**, riesgo del 0,5 %.

## Variantes del tope (decisión del usuario, 29-sep-2026, ANTES de ver resultados)
| Variante | Regla | Papel |
|---|---|---|
| `REL_0.45PCT` | `R ≤ 0,0045 × precio de entrada` | **OFICIAL** (la que se evalúa) |
| `FIXED_40PTS` | `R ≤ 40 puntos` | Control (la regla original, no estacionaria) |
| `NO_CAP` | sin tope | Control (qué hace el filtro) |

Precisión de implementación (documentada antes de ejecutar): la especificación habla del "OR_range respecto al precio
de referencia". El código compara **R = |entrada real − stop|** con **0,45 % del precio de entrada real** (con
deslizamiento). Como el stop es el extremo opuesto del rango, R = ancho del rango + distancia de la entrada al borde
roto, así que R ≥ ancho del rango: el filtro es algo más estricto que "ancho del rango ≤ 0,45 %". Los controles no se
usan para elegir la variante: la oficial ya está fijada.

## Costes (tres escenarios, fijados antes de ejecutar)
| Escenario | Deslizamiento (entrada, stop, salida por tiempo) | Comisión |
|---|---|---|
| 0 | 0 | 0 |
| 1 (referencia) | 1 tick (0,25 pt = 0,50 $/contrato) por lado | 1 $ por contrato y lado |
| 2 (estrés) | 2 ticks por lado | 1 $ por contrato y lado |
El objetivo es una orden límite: **nunca** lleva deslizamiento. No se duplican ticks en la apertura de Nueva York
(la entrada más temprana es a las 09:46, fuera de la ventana de apertura del motor).

## Periodo
- Desarrollo: sesiones del **1-ene-2015 al 21-mar-2023** (`config/particion.json`). Los datos se cortan antes de
  cargarse en la estrategia: ninguna vela posterior al 21-mar-2023 entra en el cálculo.
- Fuera de muestra: desde el 22-mar-2023, **bloqueado**. Etiqueta obligatoria: **"OOS / PREVIOUSLY EXPLORED FAMILY"**
  (el periodo ya se vio con otras ORB de NQ; para esta familia no es un fuera de muestra virgen).
- Se excluyen las sesiones ilíquidas previsibles (regla causal del proyecto) y los fines de semana.

## Problema conocido ANTES de ejecutar: el tope de 40 puntos (RESUELTO: opción b, 0,45 %)
El ancho del rango depende del nivel de precio (NQ pasó de ~4.400 a ~30.500 puntos). Ancho mediano del rango de 15 min
en desarrollo: 15-18 puntos en 2015-2017, 58-97 puntos en 2020-2022. Con 40 puntos fijos, el filtro deja pasar el 96-98 %
de los días en 2015-2017 y solo el 2-21 % en 2020-2023. En consecuencia:
- la muestra de desarrollo estaría dominada por 2015-2019;
- en el fuera de muestra (NQ a 12.000-30.000) habría muy pocas operaciones y no se podría evaluar.
**Decisión del usuario (29-sep-2026, antes de ejecutar):** opción (b), tope relativo del **0,45 %** del precio como
regla oficial; 40 puntos y sin tope se mantienen solo como controles.

## Criterios de evaluación (fijados antes de ejecutar)
- Muestra: con **menos de 100 operaciones** en el total se marca `INSUFFICIENT_SAMPLE`; en un desglose (año, hora,
  dirección, tamaño del rango), los grupos con **menos de 30** operaciones se marcan igual y no se interpretan.
- t ≥ 2 es condición **necesaria, no suficiente**: el proyecto ha probado muchas hipótesis (pruebas múltiples).

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

## Apex EOD (para la fase de simulación; NO interviene en este backtest)
Conocido (texto de reglas facilitado por el usuario, `archive/config/firms/apex_eod.yaml`): cuenta 50K con objetivo de
3.000 $, drawdown EOD de 2.000 $ (umbral = máx(umbral, saldo al cierre − 2.000)), límite de pérdida diaria de 1.000 $,
máximo 6 contratos, 30 días. Automatización y cobertura prohibidas: el sistema solo genera alertas
(`execution_enabled = False` siempre).
**UNKNOWN (no se inventan):** equivalencia contratos mini/micro, si el umbral deja de subir, si tocar el límite diario
suspende solo el día o la cuenta, hora exacta del cálculo EOD, tratamiento de la pérdida abierta en el límite diario.
Con cualquier UNKNOWN relevante sin resolver, el gestor de riesgo bloquea (`APEX_STATE_UNKNOWN` → NO TRADE).
Gestor futuro: margen de seguridad del 20 % (`usable = restante × 0,80`, para drawdown y límite diario; se aplica el
más restrictivo, contando la pérdida abierta).

## Registro de decisiones
- 29-sep-2026: ficha registrada (commit 33eee70) y código con pruebas (0009bc5) antes de ejecutar.
- 29-sep-2026: tope oficial 0,45 %; controles 40 pts y sin tope; escenarios de costes 0/1/2; umbral
  `INSUFFICIENT_SAMPLE`; etiqueta del OOS. Todo antes del primer backtest.

## Resultado del desarrollo (2015-01-01 → 2023-03-21) — añadido tras ejecutar
Informe completo: `reports/OR_VWAP_v1.0/`. Auditoría de look-ahead: OK.

| Variante oficial REL_0.45PCT | Esc. 0 (sin costes) | Esc. 1 (1 tick + 1 $) | Esc. 2 (2 ticks + 1 $) |
|---|---|---|---|
| Operaciones | 1.008 | 999 | 980 |
| Profit factor | 1,078 | 0,905 | 0,830 |
| R medio (t) | +0,040 (1,05) | −0,037 (−0,97) | −0,076 (−1,97) |
| Neto (50.000 $, 0,5 %) | +9.170 $ | −9.404 $ | −15.425 $ |
| Drawdown máximo | −15,5 % | −33,8 % | −39,7 % |

- **No cumple el criterio registrado** (PF > 1 y t ≥ 2 con costes del escenario 1). Tampoco hay ventaja significativa
  antes de costes (t = 1,05). Los controles (40 puntos, sin tope) dan lo mismo: sin ventaja tras costes.
- El tope del 0,45 % tampoco es estacionario: rechaza el 94 % de los días de 2022 (15 operaciones) y el 75 % de los de
  2020, porque depende de la volatilidad.
- Largos +0,056 R (t 1,06) y cortos −0,140 R (t −2,52): observación POSTERIOR a los datos; no se usa para cambiar la
  versión (sería minería de datos).
- **Veredicto: v1.0 no supera el desarrollo.** El fuera de muestra sigue sin tocarse. Cualquier cambio sería una
  v1.1 con ficha propia, y el usuario decide si se hace.
