# OR_VWAP_v1.0 (MNQ): backtest de DESARROLLO

- **Periodo:** sesiones del 1-ene-2015 al 21-mar-2023. El fuera de muestra no se ha cargado ni ejecutado.
- **Reglas:** `edges/mnq_or_vwap.md`, registradas antes de ejecutar en los commits 33eee70 y 013b27b.
- **Código:** `src/strategies/mnq_or_vwap.py`. Para repetirlo: `python -m src.report.or_vwap`.
- **Cuenta simulada:** 50.000 $, riesgo del 0,5 % del saldo por operación, 1 operación al día como máximo.
- **Salida de 15:55 NY:** son las 21:55 en Italia casi todo el año.

**Veredicto de desarrollo:** con la regla oficial (tope 0,45 %) y costes realistas (1 tick + 1 $), la estrategia **pierde dinero** (PF 0,905, R medio −0,037, t −0,97). **No cumple** el criterio registrado antes de ejecutar (PF > 1 y t ≥ 2). Antes de costes tampoco muestra una ventaja estadística: PF 1,078 y t 1,05.

## Archivos

| Archivo | Contenido |
|---|---|
| `summary.csv` | Todas las métricas de las 9 combinaciones (3 variantes × 3 escenarios) y el estado de cada día |
| `trades.csv` | Todas las operaciones de las 9 combinaciones (horas en UTC, NY y Roma) |
| `yearly.csv` | Métricas por año, más los días operados y los días rechazados por tope o por tamaño |
| `hourly.csv` | Métricas por hora de entrada en NY. En Italia suele ser +6 h |
| `long_short.csv` | Largos frente a cortos |
| `range_analysis.csv` | Métricas según el ancho del rango de apertura, en % del precio |
| `robustness.csv` | Resultado sin la mejor operación, sin las 5 mejores, sin el mejor año y sin el mejor mes; largos y cortos; rachas (clustering); deterioro por costes |
| `diagnostics.md` | Auditoría de look-ahead, estados por día y distribución de R |

## Tabla comparativa

Esta tabla no declara ganador: la variante oficial se fijó antes de ejecutar.

| Variante | Esc. | Oper. | Acierto | PF | Neto $ | Expect. $ | Expect. R | t | Máx. DD $ (% saldo) |
|---|---|---|---|---|---|---|---|---|---|
| **REL_0.45PCT (oficial)** | 0 | 1.008 | 41,5 % | 1,078 | +9.170 | +9,10 | +0,040 | 1,05 | −7.889 (15,5 %) |
| **REL_0.45PCT (oficial)** | **1** | **999** | **39,7 %** | **0,905** | **−9.404** | **−9,41** | **−0,037** | **−0,97** | **−17.038 (33,8 %)** |
| **REL_0.45PCT (oficial)** | 2 | 980 | 39,0 % | 0,830 | −15.425 | −15,74 | −0,076 | −1,97 | −20.048 (39,7 %) |
| FIXED_40PTS | 0 | 1.151 | 40,2 % | 1,001 | +190 | +0,17 | +0,001 | 0,03 | −9.647 (18,6 %) |
| FIXED_40PTS | 1 | 1.150 | 38,5 % | 0,854 | −16.222 | −14,11 | −0,077 | −2,21 | −20.376 (39,3 %) |
| FIXED_40PTS | 2 | 1.148 | 38,1 % | 0,790 | −21.834 | −19,02 | −0,105 | −3,04 | −24.228 (46,7 %) |
| NO_CAP | 0 | 2.011 | 41,9 % | 1,090 | +19.480 | +9,69 | +0,038 | 1,43 | −10.782 (20,8 %) |
| NO_CAP | 1 | 1.766 | 40,5 % | 0,944 | −8.350 | −4,73 | −0,019 | −0,65 | −21.323 (41,1 %) |
| NO_CAP | 2 | 1.617 | 40,0 % | 0,877 | −15.788 | −9,76 | −0,047 | −1,58 | −24.804 (47,8 %) |

Escenarios de costes:
- **0:** sin costes.
- **1:** 1 tick de deslizamiento en la entrada, el stop y la salida por tiempo, más 1 $ por contrato y lado.
- **2:** igual que el 1, pero con 2 ticks.

El objetivo es una orden límite y nunca lleva deslizamiento.

## Variante oficial, escenario 1: detalle

| Métrica | Valor |
|---|---|
| Operaciones (ganadoras / perdedoras / a cero) | 999 (397 / 596 / 6) |
| Beneficio bruto / pérdida bruta / neto | +89.874 $ / −99.278 $ / −9.404 $ |
| Ganancia media / pérdida media / ratio (payoff) | +226 $ (+1,33 R) / −167 $ (−0,95 R) / 1,36 |
| R mediano / desviación típica de R | −0,725 / 1,216 |
| Salidas | Stop 48,6 %, tiempo 28,9 %, objetivo 19,6 % (y 28 salidas en festivos, ver problemas) |
| Racha máxima de pérdidas / de ganancias | 12 / 12 |
| Riesgo medio / riesgo máximo por operación | 173 $ / 252 $ |
| Contratos medios / máximos | 5,3 / 49 MNQ |
| Mayor ganancia / mayor pérdida | +476 $ / −368 $ (1,47 veces el riesgo previsto, por hueco y deslizamiento) |
| Saldo final | 40.596 $ (empezando en 50.000 $) |
| Muestra | OK (≥ 100 operaciones) |

- El riesgo medio queda por debajo de los 250 $: el número de contratos se redondea hacia abajo y el saldo baja con las pérdidas.

**Por año (esc. 1):**

| Año | Oper. | Neto $ | PF | R medio | Días rechazados por el tope 0,45 % |
|---|---|---|---|---|---|
| 2015 | 139 | −3.760 | 0,81 | −0,117 | 113 |
| 2016 | 164 | −5.900 | 0,72 | −0,168 | 89 |
| 2017 | 221 | −6.205 | 0,71 | −0,160 | 31 |
| 2018 | 112 | +2.574 | 1,28 | +0,139 | 143 |
| 2019 | 157 | +164 | 1,01 | +0,011 | 94 |
| 2020 | 62 | −282 | 0,95 | −0,010 | 190 |
| 2021 | 120 | +3.387 | 1,48 | +0,185 | 132 |
| 2022 | 15 ⚠️ | +253 | 1,20 | +0,126 | 238 |
| 2023 (hasta el 21-mar) | 9 ⚠️ | +364 | 1,49 | +0,126 | 46 |

⚠️ `INSUFFICIENT_SAMPLE` (menos de 30 operaciones): no se interpreta.

**Por dirección (esc. 1):**

| Dirección | Oper. | Neto $ | PF | R medio | t |
|---|---|---|---|---|---|
| Largos | 523 | +3.166 | 1,07 | +0,056 | 1,06 |
| Cortos | 476 | −12.570 | 0,76 | −0,140 | −2,52 |

## Auditoría de look-ahead

Todo OK (detalle en `diagnostics.md`). Se revisaron las 999 operaciones una a una:
- El OR sale solo de las velas de 09:30 a 09:44.
- La señal y el VWAP, recalculados con los datos cortados justo en la vela de la señal, son idénticos.
- La entrada es la apertura de la vela siguiente.
- El stop y el objetivo se fijan en la entrada.
- La salida se produce en la primera vela que toca el stop o el objetivo (si los toca los dos en la misma vela, cuenta como pérdida).
- El tamaño se calcula con `position_sizing` y el saldo anterior a la operación.
- Truncamiento global: 6 cortes en sábados entre 2016 y 2022, sin diferencias.
- Ninguna vela del fuera de muestra entra en el cálculo.
- Estado de Apex: no aplica en esta fase.

**Aviso (no es look-ahead):** 28 operaciones cayeron en festivos de EE. UU., cuando CME cierra a las 13:00 NY. Salieron en la última vela de la sesión, porque las reglas no prevén ese caso. Si se quitan, el resultado apenas cambia: R medio −0,043 en lugar de −0,037.
