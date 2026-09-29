# Ventaja 1 — Barrido de Londres en el oro (MGC)

*Escrita el 29-sep-2026, ANTES de ejecutar ningún backtest de esta versión.*

## Hipótesis
En la apertura de Londres, el precio va a buscar los stops acumulados durante la sesión asiática y del día
anterior (por encima de los máximos y por debajo de los mínimos). Una vez ejecutados esos stops, el
movimiento se agota y gira. Si el precio supera un nivel de liquidez y vuelve a cerrar dentro, es más
probable que continúe hacia el lado contrario que en la dirección de la ruptura.

## Por qué debería funcionar (la causa)
- Los stops de las posiciones abiertas en Asia se acumulan justo detrás de los extremos del rango.
- Al abrir Londres entra mucho volumen institucional. Para comprar mucho sin mover el precio en contra
  hace falta contrapartida vendedora, y los stops de venta de otros son exactamente eso (y al revés).
- Consumida esa liquidez, sin más órdenes detrás, el precio vuelve.

**Advertencia honesta:** en este proyecto ya probé una versión parecida (con filtro de sesgo diario/4H,
sin la confirmación de cierre de vuelta dentro y con Asia desde las 06:00) y no funcionó. Esta ficha
describe una versión distinta, pero lo dejo escrito.

## Reglas exactas (versión mínima, sin filtros)
Todas las horas en Italia (Europe/Rome); internamente en UTC.

| Elemento | Regla |
|---|---|
| Mercado | MGC (datos de GC), 10 $ por dólar de precio, tick 0,10 |
| Niveles | Máximo y mínimo de Asia (01:00–08:50) y máximo y mínimo de la sesión anterior de CME |
| Ventanas | 08:50–09:10 y 10:03–10:30 |
| Barrido | Una vela de 1M dentro de la ventana supera un nivel (máximo por encima de un nivel superior, o mínimo por debajo de un nivel inferior). Nivel barrido = el más exterior superado |
| Confirmación | Una vela de 1M dentro de la ventana cierra de vuelta dentro (por debajo del nivel barrido si fue arriba) |
| Entrada IFVG | FVG a favor del barrido (3 velas: hueco entre la vela 1 y la 3) formado en los 30 minutos previos al extremo del barrido. Cuando una vela cierra al otro lado del FVG (a partir de la confirmación), se entra en la apertura de la vela siguiente |
| Entrada breaker | Si no hay FVG en ese tramo: cierre al otro lado de la vela que hizo el extremo del barrido |
| Dirección | Contraria al barrido (barrido arriba → corto; barrido abajo → largo) |
| Stop | Extremo del barrido ± **margen** |
| Objetivo | **2R** |
| Cierre forzado | **12:00** |
| Límites | Máximo 2 operaciones al día; si una operación pierde, se acaba el día |
| Tamaño | 0,5 % de 50.000 $ = 250 $ de riesgo; contratos = floor(250 / (distancia × 10)) |
| Costes | 1 $ por contrato y lado; deslizamiento de 2 ticks en 08:50–09:10 (apertura de Londres) y 1 tick fuera |
| Días excluidos | Sesiones ilíquidas previsibles (ver `reports/calidad_datos.md`) y días sin rango asiático completo |

**Parámetros libres (3):** margen del stop = 1,5 $, objetivo = 2R, cierre = 12:00.

## Pregunta clave: ¿aportan algo las ventanas "macro"?
Se aplican exactamente las mismas reglas en franjas FUERA de las ventanas, después de las 08:50:
09:10–09:40, 09:40–10:03, 10:30–11:00 y 11:00–11:30 (primer setup de cada franja, cada operación evaluada
por separado, cierre a las 12:00). Se compara el R medio de los setups dentro y fuera de las ventanas.

## Qué la refutaría
- Profit factor ≤ 1 después de costes en el periodo de desarrollo → **descartada**.
- Si los setups dentro de las ventanas no tienen mejor R medio que los de fuera → las ventanas "macro" no
  aportan nada (se dirá así, aunque la estrategia en conjunto fuera rentable).
