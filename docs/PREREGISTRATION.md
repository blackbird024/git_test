# Pre-registro: CRT XAUUSD 4H + 15M

Versión vigente: **2.0.0** (ver `CONFIG.json`). Cualquier cambio en las reglas obliga a subir la versión y a
dejar constancia aquí **antes** de ejecutar.

## Historial

| Versión | Fecha | Cambio | ¿Se habían visto resultados? |
|---|---|---|---|
| 1.0.0 | 2026-09-30 | Borrador: sweep → FVG contrario → ruptura IFVG por cuerpo → volumen (A/B) → TP A-E. | **No** (no existe dataset). |
| 2.0.0 | 2026-09-30 | El propietario sustituye la confirmación: **la vela inmediatamente posterior al sweep** debe ser un engulfing de cuerpo + volumen ≥ 1.5×SMA20 previa; se eliminan FVG/IFVG; RR fijo 1:1. | **No.** |

## Hipótesis (única)

> Una 4H establece un rango. En la 4H siguiente, la primera vela 15M que penetra estrictamente un extremo
> es el sweep. La vela 15M **inmediatamente siguiente** es un engulfing de cuerpo en dirección contraria
> con volumen ≥ 1.5 × media de las 20 velas previas. Entrar en el OPEN de la vela posterior, con SL detrás
> del extremo y TP = 1R, tiene expectativa positiva después de costes.

## Reglas exactas

**Tiempo.** Zona horaria canónica: `America/New_York` (IANA, con DST). Barras indexadas por su apertura, en UTC. Una barra
15M solo se usa una vez cerrada (ts + 15 min). Las 4H se construyen sobre el reloj de pared de NY, ancladas a las 17:00.

**Setups.**
- London KZ 02:00-05:00 NY → 4H de ejecución 01-05, referencia 21-01.
- NY KZ 07:00-10:00 NY → 4H de ejecución 05-09 (tramo KZ 07-09, referencia 01-05) y 09-13 (tramo KZ 09-10, referencia 05-09).

**Sweep.** LONG: la **primera** barra de la 4H de ejecución con `Low < Low_ref` (estricto). SHORT: la primera con
`High > High_ref`. Tocar el nivel no cuenta.

**Confirmación** (la barra j = sweep + 1, sin excepción):
- LONG: `C_s < O_s`, `C_c > O_c`, `O_c <= C_s`, `C_c >= O_s`
- SHORT: `C_s > O_s`, `C_c < O_c`, `O_c >= C_s`, `C_c <= O_s`
- Volumen: `V_c >= 1.5 × mean(V[j-20 .. j-1])`. La barra actual queda excluida.
- j debe estar dentro de la Kill Zone y dentro de la 4H de ejecución.
- Si falla cualquier condición, **esa dirección del setup queda invalidada.** No hay otra oportunidad.

Nota: el mensaje del propietario dice "cerrar por encima del Open de la vela del sweep", y su "definición exacta" dice
`Close_c >= Open_s`. Se aplica la definición exacta (≥). La igualdad a 2 decimales es rarísima.

**Entrada.** OPEN de la barra j + 1.

**SL.** LONG: `min(Low_s, Low_c) − 0.50`; SHORT: `max(High_s, High_c) + 0.50`. Ambas barras están cerradas antes de la
entrada. En el ejemplo del propietario, esto da 2648.5 − 0.50.

**TP.** `Entry ± 1 × Risk`.

**Salida.** SL o TP. Si ambos caen en la misma barra 15M, se asume **SL**. Un gap a través del SL se llena en el OPEN;
un gap a través del TP se llena en el TP. Si no se toca ninguno, cierre forzado al CLOSE de la última barra que
cierra antes o a las 17:00 NY (sin rollover y sin fin de semana).

**Costes.** `mult × (spread + comisión) + 2 × slippage por lado`, restados en precio. R = PnL neto / riesgo.

## Casos ambiguos: reglas fijas

| Caso | Regla |
|---|---|
| Sweep de ambos extremos | Direcciones independientes; gana la señal válida más temprana. Se marca `other_direction_also_signalled`. Nunca pueden confirmar en la misma barra (una vela no puede ser alcista y bajista a la vez). |
| Varios sweeps | Solo cuenta el **primero** de cada dirección en la 4H de ejecución. Los siguientes se ignoran. |
| Sweep antes de la KZ | Válido solo si la confirmación (sweep + 1) cae dentro de la KZ, es decir, un sweep en la barra inmediatamente anterior al inicio. En otro caso la dirección muere (`confirm_bar_outside_kill_zone`). |
| Sweep dentro de la KZ y confirmación fuera | Inválido. |
| Confirmación fuera de la 4H de ejecución (p. ej. sweep 08:45 y confirmación 09:00) | Inválido (`confirm_bar_outside_exec_4h`). |
| Sweep y confirmación en la misma vela | Imposible por definición: la confirmación es siempre la vela siguiente. |
| Vela de confirmación que vuelve a barrer el nivel | Permitido; el SL usa el extremo de las dos velas. |
| Vela de sweep doji (`C = O`) | No es bajista ni alcista, así que la dirección queda invalidada. |
| Gap o barra faltante entre el inicio de la 4H y la confirmación | Inválido (`data_gap_before_sweep` / `confirm_bar_missing_gap`). |
| Falta la barra de entrada (gap) | Operación omitida (`entry_bar_missing_gap`). |
| 4H de referencia incompleta o con huecos | Setup omitido. |
| Vela anormal (rango > 10 × mediana de las 96 barras previas) en el sweep o en la confirmación | Rechazado (`abnormal_bar`), contado. |
| Spread extremo (> 3 × mediana de las 96 barras previas; solo si el dataset trae spread) | Rechazado (`extreme_spread`). |
| Rollover y pausa diaria | Ninguna KZ lo toca; salida forzada antes de las 17:00 NY. |
| Entrada al otro lado del SL (gap) | Operación omitida (`entry_beyond_stop`). |
| Posición ya abierta en la misma KZ | Operación omitida (no stacking, sin reentrada). |
| London y NY solapadas | Setups independientes; se marca `overlaps_other_kz_trade`. |
| Timestamp ambiguo o inexistente por DST | Se descarta y se cuenta. |

Todas las señales rechazadas quedan en `reports/CRT_XAUUSD_SIGNAL_LOG.csv` con su motivo.

## Datos y separación

TRAIN 60 %, VALIDATION 20 % y TEST 20 % por tiempo, con los cortes ajustados al inicio de mes. Las fechas exactas se
imprimen en el informe. **TEST está bloqueado** y no se calcula salvo con `--unlock-test`. El primer desbloqueo queda
registrado en `reports/TEST_UNLOCK.json` con el hash de la configuración; si más tarde se desbloquea con otra configuración, el informe
avisa de que TEST ya no es un hold-out limpio.

## Contabilidad de pruebas múltiples

| Tipo | Número | Tratamiento |
|---|---|---|
| Hipótesis confirmatorias | 1 regla × 3 grupos (LONDON, NY, LONDON+NY; no independientes) | Holm sobre 3, α = 0.05 |
| Sensibilidad (no son hipótesis, **no se pueden seleccionar**) | costes 3 + slippage 4 + retraso 2 + TP 4 + volumen 6 = 19 niveles × 3 grupos = 57 filas | descriptivas |
| Nulls de falsificación | 5 × 3 grupos | p por permutación, α = 0.05 |
| Tablas de régimen | descriptivas | nunca se convierten en filtros |

## Criterios de éxito (todos a la vez para ROBUST EDGE)

≥ 150 trades en TRAIN+VALIDATION · expectativa > 0 en TRAIN **y** en VALIDATION (netas) · Holm significativo ·
expectativa > 0 con 2× costes · ≥ 60 % de ventanas walk-forward OOS positivas · ≥ 60 % de años positivos ·
vecinos (volumen 1.3 y 1.7, TP 1.5R, entrada +1 vela) positivos · expectativa > 0 quitando el 5 % de mejores trades ·
batir los 5 nulls (dirección aleatoria, tiempo aleatorio, entrada aleatoria, permutación de volumen, niveles de
sweep aleatorios) · TEST > 0 con ≥ 30 trades · coherencia económica (argumento escrito).

**PROMISING BUT INSUFFICIENT** exige como mínimo: suficientes trades, TRAIN > 0, VALIDATION > 0, 2× costes > 0, Holm
significativo y batir al menos 3 de 5 nulls. (Durante el desarrollo, un random walk puro superaba un criterio más laxo
de "TRAIN>0, VAL>0, 2×>0", así que ese criterio se descartó como insuficiente.)

En cualquier otro caso: **NO ROBUST EDGE.**

## Prohibido

Grid search; seleccionar variantes de sensibilidad; mirar TEST antes de congelar; filtros derivados de ganadores; cambiar
horarios o definiciones después de ver resultados. Cualquier mejora observada se anota como **POST-HOC OBSERVATION** y no
entra en el sistema principal.

## v2.1.0: fuente de datos (registrada antes de ver ningún dato)

| Versión | Fecha | Cambio | ¿Se habían visto resultados? |
|---|---|---|---|
| 2.1.0 | 2026-09-30 | Dataset: **Databento GLBX.MDP3, futuros de oro de CME `GC.v.0`** (contrato continuo por volumen, sin ajustar), 1M agregado a 15M, 2010-06-06 → 2026-09-29. No hay XAUUSD spot con volumen accesible. Rollover: se omite el setup si la 4H de referencia o la de ejecución abarcan más de un contrato o son contratos distintos; se omite el trade si el contrato cambia entre la confirmación y la salida. Los costes provisionales no cambian. | **No** |

Consecuencias que asumo: (1) es GC, no spot. El precio difiere por la base (contango), pero la geometría
intradía es prácticamente la misma. (2) El volumen es **volumen real negociado en CME**, no tick volume.
(3) El horario es igual al del CFD: domingo 18:00 a viernes 17:00 NY, con pausa de 17:00 a 18:00.
