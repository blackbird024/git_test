# Fase 1 — Auditoría del código y de la metodología (30-sep-2026)

Revisión línea a línea del motor, los datos y cada estrategia, más comprobaciones empíricas (`auditoria/src/validadas.py`,
resultados en el informe final). **No se ha modificado ningún archivo original.** Gravedad: CRÍTICO (invalida
resultados) / ALTO (puede cambiar la conclusión) / MEDIO (sesgo acotado) / BAJO (documentar).

## Datos (NQ y GC, Databento GLBX.MDP3, 1 min, 2015-01 → 2026-09)
| Comprobación | Resultado |
|---|---|
| Duplicados, velas imposibles (H<L, O/C fuera de rango) | 0 y 0 (NQ); `limpiar` las quitaría si existieran |
| Zona horaria | UTC en origen; sesiones con `America/New_York` vía zona horaria (cambios de hora de EE. UU./Europa correctos) |
| Huecos > 30 min dentro de sesión | 10 en NQ en 11 años (el mayor 10 h 46 min): se informan, no se rellenan |
| Picos de 1 min que se deshacen | 287 en NQ: **no se eliminan** (pueden ser errores o noticias). Riesgo BAJO: afectan a máximos/mínimos puntuales |
| Sesiones ilíquidas previsibles | 65 excluidas con regla **causal** (volumen de la sesión anterior; `calidad.dias_iliquidos`) |
| Contrato continuo | `NQ.v.0`/`GC.v.0` por volumen, sin ajustar. **Supuesto no verificado:** que Databento decida el cambio con volumen ya conocido. MEDIO |
| Velas incompletas | La zona de ruido exige datos del minuto de decisión (`isnan`); días de cierre anticipado se cierran con la última vela disponible |

## Motor común (`src/engine`)
| Punto | Estado |
|---|---|
| Ejecución | Siempre en la apertura de la vela SIGUIENTE a la de la señal (`ejecucion.indice_entrada`) |
| Stop y objetivo en la misma vela | Se cuenta pérdida (conservador) |
| Huecos | Si la vela abre más allá del stop, se ejecuta en la apertura (peor que el stop) |
| Costes | Comisión por contrato y lado + deslizamiento en ticks; 2 ticks en aperturas de sesión (Londres, NY, Globex) |
| Look-ahead | Prueba de truncamiento (`engine/lookahead.comprobar`) + `tests/test_lookahead*.py`, `test_misma_vela.py`: 104 pruebas pasan |

## Zona de ruido (`src/strategies/zona_ruido.py`)
| Punto | Estado | Gravedad |
|---|---|---|
| Sigma con los 14 días ANTERIORES (`rolling(...).shift()`) | Correcto | — |
| Decisión con el cierre del minuto anterior al chequeo, ejecución en la apertura del minuto del chequeo | Correcto (comprobado: 0 entradas fuera de chequeo) | — |
| Una posición a la vez, sin duplicados por señal persistente | Correcto (0 solapes) | — |
| neto = bruto − comisión en todas las operaciones | Correcto | — |
| **Sin stop entre chequeos** (30 min): la pérdida de una operación no está acotada por un stop; no existe "R" | Riesgo de ejecución real (noticias). Se informa la peor operación | ALTO para gestión del riesgo |
| Comisión 1 $/lado (MNQ real ≈ 0,6–0,9 $) y 1 tick por lado | Algo conservador | BAJO |
| VWAP con volumen del futuro NQ; en el EA se usa volumen de ticks del CFD NAS100 | Backtest y ejecución no son equivalentes | MEDIO |
| **Selección múltiple:** esta versión se eligió entre variantes del estudio original (`archive/reports/estudio_noise_area.md`, incluida una con stop que falló) mirando todo el periodo | El periodo posterior a 2023 **no es fuera de muestra** | ALTO para la interpretación |

## RSI(2) (`src/strategies/nq_rsi2.py`)
| Punto | Estado | Gravedad |
|---|---|---|
| Señal al cierre de la sesión; entrada en la apertura siguiente (Globex 18:00 NY) | Correcto (0 entradas antes de la señal) | — |
| Salida en la apertura tras el cierre con RSI > 70 o tras 5 sesiones | Correcto | — |
| Cierres ajustados por cambio de contrato solo con el pasado | Correcto; el día del cambio se pierde el hueco nocturno real (aproximación causal) | BAJO |
| Sin stop: la pérdida de una operación depende de la caída en 5 sesiones (incluye huecos de fin de semana) | Riesgo de cola | ALTO para gestión del riesgo |
| Su "R" = rendimiento / volatilidad de 20 sesiones (no un R por stop) | Se informa en $ para comparar | BAJO |
| **Selección múltiple:** fue 1 de 3 ventajas del paso 1; en el paso 2 se probaron 3 mejoras (se descartaron); el paso 3 miró el periodo posterior | El periodo posterior **no es fuera de muestra** | ALTO para la interpretación |
| Muestra pequeña (~13 operaciones/año) | IC amplios | ALTO |

## Estrategias rechazadas
| Estrategia | Revisión | Errores de código detectados |
|---|---|---|
| SMC/ICT kill zones | Reglas de la ficha implementadas; 7 pruebas (`test_smc.py`) | Ninguno. Muestra ínfima (8–17 operaciones) por reglas muy estrictas: diseño, no error |
| Rango 30 min + London + VWAP | Cierre de 5 min por minuto `:x4/:x9`; auditoría de look-ahead OK | Ninguno. BAJO: si falta un minuto, ese cierre de 5 min no se evalúa |
| Cruce VWAP 15m 1:2 | Stop en la vela de señal; look-ahead OK | Ninguno. Stops muy cortos → costes grandes en R: diseño |
| VWAP direccional (subproyecto) | Error de separación de sesiones **encontrado y corregido antes de obtener resultados** (24 pruebas) | Ninguno pendiente |
| VWAP + EMAs A–D (subproyecto) | Error de índice de entrada (entraba en la apertura de la vela de señal) **encontrado y corregido antes de obtener resultados** (16 pruebas) | Ninguno pendiente. Velas de 15 min: stop y objetivo en la misma vela = stop (pesimista) |
| Zona de ruido / RSI(2) en oro | Mismo código que en NQ con especificaciones de MGC | Ninguno. Supuesto discutible: sesión de NY 09:30–16:00 para el oro (la ficha lo fijó así) |
| Pares oro/plata | Velas diarias por día UTC; entrada en la apertura de las 00:00 UTC | Ninguno. MEDIO: liquidez a medianoche UTC (costes quizá infravalorados) |
| Bot oferta/demanda | Funciones de señal copiadas literalmente del bot | Ninguno en la copia. Datos: futuro GC ajustado, no el CFD XAUUSD; sin swap. Su afirmación "PF ~1,44 en 22 años" **no es verificable** (no hay `bot_fixed.py` ni sus datos) |

## Riesgos metodológicos transversales
1. **No queda test intocable** en ninguna estrategia (ver `CRITERIOS.md`). Único dato nuevo: prueba hacia delante.
2. **Selección múltiple del proyecto:** unas 25+ ideas probadas en NQ/oro; que 2 de ellas pasen umbrales t ≈ 2 es
   compatible con el azar. Esto rebaja la confianza en las dos validadas aunque sus reglas no se hayan re-ajustado.
3. Backtests en **futuros**; la ejecución prevista es en **CFD NAS100** (precio, VWAP, spread y swap distintos).
