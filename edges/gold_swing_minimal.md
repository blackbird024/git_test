# GOLD_SWING_MINIMAL_v1.0: continuación de tendencia en el oro (4H EMA 50 → 1H retroceso + recuperación → 2R)

*Ficha escrita el 29-sep-2026, ANTES de programar y de ejecutar. Reglas de la especificación del usuario. Donde admiten
más de una lectura, se fija aquí UNA interpretación mecánica, que no se cambia después de ver resultados. Cualquier
cambio será GOLD_SWING_MINIMAL_v1.1.*

## Pregunta
¿Una continuación de tendencia extremadamente simple en el oro tiene ventaja suficiente para seguir investigándola?
Además: ¿simplificar sube de verdad la frecuencia? GOLD_SWING_SIMPLE_v1.0 dio 41 operaciones en 8 años.

## Hipótesis y racional
- El oro tiene tendencias persistentes en horizontes de días (flujos de bancos centrales, ETF y macro).
- En una tendencia, un retroceso corto de 1H seguido de una vela que supera el máximo de la anterior indica que el
  retroceso terminó.
- Entrar ahí con el stop bajo el retroceso daría más de 1 acierto de cada 3 a 2R.
- Conocimiento previo: en este proyecto el seguimiento de tendencia en GC (AQR, diario) y los cruces de medias no
  tuvieron ventaja. Esta es otra escala temporal y otra forma de entrar, pero la familia "tendencia en el oro" no es
  nueva.

## Datos
Futuros GC (Databento) con el mismo ajuste hacia atrás por cambios de contrato que GOLD_SWING_SIMPLE_v1.0
(`ajustar_rolls`). Velas de 1H (reloj UTC) y de 4H (sesión de CME), construidas desde 1M. Nada de 15m ni inferior.
Cada vela se usa desde su cierre nominal.

## Reglas exactas (v1.0)

### 1. Dirección 4H
- EMA 50 de los cierres de 4H: exponencial estándar, α = 2/51, que empieza en el primer cierre. Se calcula solo con
  velas cerradas.
- En cada instante t se mira la **última vela 4H cerrada**:
  - cierre > EMA → LARGO;
  - cierre < EMA → CORTO;
  - cierre = EMA → sin dirección.
- Las primeras 50 velas 4H (calentamiento de la EMA) no generan dirección.

### 2. Retroceso y señal (en 1H; la dirección se evalúa al cierre de cada vela 1H)
- **LARGO:**
  - Vela de retroceso: con dirección LARGO, una vela 1H cierra por debajo del cierre de la vela anterior.
  - Vela de señal: después, una vela 1H cierra por encima del **máximo de la vela inmediatamente anterior** (sea el
    retroceso u otra).
- **CORTO:** simétrico. Retroceso = cierre por encima del cierre anterior; señal = cierre por debajo del mínimo de la
  vela anterior.
- Una vela de señal nunca es a la vez un retroceso, porque su cierre supera el máximo anterior y, por tanto, el cierre
  anterior.

### 3. Reinicio y caducidad (interpretación fijada)
- Si antes de la señal aparece **otra vela de retroceso**, el setup se reinicia: esa vela pasa a ser el retroceso
  (stop y ventana nuevos).
- La señal tiene que llegar en las **5 velas 1H siguientes** al retroceso vigente. Si no, el setup se cancela y se
  vuelve a esperar un retroceso.
- Si la dirección 4H cambia (o deja de existir) mientras hay un setup abierto, se cancela.
- La señal exige que la dirección 4H, al cierre de la vela de señal, sea la del setup.

### 4. Entrada
"Al cierre de la vela de señal": el cierre solo se conoce cuando la vela termina, así que el primer precio operable es
la **apertura de la vela 1H siguiente**. Se entra a mercado en esa apertura. Es la regla estándar del proyecto y evita
suponer un llenado exacto en el cierre.

### 5. Stop
- **LARGO:** mínimo de la vela de retroceso vigente − 0,10 × ATR(14) de 1H.
- **CORTO:** máximo + 0,10 × ATR(14).
- El ATR es el de Wilder, al cierre de la vela de señal.
- Si la entrada queda al otro lado del stop (por un hueco), no se opera (`ENTRY_BEYOND_STOP`).

### 6. Objetivo
TP = entrada ± 2R, con R = |entrada − stop|. Orden límite. Sin trailing, sin break-even, sin parciales y sin cambios.

### 7. Gestión
- Velas de 1H. La vela de entrada cuenta entera, porque la entrada es en su apertura.
- Si una vela toca el stop y el objetivo, cuenta como pérdida.
- Si una vela abre más allá del stop (hueco), se sale en la apertura.
- Solo se sale por SL o TP. Al final de los datos, al último precio (`END_OF_DATA`).
- **Una sola operación abierta:**
  - mientras está abierta, las señales se ignoran (`IGNORED_TRADE_OPEN`, registradas en el archivo de señales);
  - al cerrarla, la búsqueda de setups empieza de cero en la vela siguiente a la de salida.
- Sin límite de operaciones por día ni filtros horarios.

### 8. Tamaño
Igual que en GOLD_SWING_SIMPLE_v1.0:
- cuenta de 50.000 $ y riesgo del 0,5 % del saldo, con `position_sizing`;
- unidad: 1 oz, redondeando hacia abajo;
- si sale menos de 1 oz, no se opera (`POSITION_SIZE_BELOW_MINIMUM`).

## Costes (exactamente los de GOLD_SWING_SIMPLE_v1.0; $ por onza)
| Escenario | Spread | Comisión | Deslizamiento adverso |
|---|---|---|---|
| A | 0 | 0 | 0 |
| B | 0,30 | 0,07 | 0 |
| C | 0,30 | 0,07 | 0,10 en la entrada y 0,30 en las salidas por stop |

El objetivo (límite) nunca lleva deslizamiento.

## Parámetros oficiales
EMA 50 en 4H, TP 2R, buffer de 0,10 × ATR(14) de 1H y ventana de 5 velas.

## Periodo
- **Desarrollo (70 %):** sesiones de CME del 2-ene-2015 al 21-mar-2023.
- **Fuera de muestra (30 %):** desde el 22-mar-2023. **Bloqueado**: solo se ejecuta si el desarrollo cumple los
  criterios.

## Criterios (fijados antes de ejecutar)
Para ejecutar el fuera de muestra, con el escenario B deben cumplirse todos:
- al menos 100 operaciones (si hay menos: `INSUFFICIENT_SAMPLE`);
- PF > 1;
- R medio > 0 con t ≥ 2.

t ≥ 2 es necesario, no suficiente. Si falla: se registra y no se toca nada.

**Frecuencia:** se informa del total de operaciones y de las operaciones por año, comparadas con las 41 (unas 5 al año)
de GOLD_SWING_SIMPLE_v1.0.

**Sensibilidad (solo diagnóstico, en desarrollo):**
- EMA de 20, 50 y 100 por TP de 1,5R, 2R y 2,5R (9 combinaciones) × escenarios A, B y C.
- Se reportan todas. La oficial sigue siendo EMA 50 con TP 2R.

## Posibles fuentes de sesgo
1. Conocimiento previo de la familia "tendencia en el oro" (ver arriba).
2. GC en lugar de XAUUSD al contado; ajuste por cambios de contrato.
3. Velas de 1H: la ambigüedad dentro de la vela se resuelve siempre en contra (misma vela = pérdida).
4. Stops cortos (el retroceso de una sola vela): los costes pesarán mucho en R. Por eso se informa también sin costes.
5. Las interpretaciones de los puntos 3 y 4 son mías, fijadas aquí antes de ver datos.

## Resultado del desarrollo (2-ene-2015 → 21-mar-2023): añadido tras ejecutar
Informe: `reports/GOLD_SWING_MINIMAL_v1.0/`. Auditoría de look-ahead: OK en las 2.337 operaciones.

| v1.0 (EMA 50, 2R) | A (sin costes) | B (realistas) | C (+ deslizamiento) |
|---|---|---|---|
| Operaciones (al año) | 2.337 (284,5) | 2.337 (284,5) | 2.407 (293,1) |
| Acierto | 33,2 % | 33,2 % | 33,1 % |
| Profit factor | 0,98 | 0,82 | 0,71 |
| R medio (t) | −0,007 (−0,24) | −0,121 (−4,09) | −0,215 (−7,00) |

- **Frecuencia:** ×57 respecto a GOLD_SWING_SIMPLE_v1.0 (41 → 2.337). La muestra ya no es el problema.
- **Sin ventaja ni antes de costes:** el acierto del 33,2 % es exactamente el punto de equilibrio de 2R, lo que daría el
  azar. Con costes pierde de forma significativa, porque el stop mediano es de 4 $/oz y los costes cuestan ~0,11 R por
  operación.
- **Sensibilidad (diagnóstico):** las 9 combinaciones de EMA y TP dan R sin costes entre −0,007 y +0,026 (|t| < 1),
  y todas pierden con costes (t ≤ −2,4).
- **Veredicto: RECHAZADA en el desarrollo.** El fuera de muestra no se ejecuta y las reglas no se tocan.
