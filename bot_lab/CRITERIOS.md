# Trading Bot Lab — criterios PRE-REGISTRADOS (30-sep-2026, antes de ejecutar ningún backtest del laboratorio)

Este archivo fija las reglas del juego **antes de ver resultados**. Todo cambio posterior se anota al final, en
"Cambios tras ver datos", con fecha y motivo. Lo que no esté aquí no se usa para decidir.

## 1. Datos y partición
- NQ 1 min de Databento (`NQ.v.0`), 2015-01-02 → 2026-09-28. Se excluyen las 65 sesiones ilíquidas (regla causal del proyecto).
- **Partición por sesiones RTH (60/20/20):**

  | Tramo | Periodo | Sesiones |
  |---|---|---|
  | TRAIN | 2015-01-02 → 2022-01-14 | 60 % |
  | VALIDATION | 2022-01-18 → 2024-05-22 | 20 % |
  | TEST | 2024-05-23 → 2026-09-28 | 20 % |

- El **TEST** queda bloqueado. Solo se abre **una vez**, cuando todos los finalistas estén congelados. No se usa para decidir nada; lo que salga se publica.
- **Advertencia obligatoria:** 2015-2026 ya se usó en investigaciones anteriores del proyecto, así que el TEST está reservado *para estas reglas*, pero **no es fuera de muestra puro**. El único dato nuevo es el forward test desde el 30-sep-2026.
- Una operación pertenece al tramo del día (hora de NY) de su **entrada**.

## 2. Ejecución (mismas reglas que el motor existente)
- **Señal:** se calcula con la vela (de 1, 5 o 15 min) **cerrada**.
  - Orden a mercado: se ejecuta en la **apertura del minuto siguiente**.
  - Orden stop (ruptura): se llena cuando el precio la cruza, en el nivel o en la apertura si hay hueco, con deslizamiento.
- **Stop y objetivo en el mismo minuto:** cuenta **STOP**. En el minuto de llenado de una orden stop solo puede saltar el stop.
- **Stop:** el hueco se ejecuta en la apertura. **Objetivo:** orden límite al nivel exacto, sin deslizamiento. **Salida por tiempo:** en la apertura, con deslizamiento.
- **Una posición a la vez por estrategia.**
- **Estrategias intradía:** entradas solo en su ventana y cierre obligatorio a las **15:55 NY**, salvo las de Londres o de la noche, que tienen su propia hora.
- **Indicadores:**
  - Se calculan con precios **ajustados de forma causal** por cambio de contrato (suma acumulada de los saltos pasados). Las comparaciones precio/indicador no dependen del ajuste y no usan el futuro.
  - Los niveles de stop y objetivo se devuelven a precio real.
  - El VWAP usa precio real y volumen real, desde las 09:30 NY (RTH) o desde las 18:00 NY (Globex).

## 3. Costes (1 MNQ = 2 $/punto; tick 0,25 = 0,50 $)
| Escenario | Comisión por lado | Deslizamiento por orden a mercado o stop |
|---|---|---|
| BASE | 1,00 $ | 1 tick; 2 ticks en aperturas (Londres 07:50-08:10 LDN, NY 09:25-09:45 NY, Globex 18:00-18:15 NY) |
| STRESS 1 | 2,00 $ | ×2 |
| STRESS 2 | 3,00 $ | ×3 |

- Los objetivos límite no tienen deslizamiento en ningún escenario. Si una estrategia pierde la expectativa positiva con ×2, es **frágil**.
- La señal se investiga con **1 MNQ fijo**. El tamaño se estudia aparte (sección 9).

## 4. Variantes pre-registradas (presupuesto de parámetros)
Se cambia un componente cada vez respecto a la base, sin rejillas completas. Las variantes "control" sirven solo para medir si un filtro importa y **no se pueden seleccionar**.

| BOT | Marco | Variantes | Detalle en |
|---|---|---|---|
| 13 VWAP mean reversion | 5 m RTH | 11 | `strategies/vwap_mean_reversion.py` |
| 14 ORB | 1 m + rango | 14 (10 puras + 4 filtros de uno en uno) | `strategies/orb.py` |
| 15 Trend following | 15 m | 6 | `strategies/trend_following.py` |
| 16 Momentum breakout | 5 m | 9 | `strategies/momentum.py` |
| 17 Pullback trend | 5 m | 4 | `strategies/pullback.py` |
| 18 RSI(2) extremo + filtro | diario | 8 | `strategies/rsi2_extremo.py` |
| 19 VWAP + régimen | 5 m | 4 + 2 controles | `strategies/regime.py` |
| 21 Hora del día (deriva nocturna, literatura) | 1 m | 2 | `strategies/time_of_day.py` |
| 23 Niveles del día anterior | 5 m | 4 | `strategies/previous_day.py` |
| 24 Rango nocturno → NY | 5 m | 3 | `strategies/overnight.py` |
| 26 Spread oro/plata (z-score) | diario | 3 | `strategies/statistical_spread.py` |
| 25/26 NQ-ES | — | pendiente de datos | — |

Los parámetros exactos de cada variante están en el código de su módulo (`VARIANTES`), escrito antes de ejecutar. Las vecindades de sensibilidad también se fijan en el módulo (`VECINDAD`).

## 5. Protocolo por BOT
1. **Cribado (solo TRAIN):** se ejecutan todas las variantes pre-registradas.
2. **Selección (solo TRAIN):**
   - Gana la variante no-control con mayor **t de la expectativa** (media / error estándar). Necesita ≥ 100 operaciones, o ≥ 30 si es diaria o de baja frecuencia.
   - Si varias quedan a menos de 0,3 de t, gana la **base** o la más simple.
   - Se anota el motivo en `RESEARCH_LOG.md`.
3. **Puerta de cribado (variante elegida, TRAIN):** expectativa > 0, PF ≥ 1,05, t ≥ 1,5 y muestra suficiente. Si solo falla la muestra, es **C**.
4. **VALIDATION (solo la variante elegida, sin re-ajustar):** expectativa > 0 y PF ≥ 1,00 → **finalista**.
5. **Finalistas:**
   - walk-forward;
   - sensibilidad (vecindad);
   - costes ×2 y ×3;
   - regímenes, año, sesión y día;
   - bootstrap por bloques;
   - Monte Carlo.
   Después se abre el TEST una vez.
6. Como máximo 3 estrategias nuevas pasan a cartera.

## 6. Validación
- **Walk-forward:**
  - ventanas de 12 meses de entrenamiento y 3 de prueba, que avanzan 3 meses;
  - en cada ventana se re-selecciona, con la regla del punto 5.2, entre las variantes pre-registradas del BOT (mínimo 20 operaciones);
  - se informa el P&L concatenado de las ventanas de prueba y el % de ventanas positivas;
  - también se informa la versión con parámetros fijos.
- **Bootstrap:**
  - por bloques de 20 sesiones, 5.000 réplicas, semilla 20260930;
  - IC 95 % de la expectativa;
  - distribuciones a 1 año (252 sesiones): P&L, drawdown máximo, P(año negativo), P(drawdown ≥ 2.500 $ / 5.000 $) y P(ruina = perder el 50 % de 25.000 $).
- **Sensibilidad:** la vecindad pre-registrada.
  - **Estabilidad** = media de 4 fracciones: vecinos con expectativa > 0, años positivos, regímenes de volatilidad positivos (de 3) y costes ×2 positivos (0 o 1).
  - Se busca una meseta, no un pico.
- **Regímenes (fijos, sin optimizar):**

  | Régimen | Medida (sesión anterior, causal) | Clases |
  |---|---|---|
  | Volatilidad | ATR(14) diario / ATR(250) diario | BAJA < 0,8; NORMAL; ALTA > 1,2 |
  | Tendencia | Ratio de eficiencia de 20 sesiones | TENDENCIA > 0,3; RANGO el resto |
  | Sesión | Hora de entrada NY | Noche 18-03, Londres 03-08, Pre-apertura/solape 08-09:30, Apertura NY 09:30-10:30, Mañana NY 10:30-11:30, Mediodía 11:30-14, Tarde 14-16 |

## 7. Clasificación automática (se aplica al tramo completo cuando el TEST ya está abierto)
Criterios:
1. PF > 1,15.
2. Expectativa > 0.
3. IC 95 % por bloques > 0.
4. Operaciones ≥ 200 (≥ 100 si es de baja frecuencia).
5. Walk-forward: expectativa concatenada > 0 y ≥ 50 % de ventanas positivas.
6. Estabilidad ≥ 0,70.
7. Costes ×2 con expectativa > 0.
8. Años positivos ≥ 60 %.
9. Monte Carlo: P(año negativo) < 30 %.
10. Drawdown aceptable: neto anual / |DD máx| ≥ 0,33.
11. TEST con expectativa > 0.

Clases:
| Clase | Condición |
|---|---|
| **A — ROBUST** | Cumple 2, 3, 4, 5, 7 y 11, y al menos 9 de los 11 |
| **E — NEGATIVE** | No pasa el cribado ni la validación (con muestra suficiente) |
| **D — FRAGILE** | Finalista con estabilidad < 0,5, o que pierde con costes ×2 |
| **C — INSUFFICIENT** | Resultado positivo con muestra insuficiente (menos de 100 operaciones en TRAIN, o menos de 30 si es diaria) |
| **B — PROMISING** | El resto de finalistas |

## 8. Pruebas múltiples
- Se cuentan **todas** las variantes ejecutadas, controles incluidos. También se anotan las hipótesis ya probadas en `archive/` y en la auditoría.
- Para cada finalista se informa la t que haría falta con Bonferroni para el número total de variantes del laboratorio. Es informativa: no se usa como puerta.

## 9. Cartera, tamaño y prop firm (solo después de clasificar)
- **Carteras:** A = BOT01 + BOT02 (1+1 MNQ). B = A + la mejor nueva. C = B + la segunda mejor que no esté correlacionada (correlación diaria < 0,3).
- **Tamaño** (solo finalistas con stop): arriesgar 0,25 %, 0,5 % y 1 % de 25.000 $ por operación, con contratos enteros y un máximo de 10 MNQ.
- **Prop firm** (módulo aparte, sin adaptar la estrategia): cuenta de 50.000 $ con:
  - límite diario de 1.000 $;
  - drawdown trailing de 2.500 $ sobre el cierre diario;
  - objetivo de 3.000 $;
  - máximo 10 MNQ.
  Se informa la probabilidad de alcanzar el objetivo antes de quemar la cuenta, por bootstrap del P&L diario.

## Cambios tras ver datos
- 30-sep, **antes de ver ningún resultado** (solo recuentos de operaciones de 2015-2016): el BOT 24.2 ("la sesión
  abre fuera del rango nocturno") dio 1 operación en 2 años, porque el rango nocturno incluye el precio de las 09:29.
  Se redefine como ruptura fallida del rango nocturno (el precio lo supera entre 09:30 y 11:30 y vuelve a cerrar
  dentro). Es un error de definición, no un ajuste a resultados.
