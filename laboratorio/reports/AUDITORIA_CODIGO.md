# Auditoría de código, datos y sesgos

Fecha: 9 de octubre de 2026. Alcance: el código previo del repositorio (`alpaca/`, `orb_mnq/`, `tradingview/`, `mt5/`) y el laboratorio nuevo (`laboratorio/`). No he modificado ningún archivo previo.

## 1. Código y resultados previos

| # | Archivo | Problema | Gravedad | Efecto |
|---|---|---|---|---|
| 1 | `alpaca/nq_intraday_research.py`, `alpaca/mezcla_filtros.py` | `build_days` rompía la cadena de días cuando un día no tenía sesión regular, lo que **excluía todos los lunes**. | Alta | Ya corregido en esta conversación (commit anterior al laboratorio) y resultados recalculados. Cualquier cifra anterior a la corrección de esos scripts no es válida. |
| 2 | `alpaca/swing_lab.py`, `alpaca/strategy_lab.py` | Usan velas diarias de Alpaca **sin ajustar** (la opción por defecto de alpaca-py es RAW): se ignoran los dividendos. | Media | Infravalora el benchmark de comprar y mantener (~0,6 %/año en QQQ) y cualquier estrategia larga. El laboratorio usa precios ajustados. |
| 3 | `alpaca/swing_lab.py` | La señal del cierre se ejecuta **en ese mismo cierre**. | Media | Optimista si no se puede operar en la subasta de cierre. Un ETF UCITS europeo **no cotiza** a la hora del cierre de EE. UU. El laboratorio usa la apertura siguiente como ejecución principal. |
| 4 | `alpaca/mnq_intraday_lab.py` (zona de ruido) | Coste fijo de 1 punto (2 $) ida y vuelta, incluidos comisión y deslizamiento; salida exacta al cierre de las 16:00. | Baja | Algo optimista. Con el coste base del laboratorio (≈ 3,5 $ i/v) y salida a las 15:55, el PF baja de 1,33 a ~1,25 fuera de muestra. |
| 5 | `alpaca/mnq_intraday_lab.py` | Sin stop-loss en la zona de ruido. | Media (operativa) | El riesgo por operación no está acotado; en Topstep el flotante puede tocar el MLL. Modelado con la MAE en `run_topstep.py`. |
| 6 | Todos los scripts intradía previos | Contrato continuo `NQ.c.0`, que cambia el domingo **después** del vencimiento. | Media | Unas 20 sesiones al año con el contrato que vence (~24 % del volumen). En el laboratorio, fuera de muestra, esas semanas rinden peor en todas las estrategias. |
| 7 | Toda la investigación de ORB de esta conversación (≈ 40 scripts) | **Sesgo de selección**: se probaron decenas de variantes de ORB sobre los mismos datos de 2018-2026 y se eligieron las mejores ("la vela habla", salida por EMA50, etc.). | Alta | Las cifras de esas variantes (p. ej. +2.215/+2.477 $/año) **no son estimaciones fuera de muestra**. El laboratorio solo evalúa reglas fijadas de antemano y sus vecinos. |
| 8 | `alpaca/orb5_retesteo.py` | La especificación difiere de la definitiva (sin tolerancia de 2 ticks, sin confirmación con cierre, sin SL en la vela de retesteo, sin salida a las 11:30 ni 2R). | Baja | Reimplementado según tu especificación en `strategies/orb.py`: resultado también negativo. |
| 9 | Cifras citadas en el prompt | "Ruido PF 1,19–1,20": en este repositorio el PF de 1,19 es de **EMA 9/21 + CHOP**, no de la zona de ruido (PF 1,33). "RSI(2) PF 1,46/1,93" no aparece en el repositorio. | Media | Posible confusión de etiquetas o resultados del Acer. Hay que comprobarlo allí antes de citarlas. |
| 10 | `mt5/README.md` (IbsSwing: "+14 % anual, caída −9,7 %") | No auditado en esta tarea. Viene de `swing_lab.py`, así que hereda los problemas 2 y 3, y además se seleccionó como "la mejor" entre 12 estrategias. | Media | Tratarlo como hipótesis, no como resultado. |
| 11 | `auditoria/experimentos/20260930_0633/` | **No existe** en el repositorio ni en el historial git. | — | No se pudo revisar. |

## 2. Supuestos del laboratorio que pueden sesgar resultados

- **Ejecución:**
  - Velas de 1 minuto construidas con operaciones; sin bid/ask. Un minuto sin operaciones no genera vela.
  - El deslizamiento es un parámetro (1–3 ticks; robustez probada hasta +4).
- **Orden stop de entrada (ORB inmediato):**
  - Si en la vela de entrada también se toca el stop-loss, se supone el stop después (conservador). En esa vela no se concede el objetivo.
  - Si se activan las dos órdenes en el mismo minuto, se elige la más cercana a la apertura del minuto. Es una heurística: en realidad podrían llenarse ambas.
- **Continuación de tendencia:** la orden stop pendiente no se cancela si, dentro de la misma vela de 5 min, el precio rompe el mínimo de la vela de retroceso antes de activarse. Esto puede **sobrestimar** el número de entradas; la estrategia ya está rechazada.
- **Filtro de volatilidad:** usa el ATR de la sesión regular (no de 24 h), desplazado un día.
- **Simulación de Topstep:**
  - El flotante se aproxima con la peor excursión adversa (MAE) de cada operación, sin conocer el orden exacto entre operaciones del mismo día.
  - Los intentos empiezan cada día y se solapan: las probabilidades no salen de muestras independientes.
- **Reglas de Topstep:**
  - El MLL de 2.000 $ con trailing al cierre se ha deducido de tu panel.
  - El DLL de 1.000 $, los 50 MNQ máximos, el cierre a las 16:10 ET y la interpretación de la consistencia son **sin verificar**.
- **Costes:** 0,75 $ por lado y contrato de comisión + tasas; **sin verificar**.
- **Swing:**
  - QQQ como proxy de un ETF UCITS: distinto horario, divisa (USD frente a EUR), TER y spread.
  - Fiscalidad simplificada: 26 % sobre cada ganancia, sin compensar pérdidas. El IVAFE no se aplica en el backtest de estrategias, solo en el plan.
- **Plan financiero:** rendimientos log-normales con volatilidad del 22 %; las colas reales del Nasdaq-100 son más gruesas.

## 3. Errores encontrados y corregidos durante el trabajo

| Error | Detección | Corrección |
|---|---|---|
| Test `bars5`: los minutos sintéticos rellenos alteraban el máximo esperado | test | Corregido el test (no el código) |
| `pct_en_1_4_semanas` excluía las salidas por tiempo del día 21 | revisión de resultados | Rango 5–21 sesiones |
| Plan financiero: cobraba comisión aunque la compra fuera 0 € | resultado negativo imposible | Solo se cobra si hay compra |
| Tests de Topstep mal planteados (DLL y MLL interferían) | test | Rehechos con casos que distinguen cada regla |
| Comparación con NaN en un test de no-anticipación | test | `np.allclose(..., equal_nan=True)` |
| Error de sintaxis en `run_clasificacion.py` | ejecución | Corregido el nombre de la columna |

## 4. Errores conocidos sin corregir

1. **Ambigüedad de las dos órdenes stop** en el mismo minuto (ORB inmediato): heurística, no resuelta. Afecta a pocas sesiones; no se ha contado cuántas.
2. **Cancelación de la orden pendiente** en la continuación de tendencia (ver §2). No afecta a la conclusión: la estrategia está rechazada.
3. **El experimento de prueba `20261009_193500_sistema_a`** es una ejecución parcial (una sola variante) y queda como registro; no se usa en ningún informe.
4. **Reglas oficiales de Topstep y comisiones:** pendientes de verificar. Todos los resultados de Topstep son provisionales.

## 5. Lo que no se ha podido hacer

- **Datos 2015-2017:** habría que comprar NQ 1 min a Databento. No se ha descargado nada de pago.
- **Verificar fuentes oficiales:** Topstep, CME, IBKR y justETF están bloqueados desde este entorno.
- **Reproducir los resultados del Acer** (ruido PF 1,19–1,20 y RSI(2) PF 1,46/1,93) y los informes de `auditoria/`: no están aquí.
