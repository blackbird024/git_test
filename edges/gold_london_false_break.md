# GOLD_LONDON_FALSE_BREAK_v1.0: falsa ruptura del rango inicial de Londres en el oro (15m)

*Ficha escrita el 29-sep-2026, ANTES de programar y de ejecutar. Reglas de la especificación del usuario. Donde admiten
más de una lectura, se fija aquí UNA interpretación mecánica, que no se cambia después de ver resultados. Cualquier
cambio será GOLD_LONDON_FALSE_BREAK_v1.1.*

## Hipótesis
Cuando el oro supera un extremo del rango de la primera hora de Londres y la misma vela de 15m cierra de vuelta dentro,
la ruptura ha fallado. Los que compraron (o vendieron) la ruptura quedan atrapados, y el precio tiende a ir hacia el
extremo opuesto lo bastante como para llegar a 2R antes que al stop.

## Contexto honesto (conocimiento previo)
- `edges/london_range_breakout_gold.md` usó el **mismo rango** (08:00-09:00 de Londres, velas de 1m) apostando a la
  **continuación**. Sin ventaja: PF 1,00 antes de costes, y solo el 30 % de las rupturas llegó a 2R.
- `edges/barrido_londres.md` (giro tras barrer niveles de Asia y del día anterior en la apertura de Londres): PF 0,99.
- Esta versión es distinta (falsa ruptura del rango en una sola vela de 15m, stop en esa vela, entrada inmediata), y
  sus reglas vienen de la especificación del usuario, no se han ajustado con esos resultados. Pero la zona horaria y
  el tipo de idea no son nuevos. Se tendrá en cuenta al leer el resultado (pruebas múltiples).

## Datos
- Futuros GC (Databento), con el mismo ajuste hacia atrás por cambios de contrato que los estudios anteriores
  (`ajustar_rolls`).
- La estrategia **solo ve velas de 15m** (bloques de reloj: :00, :15, :30, :45), construidas desde 1M.
- Horas en **Europe/London**, convertidas a UTC día a día (respeta el cambio de hora).
- Se excluyen las sesiones ilíquidas previsibles (regla causal del proyecto, igual que en el London Range Breakout) y
  los fines de semana.

## Reglas exactas (v1.0)

### 1. Rango de Londres
- Velas de 15m que empiezan a las **08:00, 08:15, 08:30 y 08:45** de Londres.
- `RH` = máximo y `RL` = mínimo de esas 4 velas.
- Se congela a las 09:00 y no cambia en todo el día.
- **Día válido:** las 4 velas presentes y `RH > RL`. Si no, no se opera (`RANGE_INCOMPLETE`).

### 2. Ventana
- Velas de señal: las que **empiezan entre las 09:00 y las 11:30** de Londres.
- La entrada es en la apertura de la vela siguiente, así que la última entrada posible es a las 11:45.
- No se abre nada a partir de las 12:00.

### 3. Falsa ruptura y "primer break" (interpretación fijada)
- **Primer ataque a un extremo:** la primera vela de la ventana cuyo máximo supera `RH` (o cuyo mínimo baja de `RL`).
- **Falsa ruptura del HIGH:** esa primera vela que supera `RH` **cierra por debajo de `RH`** → señal SHORT.
- **Falsa ruptura del LOW:** esa primera vela que baja de `RL` **cierra por encima de `RL`** → señal LONG.
- **Ruptura real:** si la primera vela que ataca un extremo cierra fuera del rango, ese extremo queda "gastado" y ya no
  puede dar señal ese día. El otro extremo sigue disponible.
- **Una sola señal por día:** la primera falsa ruptura válida. Si no llega a operarse (entrada más allá del stop o
  tamaño < 1 oz), ese día no hay más operaciones.
- **Vela que ataca los dos extremos a la vez:** es ambigua y el día no se opera (`BOTH_SIDES_SAME_BAR`).
- Los ataques a un extremo durante la formación del rango no cuentan: forman el rango.

### 4. Entrada
A mercado, en la **apertura de la vela de 15m siguiente** a la de la falsa ruptura.

### 5. Stop
- **SHORT:** máximo de la vela de la falsa ruptura + 0,10 × ATR(14) de 15m.
- **LONG:** mínimo − 0,10 × ATR(14).
- El ATR es el de Wilder, sobre las velas de 15m, calculado al cierre de la vela de señal. Solo sirve para el buffer.
- Si la apertura de entrada ya queda al otro lado del stop, no se opera (`ENTRY_BEYOND_STOP`).

### 6. Objetivo
TP = entrada ∓ 2R, con R = |entrada − stop|. Orden límite. Sin trailing, sin break-even, sin parciales.

### 7. Gestión y salida por tiempo
- En velas de 15m. La vela de entrada cuenta entera, porque la entrada es en su apertura.
- Si una vela toca el stop y el objetivo, cuenta como pérdida.
- Si una vela abre más allá del stop (hueco), se sale en la apertura.
- **Salida por tiempo a las 12:00 de Londres:** al cierre de la última vela de 15m anterior a las 12:00 (la de las
  11:45), que es el precio disponible a las 12:00. Nunca queda nada abierto de un día para otro.

### 8. Tamaño
Igual que en los estudios anteriores:
- cuenta de 50.000 $ y riesgo del 0,5 % del saldo, con `position_sizing`;
- unidad: 1 oz, redondeando hacia abajo;
- si sale menos de 1 oz, no se opera (`POSITION_SIZE_BELOW_MINIMUM`).

## Costes (los mismos de GOLD_SWING_SIMPLE / MINIMAL; $ por onza)
| Escenario | Spread | Comisión | Deslizamiento adverso |
|---|---|---|---|
| A | 0 | 0 | 0 |
| B | 0,30 | 0,07 | 0 |
| C | 0,30 | 0,07 | 0,10 en la entrada y 0,30 en las salidas a mercado (stop **y salida por tiempo**) |

El objetivo (límite) nunca lleva deslizamiento. Esta versión tiene salida por tiempo, que las anteriores no tenían: es
una orden a mercado, así que en C lleva el mismo deslizamiento que el stop.

## Periodo
- **Desarrollo (70 %):** sesiones del 2-ene-2015 al 21-mar-2023 (`config/particion.json`).
- **Fuera de muestra (30 %):** desde el 22-mar-2023. **Bloqueado.** No se ejecuta en esta fase, ni siquiera si el
  desarrollo cumple los criterios: esa decisión es del usuario.

## Criterios (fijados antes de ejecutar)
**Para considerar que el desarrollo es prometedor**, con el escenario B deben cumplirse todos:
- al menos 100 operaciones (si hay menos: `INSUFFICIENT_SAMPLE`);
- PF > 1;
- R medio > 0 con t ≥ 2.

t ≥ 2 es necesario, no suficiente: el proyecto ha probado muchas hipótesis, varias en esta misma franja de Londres en
el oro.

## Registro y diagnóstico (no filtran nada en v1.0)
**Por operación:**
- rango en $ y en % del precio;
- distancia del stop;
- profundidad de la ruptura (`high − RH` en SHORT, `RL − low` en LONG) y profundidad / rango;
- MAE y MFE.

**Por día:** RH, RL, rango en $ y en %, primer extremo atacado, hora y profundidad de la falsa ruptura, y resultado.

**Diagnóstico (solo descriptivo):**
- SHORT (falsa ruptura del HIGH) frente a LONG (falsa ruptura del LOW);
- resultado por quintiles del rango (%) y de la profundidad / rango, y tabla cruzada rango × profundidad;
- por hora de la señal y por año;
- sensibilidad cambiando un parámetro cada vez: TP de 1,5R y de 2,5R, y buffer 0.

Ninguna de estas cifras cambia la v1.0.

## Posibles fuentes de sesgo
1. Conocimiento previo de esta franja y este rango (ver arriba).
2. GC en lugar de XAUUSD al contado.
3. Velas de 15m: la ambigüedad dentro de la vela se resuelve siempre en contra.
4. Stops cortos (una sola vela de 15m): los costes pesarán en R. Por eso se informa también sin costes.
5. Las interpretaciones del punto 3 ("primer break", ruptura real que gasta el extremo, vela que ataca los dos lados)
   son mías, fijadas aquí antes de ver datos.
