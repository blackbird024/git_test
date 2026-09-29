# SMC algorítmico — Barrido de liquidez + desplazamiento + FVG (MGC y MNQ)

*Ficha escrita el 29-sep-2026, ANTES de ejecutar ningún backtest de esta versión.*

## Hipótesis
Cuando el precio barre el máximo (o mínimo) de la sesión anterior, vuelve a cerrar dentro y, acto seguido, se
mueve con fuerza en sentido contrario (desplazamiento) dejando un hueco de precio (FVG), ese movimiento revela
participación institucional real. Un retroceso al FVG ofrece una entrada a favor del nuevo movimiento con un riesgo
acotado (detrás del extremo del barrido), y el precio tiende a llegar a la siguiente zona de liquidez.

## Racional de mercado
- Detrás del máximo/mínimo de la sesión anterior se acumulan stops y órdenes de ruptura (liquidez).
- Un barrido seguido de vuelta dentro indica que esa liquidez sirvió de contrapartida a órdenes grandes en el
  sentido contrario.
- El **desplazamiento** (una vela grande respecto a la volatilidad normal) es la huella de esas órdenes grandes;
  sin él, un barrido es solo ruido. Esta es la diferencia con la versión ya probada (barrido + IFVG en el oro,
  sin ventaja): aquí se exige un movimiento fuerte y se entra en el **retroceso**, no en la ruptura del FVG.
- El FVG es una zona que el precio cruzó sin negociar en los dos sentidos; los participantes que no pudieron
  entrar ofrecerían liquidez al volver.

## Definición exacta de cada regla
Patrón en velas de **5 minutos** (construidas desde 1M; una vela de 5M solo se usa cuando ya ha cerrado).
Ejecución y gestión en velas de **1 minuto**. Datos en UTC; ventanas en la zona local de cada mercado.

| Elemento | MGC (oro) | MNQ (Nasdaq) |
|---|---|---|
| Niveles de liquidez | Máximo (PDH) y mínimo (PDL) de la **sesión anterior de CME** | Igual |
| Ventana del patrón | 08:00–16:00 de **Londres** | 09:30–15:30 de **Nueva York** |
| Cierre forzado | 16:30 de Londres | 15:55 de Nueva York |

**1. Barrido.** Una vela de 5M dentro de la ventana supera el nivel (máximo > PDH, o mínimo < PDL).
- Tiene que ser el **primer cruce** de la sesión: si el nivel ya se superó antes (desde la apertura de la sesión
  de CME a las 18:00 de Nueva York), ya está barrido y no cuenta.
- Extremo del barrido = el máximo (o mínimo) alcanzado desde esa vela; se actualiza mientras el patrón no esté
  completo.

**2. Vuelta dentro.** En las **N = 6** velas siguientes (30 minutos, contando la del barrido), una vela de 5M
cierra de vuelta dentro (cierre < PDH, o cierre > PDL). Si no ocurre, el barrido se descarta.

**3. Desplazamiento.** Desde la vuelta dentro, en las N = 6 velas siguientes aparece una vela de 5M en el sentido
contrario al barrido (bajista si se barrió el máximo) cuyo **cuerpo |cierre − apertura| ≥ k × ATR(14)** de 5M, con
**k = 1,5**. ATR = media del rango verdadero de las 14 velas de 5M **anteriores** a la de desplazamiento
(precisión añadida antes de ver ningún resultado: así la vela grande no infla su propia referencia).

**4. FVG.** La vela de desplazamiento es la vela central de un patrón de 3 velas con hueco:
- Bajista: máximo de la vela 3 < mínimo de la vela 1. Zona = [máximo vela 3, mínimo vela 1].
- Alcista: mínimo de la vela 3 > máximo de la vela 1. Zona = [máximo vela 1, mínimo vela 3].
- El FVG queda confirmado al cierre de la vela 3.

**5. Entrada (orden límite en el retroceso).** Desde el cierre de la vela 3, orden límite en el **borde cercano**
del FVG (corto: máximo de la vela 3; largo: mínimo de la vela 3).
- Se considera llenada si el precio (velas de 1M) cruza el límite en **al menos 1 tick** (supuesto conservador:
  tocar el precio justo no garantiza el llenado).
- Validez de la orden: **M = 12** velas de 5M (60 minutos) y siempre dentro de la ventana. Se cancela si antes
  el precio toca el stop o el objetivo.
- Sin deslizamiento en la entrada (orden límite).

**6. Stop.** Extremo del barrido ± 2 ticks.

**7. Objetivo: siguiente zona de liquidez.** Corto: el **mínimo de la sesión actual** antes del barrido (desde las
18:00 de Nueva York); si no queda por debajo de la entrada, el PDL. Largo: simétrico. Si la recompensa es menor que
**1R**, no se opera (Apex prohíbe objetivos pequeños con stops grandes).

**8. Gestión.** Una sola operación al día por mercado (el primer patrón completo). Si el stop y el objetivo caen en
la misma vela de 1M, pérdida. En la vela en que se llena la orden límite solo cuenta el stop, no el objetivo
(no se sabe el orden). Salida por tiempo en el cierre forzado.

**9. Tamaño.** 1 contrato fijo (1 MGC o 1 MNQ), para no descartar días de stop ancho; resultados también en R.

## Parámetros libres (3), fijos en esta fase
| Parámetro | Valor |
|---|---|
| k del desplazamiento | 1,5 × ATR(14) de 5M |
| N (ventana de vuelta dentro y de desplazamiento) | 6 velas de 5M |
| M (validez de la orden límite) | 12 velas de 5M |

Fijos por definición: niveles PDH/PDL, ventanas, stop a 2 ticks del extremo, objetivo en la siguiente liquidez,
RR mínimo 1.

## Costes (modelo estándar, sin cambios)
Comisión 1 $ por contrato y lado. Deslizamiento de 1 tick (2 en aperturas de sesión) en stops y salidas por
tiempo; 0 en la entrada límite y en el objetivo. Resultados antes y después de costes.

## Periodo
Desarrollo: sesiones hasta el 21-mar-2023 (GC y NQ). El fuera de muestra (desde el 22-mar-2023) no se carga.
Se excluyen las sesiones ilíquidas previsibles.

## Criterios de aceptación / rechazo (paso 1)
Se decide **por mercado, por separado**. Pasa al paso 2 solo si, después de costes: profit factor > 1 **y** R medio
> 0 con **t ≥ 2**. Si no: rechazada en ese mercado, sin filtros para salvarla.

## Posibles fuentes de sesgo
1. **Conocimiento previo:** ya probé barrido + IFVG en el oro sin ventaja. Esta versión es distinta (niveles solo del
   día anterior, desplazamiento obligatorio, entrada en retroceso con límite, objetivo en liquidez), y sus reglas vienen
   de la especificación de la estrategia, no ajustadas a aquel resultado.
2. **Llenado de órdenes límite:** exigir 1 tick de cruce es conservador, pero en la realidad también se pierden
   llenados justo cuando el precio no vuelve (selección adversa). El modelo lo captura en parte.
3. **Dos mercados = dos pruebas:** con el listón t ≥ 2 en cada uno, la probabilidad de un falso positivo sigue existiendo.
4. **Velas de 1M:** ambigüedad dentro de la vela, resuelta siempre en contra.
5. **Contrato continuo** y minutos sin negociación (oro): igual que en el resto del proyecto.
6. **Definiciones:** hay muchas formas de definir un barrido o un desplazamiento; esta ficha fija una antes de ver
   datos y no se cambiará según el resultado.
