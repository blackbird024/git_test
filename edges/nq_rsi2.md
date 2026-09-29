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
