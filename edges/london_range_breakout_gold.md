# London Range Breakout en el oro (MGC)

*Ficha escrita el 29-sep-2026, ANTES de ejecutar ningún backtest de esta hipótesis. Hipótesis NUEVA en el proyecto.*

## Hipótesis
Después de formarse un rango en la primera hora de la sesión de Londres, una ruptura **confirmada por cierre**
de ese rango tiende a continuar en la dirección de la ruptura durante el resto de la sesión europea.

## Racional de mercado
- Londres es el mayor centro de negociación de oro físico y OTC del mundo. En su apertura entra el flujo
  institucional europeo (bancos de lingotes, fondos, coberturas de productores y consumidores).
- La primera hora concentra la "búsqueda de precio": el rango de esa hora es el acuerdo inicial del mercado.
- Si el precio lo abandona con un cierre fuera, indicaría un desequilibrio de órdenes que no se ha agotado.
  Los grandes participantes ejecutan en tramos a lo largo del día (algoritmos TWAP/VWAP), lo que alimentaría
  la continuación.

## Definición exacta de cada regla

### Datos y horas (sin conversiones implícitas)
| Elemento | Valor |
|---|---|
| Zona horaria de los datos | **UTC**. Cada vela de 1 minuto lleva la hora de su **inicio** |
| Zona de las reglas | **Europe/London**, convertida a UTC vela a vela (estable ante el cambio de hora) |
| Sesión de Londres | Desde las **08:00** hasta las **16:30** hora de Londres (cierre de la sesión de contado de la Bolsa de Londres) |
| Formación del rango | Velas que empiezan entre las **08:00 y las 08:59** de Londres (60 velas). En UTC: **08:00-08:59 en invierno (GMT)** y **07:00-07:59 en verano (BST)**. En Italia es siempre **09:00-09:59** |
| Entradas permitidas | Señal = cierre de una vela que empieza entre las **09:00 y las 16:28** de Londres. La entrada es en la apertura de la vela siguiente, así que la última entrada posible es a las 16:29 |
| Cierre de posiciones | **16:30** de Londres (16:30 UTC en invierno, 15:30 UTC en verano; 17:30 en Italia), en la apertura de la vela de las 16:30 |

Por qué 16:30: el proyecto no tenía definido un cierre de Londres (la única referencia era el cierre a las
12:00 de Italia de otra estrategia). Se elige el cierre convencional de la sesión europea. Europa y Reino
Unido cambian de hora el mismo día, así que la relación Londres-Italia es siempre de 1 hora. La apertura de
Nueva York (14:30 de Londres casi todo el año, 13:30 en las semanas de desajuste de marzo y
octubre/noviembre) cae dentro de la ventana. No afecta a las reglas, pero si hay una salida en esos minutos
el deslizamiento estándar es de 2 ticks.

### Rango
- `range_high` = máximo de las 60 velas del rango; `range_low` = mínimo. Se fijan a las 09:00 de Londres y no
  cambian en todo el día.
- Día válido: al menos 50 de las 60 velas del rango presentes (en el oro de madrugada puede faltar algún minuto
  sin negociación). Si hay menos, no se opera ese día.

### Entrada
- LARGO: la primera vela de 1 minuto (en la ventana de entradas) cuyo **cierre > range_high** (estrictamente).
- CORTO: la primera vela de 1 minuto cuyo **cierre < range_low** (estrictamente).
- Que una vela toque el rango con la mecha no cuenta: hace falta el cierre fuera.
- Entrada en la **apertura de la vela siguiente** (motor estándar del proyecto).
- **Máximo 1 operación al día en total**: la primera ruptura confirmada, en cualquier sentido. Después, no se
  entra más ese día.

### Stop y objetivo
- LARGO: stop = `range_low`. CORTO: stop = `range_high`. Sin ATR, sin swings, sin filtros.
- R = distancia entre el **precio de entrada real** (apertura siguiente con deslizamiento) y el stop.
- Objetivo = entrada ± **2R**.
- Si el stop y el objetivo caen en la misma vela, cuenta como pérdida (motor estándar).
- Si no se toca ninguno: salida por tiempo a las 16:30 de Londres.

### Tamaño
- **1 MGC fijo** en todas las operaciones. Motivo: con un riesgo fijo en dólares, los días de rango muy ancho
  (R grande) no admitirían ni un contrato y se descartarían, lo que sesgaría la muestra. Con 1 contrato se
  prueban TODAS las rupturas. El resultado se da también en R, que no depende del tamaño.

## Parámetros (fijos en esta fase; no se optimizan)
| Parámetro | Valor |
|---|---|
| Duración del rango | 60 minutos (08:00-09:00 Londres) |
| Objetivo | 2R |
| Cierre de la ventana | 16:30 Londres |

## Costes (modelo estándar del proyecto, sin cambios)
- Comisión: 1 $ por contrato y lado.
- Deslizamiento: 1 tick (0,10 $) por lado en entradas, stops y salida por tiempo; 2 ticks en las aperturas de
  Londres (07:50-08:10 Londres, fuera de la ventana de entradas), de Nueva York (09:25-09:45 NY) y de Globex.
  El objetivo es una orden límite, sin deslizamiento. No hay spread aparte: lo cubre el deslizamiento.
- Se informará **antes y después de costes**.

## Periodo
- Desarrollo: sesiones del **2-ene-2015 al 21-mar-2023** (70 %, `config/particion.json`).
- Fuera de muestra: desde el **22-mar-2023** (30 %). **No se carga ni se mira en esta fase.**
- Se excluyen las sesiones ilíquidas previsibles (regla causal del proyecto).

## Criterios de aceptación / rechazo
**Paso 1 (esta fase, solo desarrollo)** — pasa al paso 2 solo si, **después de costes**:
1. profit factor > 1, y
2. R medio > 0 con estadístico **t ≥ 2** (listón reforzado: el proyecto ya ha probado muchas hipótesis y el
   riesgo de encontrar una ventaja por casualidad es alto).
Si no se cumplen: **rechazada**, sin intentar salvarla con filtros.

**Paso 3 (si llega)** — criterios estándar del proyecto: PF fuera de muestra ≥ 1,3 con ≥ 100 operaciones en total;
fuera de muestra no peor que el 50 % del desarrollo; sensibilidad ±20 % rentable; otro mercado parecido (euro,
6E: requiere comprar sus datos); costes duplicados rentable; Monte Carlo de 1.000 simulaciones.

## Posibles fuentes de sesgo
1. **Conocimiento previo (el más importante):** en este proyecto ya probé el setup CONTRARIO (barrido de niveles
   de Asia y del día anterior en la apertura de Londres, apostando al giro) y no tuvo ventaja ni antes de costes
   (PF 0,99). Eso sugiere que en esas horas el oro no gira de forma sistemática, pero no dice si continúa: los
   niveles, la ventana y el disparo son distintos. Las reglas de esta ficha vienen de la especificación del
   usuario y no se han ajustado con ese resultado.
2. **Deslizamiento optimista en rupturas:** justo al romper un rango el precio se mueve rápido; 1 tick puede quedarse
   corto. Se probará con costes duplicados en el paso 3.
3. **Contrato continuo:** el contrato continuo de GC por volumen cambia de vencimiento con retraso. Se excluyen las
   sesiones ilíquidas previsibles. Una operación intradía nunca cruza un cambio de contrato.
4. **Velas de 1 minuto:** no se sabe qué ocurrió primero dentro de una vela; si se tocan stop y objetivo, pérdida
   (conservador).
5. **Minutos sin negociación:** en el oro faltan minutos sueltos. La entrada es en la siguiente vela existente, que
   puede ser algo más tarde que "el minuto siguiente".
6. **Elección del cierre (16:30):** la hora de cierre es una decisión mía, documentada aquí antes de ver resultados.
   No se cambiará después según el resultado.
7. **Tamaño fijo de 1 contrato:** en dólares, los años con precio del oro más alto pesan más. Por eso se reportan
   también las métricas en R.
