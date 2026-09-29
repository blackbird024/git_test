# Ventaja 3 — Nasdaq: RSI(2) con filtro de la media de 200 (Connors)

*Escrita el 29-sep-2026, ANTES de ejecutar ningún backtest.*

## Hipótesis
En un índice con tendencia alcista de fondo (precio por encima de su media de 200 sesiones), las caídas
cortas y bruscas (RSI de 2 periodos muy bajo) tienden a revertir en pocos días.

## Por qué debería funcionar (la causa)
- En tendencia alcista hay compradores estructurales (flujos de fondos, planes de pensiones, recompras)
  que aprovechan las caídas.
- Las caídas de 1-3 días suelen deberse a ventas forzadas o reacciones exageradas (liquidez), no a un
  cambio de fundamentales, y se corrigen.
- El filtro de 200 sesiones evita comprar caídas en mercados bajistas, donde las caídas continúan.

**Origen:** Larry Connors y Cesar Alvarez, *Short Term Trading Strategies That Work* (**2008**). (El RSI(2)
es de Connors; Larry Williams es el autor del %R.) Todos nuestros datos (2015-2026) son posteriores a la
publicación: si la ventaja existe aquí, ha sobrevivido a hacerse pública.

## Reglas exactas (versión mínima)
| Elemento | Regla |
|---|---|
| Mercado | MNQ (datos de NQ), 1 contrato |
| Velas | Diarias de la sesión de CME (18:00 → 17:00 de Nueva York), construidas desde 1M |
| Serie para indicadores | Cierres ajustados por los cambios de contrato (sin saltos de roll) |
| Señal | Al cierre de la sesión: cierre > SMA(200) y RSI(2) < **20** |
| Entrada | Apertura de la sesión siguiente (reapertura de Globex, 18:00 de Nueva York) |
| Salida | Al cierre en que RSI(2) > **70** (salida en la apertura siguiente), o tras **5** sesiones |
| Stop | Ninguno (versión mínima, como en el original) |
| Costes | 1 $ por contrato y lado; 2 ticks en la reapertura de Globex, 1 tick en el resto |

**Parámetros libres (3):** umbral de entrada = 20, umbral de salida = 70 (centro del rango 60-80
propuesto), días máximos = 5.

## Comparación
El Nasdaq ha subido mucho en estos años. Se compara el rendimiento por día dentro de la operación con el
rendimiento medio por día de estar comprado siempre. La ventaja tiene que ser mejor que la simple subida del
mercado.

## Qué la refutaría
- Profit factor ≤ 1 después de costes → **descartada**.
- Rendimiento por día invertido no mejor que el de comprar y mantener.
- Resultado concentrado en pocos años.

**Aviso: incompatible con Apex** (mantiene posiciones de un día para otro). Solo para cuenta propia.

## Resultado del paso 1 y del paso 2 (periodo de desarrollo)
- Paso 1: 97 operaciones, acierto 68 %, PF 1,46, R medio +0,30, t 1,22 → pasa al paso 2.
- Paso 2: salida RSI>60, filtro de volatilidad y stop de 2 ATR NO mejoran a la vez PF y R medio → versión
  final = versión mínima (entrada 20, salida 70, máximo 5 sesiones, sin stop).

## Criterios de validación del paso 3 (escritos ANTES de mirar el fuera de muestra)
Todos deben cumplirse:
1. Fuera de muestra: profit factor ≥ 1,3, y al menos 100 operaciones sumando desarrollo y fuera de muestra.
2. R medio fuera de muestra ≥ 50 % del R medio de desarrollo (0,30 → mínimo 0,15).
3. Sensibilidad (en desarrollo): cada parámetro ±20 % (entrada 16/20/24, salida 56/70/84, máx. días 4/5/6);
   las 27 combinaciones con profit factor > 1.
4. Otro mercado: ES (datos diarios de Databento, día UTC, 2010-2026): profit factor > 1.
5. Costes duplicados (periodo completo): beneficio neto > 0.
6. Monte Carlo (1.000 órdenes aleatorias, periodo completo): se informa del drawdown al percentil 95.
7. Walk-forward: no aplica (ningún parámetro se ha optimizado).
