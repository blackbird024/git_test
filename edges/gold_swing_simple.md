# GOLD_SWING_SIMPLE_v1.0: swing en el oro (4H dirección → 1H barrido + confirmación + FVG → entrada en 15m)

*Ficha escrita el 29-sep-2026, ANTES de programar y de ejecutar ningún backtest. Las reglas vienen de la especificación
del usuario. Donde la especificación admite más de una lectura, se fija aquí UNA interpretación mecánica y no se cambia
después de ver resultados. Cualquier cambio posterior será GOLD_SWING_SIMPLE_v1.1.*

## Hipótesis
Cuando el oro está en tendencia en 4H (máximos y mínimos crecientes, o decrecientes), un barrido de liquidez en 1H en
contra de la tendencia, seguido de una vela que recupera todo el rango de la vela del barrido y deja un hueco (FVG),
marca el final del retroceso. Si se entra en el retroceso al 50 % del FVG, con el stop detrás del barrido, el precio
llega a 2R más a menudo que al stop (más de 1 de cada 3 veces, que es el punto de equilibrio sin costes).

## Racional
- Los stops de los que operan a favor de tendencia están bajo los mínimos recientes. Barrerlos da liquidez a órdenes
  grandes en el sentido de la tendencia.
- La vela de confirmación (cierre por encima del máximo de la vela del barrido) muestra que los compradores recuperan
  el control; el FVG es la huella de ese desplazamiento.
- Honestidad: el proyecto ya probó ideas cercanas en el oro sin ventaja: barrido de Londres, setup ICT con IFVG,
  PO3 / Judas swing y SMC barrido + desplazamiento + FVG (implementada, sin ejecutar). Esta versión es distinta
  (swing multi-día, filtro de tendencia 4H, niveles de swing de 1H), pero no parte de cero. Lo tendremos en cuenta al leer el resultado.

## Datos
- **Instrumento:** futuros GC de Databento (contrato continuo por volumen), velas de 1 minuto en UTC. Sustituyen a
  XAUUSD al contado: el precio es casi idéntico (diferencia de base de unos pocos dólares, estable día a día) y cotizan
  casi las mismas horas (domingo 18:00 NY → viernes 17:00 NY, con pausa diaria de 1 h).
- **Cambios de contrato:** hay 59 en el periodo. La serie se **ajusta hacia atrás** (sumando el salto de cada cambio a
  todos los precios anteriores). El salto se mide como apertura del contrato nuevo − cierre del anterior. Las reglas
  solo usan diferencias de precio, y un desplazamiento constante de todo el pasado no cambia ninguna comparación, así
  que el ajuste no mete información futura. Límite conocido: si el cambio cae en la reapertura del domingo, el salto
  medido incluye el hueco del fin de semana. Se informará de las operaciones abiertas durante un cambio de contrato.
- **Marcos:** se construyen desde 1M. La estrategia SOLO ve velas de 15m, 1H y 4H (nada inferior a 15m).
  - 15m y 1H: bloques de reloj (UTC).
  - 4H: alineadas con la sesión de CME (18:00, 22:00, 02:00, 06:00, 10:00 y 14:00 de NY).
  - Una vela solo se usa desde su **cierre nominal** (inicio + duración).

## Reglas exactas (v1.0)

### 1. Swings (4H y 1H, mismo método)
- **Swing high** en la vela i: `high[i]` es estrictamente mayor que el `high` de las 2 velas anteriores y de las 2
  posteriores.
- **Swing low**: `low[i]` es estrictamente menor que el de las 2 velas a cada lado.
- **Momento de confirmación:** el cierre de la vela i+2. Antes de ese momento el swing no existe para la estrategia.

### 2. Dirección 4H
Se evalúa en un instante t con los swings de 4H confirmados hasta t:
- **Alcista:** el último swing high confirmado > el anterior **y** el último swing low confirmado > el anterior.
- **Bajista:** el último swing high confirmado < el anterior **y** el último swing low confirmado < el anterior.
- **Cualquier otro caso:** neutral → NO TRADE.

La dirección tiene que coincidir con el setup al cierre de la vela del barrido y seguir coincidiendo hasta la entrada.
Si cambia (a neutral o a la contraria) antes de la entrada, el setup se cancela.

### 3. Barrido 1H (liquidity sweep)
**Nivel vigente de mínimos:** el último swing low de 1H confirmado **antes** de que empiece la vela evaluada, siempre
que ninguna vela posterior a su confirmación haya operado por debajo. En cuanto una vela opera por debajo, el nivel
queda "gastado", y no hay otro nivel hasta que se confirme un swing low nuevo. Solo cuenta el último swing: si el
último está gastado, no se vuelve a uno anterior.

**Barrido de mínimos** (sirve para LARGOS): en la primera vela 1H que opera por debajo del nivel vigente se cumple
`low < nivel` y `cierre > nivel`. Si esa vela cierra en el nivel o por debajo, es una ruptura, no un barrido: el nivel
se gasta sin setup.

**Barrido de máximos** (sirve para CORTOS): simétrico, con el último swing high.

Se detectan todos los barridos de los dos lados. Solo inician un setup los que van a favor de la dirección 4H
(barrido de mínimos con 4H alcista, barrido de máximos con 4H bajista).

### 4. Confirmación 1H
- **Largo:** la vela 1H siguiente a la del barrido (la vela b+1) cierra por encima del **máximo** de la vela del barrido.
- **Corto:** la vela b+1 cierra por debajo de su mínimo.
- Si no ocurre en esa misma vela, el setup se cancela (`NO_CONFIRMATION`).

### 5. FVG 1H
Interpretación fijada: el FVG tiene como vela central la de confirmación. Es decir, vela 1 = la del barrido,
vela 2 = la de confirmación y vela 3 = la vela b+2.
- **Alcista:** `low[vela 3] > high[vela 1]`. Zona = [high vela 1, low vela 3].
- **Bajista:** `high[vela 3] < low[vela 1]`. Zona = [high vela 3, low vela 1].
- Si no hay hueco, el setup se cancela (`NO_FVG`). No se buscan otros FVG.
- El FVG existe desde el cierre de la vela 3.

### 6. Entrada 15m
- Orden límite en el **50 % del FVG**, activa desde el cierre de la vela 3.
- Se llena cuando una vela de 15m toca ese precio (el mínimo ≤ 50 % en largos; el máximo ≥ 50 % en cortos).
- Precio de llenado: el 50 %, o la apertura de la vela si ya abre más allá del 50 % pero dentro de la zona (una orden
  límite se llena al mejor precio disponible).
- Sin ninguna confirmación en 15m.

### 7. Validez y cancelación del setup (antes de la entrada)
Primero ocurre la entrada, si el precio toca el 50 %. Si antes pasa cualquiera de estas cosas, el setup se cancela:

| Motivo | Regla mecánica |
|---|---|
| `CANCEL_TRAVERSED` | Una vela de 15m abre ya al otro lado de la zona (hueco que la atraviesa sin tocar el 50 % de forma operable). Una vela que viene desde fuera y cruza toda la zona toca antes el 50 %: eso es una entrada |
| `CANCEL_COUNTER_STRUCTURE` | Una vela 1H cierra más allá del extremo del barrido: por debajo del mínimo del barrido en largos, por encima del máximo en cortos |
| `EXPIRED_24H` | Han cerrado 24 velas 1H después de la de confirmación (vela b+25) |
| `CANCEL_NEW_SWEEP` | Cierra otra vela 1H con un barrido, de cualquier lado, según la regla 3. Ese nuevo barrido puede empezar su propio setup |
| `CANCEL_4H_CHANGED` | La dirección 4H deja de coincidir con el setup |

- Los eventos de 1H y 4H cancelan la orden desde el **cierre** de la vela en que ocurren. Las velas de 15m que empiezan
  antes de ese cierre todavía pueden llenar la orden.
- Máximo 1 entrada por setup.
- Si hay una operación abierta, no se buscan setups: los barridos que cierran mientras hay una operación abierta se
  registran como `TRADE_OPEN` y se descartan.

### 8. Stop
- **Largo:** mínimo de la vela del barrido − `SL_BUFFER`.
- **Corto:** máximo de la vela del barrido + `SL_BUFFER`.
- `SL_BUFFER = 0,10 × ATR(14)` de 1H. Es el ATR de Wilder al cierre de la vela del barrido, configurable.
- El stop es fijo: sin trailing y sin break-even.

### 9. Objetivo
TP = entrada ± 2R, con R = |entrada − stop| usando el precio de llenado. Orden límite. Un único objetivo, sin parciales.

### 10. Gestión
- 1 operación abierta como máximo. Solo se sale por stop o por objetivo: no hay salida por tiempo ni por estructura, y
  la operación puede durar días (incluidos fines de semana).
- Gestión en velas de 15m:
  - En la vela del llenado solo cuenta el stop, porque no se sabe el orden dentro de la vela.
  - Si una vela toca stop y objetivo a la vez, cuenta como pérdida.
  - Si la vela abre más allá del stop (hueco), se sale en la apertura.
- Al final de los datos del periodo, la operación abierta se cierra al último precio (`END_OF_DATA`).

### 11. Tamaño (para los resultados en dinero)
- Cuenta de 50.000 $ y riesgo del 0,5 % del saldo en cada operación, con `src/risk/position_sizing.py`.
- La unidad es 1 onza (0,01 lotes de XAUUSD = 1 oz; 1 MGC = 10 oz).
- Onzas = floor(saldo × 0,5 % / R). Si sale menos de 1 oz, no se opera (`POSITION_SIZE_BELOW_MINIMUM`).
- Los resultados se dan también en R, que no depende del tamaño.

## Costes (configurables; en $ por onza)
| Escenario | Spread (ida y vuelta) | Comisión (ida y vuelta) | Deslizamiento adverso |
|---|---|---|---|
| A: sin costes | 0 | 0 | 0 |
| B: realistas | 0,30 | 0,07 (7 $ por lote de 100 oz) | 0 |
| C: B + deslizamiento | 0,30 | 0,07 | 0,10 en la entrada y 0,30 en las salidas por stop |

- El objetivo (orden límite) nunca lleva deslizamiento.
- Los datos son precios negociados. El spread se descuenta como un coste por operación, en lugar de simular precios
  de compra y de venta por separado.

## Parámetros (fijos en v1.0)
Swing de 2 velas, TP 2R, entrada al 50 % del FVG, buffer de 0,10 × ATR(14) de 1H y caducidad de 24 velas 1H.

## Periodo
- **Desarrollo (70 %):** sesiones de CME del 2-ene-2015 al 21-mar-2023 (`config/particion.json`).
- **Fuera de muestra (30 %):** desde el 22-mar-2023. **Bloqueado.** Solo se ejecuta si el desarrollo cumple los
  criterios. El OOS del oro ya se usó con otras familias de estrategias, pero no con esta.

## Criterios (fijados antes de ejecutar)
**Para pasar del desarrollo al fuera de muestra**, con el escenario B, deben cumplirse todos:
1. al menos 100 operaciones (si hay menos: `INSUFFICIENT_SAMPLE`, no se evalúa);
2. PF > 1;
3. R medio > 0 con t ≥ 2.

t ≥ 2 es necesario pero no suficiente: el proyecto ya ha probado muchas hipótesis.

**Si falla:** se registra, las reglas no se tocan y el fuera de muestra no se ejecuta.

**Sensibilidad (solo diagnóstico, después del backtest oficial, solo en desarrollo):** se cambia un parámetro cada
vez:
- swing de 3 velas;
- TP de 1,5R y de 2,5R;
- entrada en el borde cercano del FVG (el primero que toca el precio) y en el borde lejano;
- buffer 0.

Se reportan todas las variantes. Ninguna sustituye a la v1.0.

## Posibles fuentes de sesgo
1. Conocimiento previo de ideas parecidas en el oro (ver arriba).
2. GC en lugar de XAUUSD al contado; hay cambios de contrato y ajuste hacia atrás.
3. Llenado de órdenes límite por contacto: es optimista, porque en la realidad tocar el precio no garantiza el
   llenado. Por eso el escenario C penaliza la entrada.
4. Velas de 15m: la ambigüedad dentro de la vela se resuelve siempre en contra.
5. Las interpretaciones de los puntos 3, 5 y 7 son decisiones mías, fijadas aquí antes de ver datos.
