# MNQ_ORB_RETEST_v1.0 · especificación congelada

Reglas congeladas el 2026-10-17 (hash de reglas `51bd2fc16336f433`, código `70fc2a4`, ver `FREEZE.json`) después de ver
SOLO desarrollo y validación. La prueba 2025-2026 se abrió una vez con estas reglas. Cualquier cambio de reglas crea
otra versión, y para ella la prueba 2025-2026 ya no es independiente.

## Mercado y datos
- MNQ (Micro E-mini Nasdaq-100), simulado con precios de NQ.c.0 1 min de Databento (mismo subyacente y rejilla de 0,25).
- Hora de Nueva York (America/New_York), con cambios de horario, festivos y medias jornadas del calendario XNYS.
- Minuto de sesión k = 0 es la vela de 1 min que empieza a las 9:30:00 ET.

## Rango de apertura
- ORH / ORL = máximo / mínimo de las velas de 1 min de 9:30:00 a 9:44:59 (minutos 0-14). Utilizables desde las 9:45.
- Si hay menos de 14 de esos 15 minutos con datos, o falta la vela de 9:30, no se opera ("rango_incompleto").

## Ruptura (velas de 5 min alineadas a 9:30, construidas solo con sus propias velas de 1 min)
- Primera vela de 5 min completa, desde la de 9:45, con cierre > ORH (largo) o cierre < ORL (corto).
- Una mecha fuera del rango sin cierre fuera no es ruptura. Solo cuenta la primera ruptura del día.

## Retesteo y confirmación (en las 3 velas de 5 min siguientes a la ruptura)
Largo: la primera vela que cumple a la vez
- mínimo ≤ ORH + 2 ticks (vuelve a la zona),
- mínimo ≥ ORH − 2 ticks (no se hunde más de 2 ticks),
- cierre > ORH,
- cierre > apertura (alcista).

Corto: espejo con ORL (máximo entre ORL − 2 ticks y ORL + 2 ticks, cierre < ORL, cierre < apertura).

Si ninguna de las 3 velas cumple, se cancela el día. Una vela que no cumple no se valida después mirando velas posteriores.

## Entrada
- La señal existe al cierre de la vela de confirmación (minuto `signal_k`).
- Entrada a mercado en la APERTURA del primer minuto con operaciones ≥ `signal_k` (nunca al cierre de la vela de
  señal), con deslizamiento adverso.
- No se abre nada después de las 11:30 ET (entrada como muy tarde en el minuto 120).

## Stop, objetivo y salida
- SL largo = mínimo de la vela de retesteo − 1 tick; SL corto = máximo + 1 tick.
- Si la entrada ejecutada queda al otro lado del SL (o a distancia 0), se descarta la operación.
- R = |entrada ejecutada − SL|.
- TP = entrada ± 2R, redondeado a la rejilla de 0,25 en el sentido desfavorable (más lejos).
- Sin trailing, sin break-even, sin parciales.
- Cierre obligatorio a mercado a las 15:55 ET (5 min antes del cierre en medias jornadas).
- Máximo una operación por sesión.

## Ejecución (velas de 1 min)
- Stop: si la apertura de un minuto ya está más allá del SL, se sale en esa apertura (peor precio); si no, en el SL.
  En ambos casos con deslizamiento adverso.
- TP: orden límite; solo se llena si el precio cruza el nivel en 1 tick, sin deslizamiento. Si un hueco lo salta, se
  llena en el TP (no se cobra la mejora).
- Si SL y TP caben en el mismo minuto: SL primero (se cuenta como ambigua).

## Costes (configurables en `orb_retest/config.py`)
| Escenario | Comisión por lado | Desliz. entrada / stop / tiempo (ticks) |
|---|---|---|
| sin_costes | 0 | 0 / 0 / 0 |
| base | 1,00 USD | 1 / 1 / 1 |
| base_2t | 1,00 USD | 2 / 2 / 2 |
| proyecto_previo (CONFIG_COSTES.yaml) | 0,75 USD | 2 / 2 / 2 |
| estres | 1,50 USD | 3 / 4 / 3 |

No son las tarifas reales de ningún bróker: sustitúyelas por las de tu cuenta.

## Tamaño
- contratos = floor(presupuesto / pérdida estimada por contrato), con un máximo de 50.
- Pérdida estimada = (distancia del cierre de señal al SL + deslizamiento de entrada y de stop) × 2 USD + comisión
  ida y vuelta.
- Si no cabe un contrato, no se opera.
- Escenarios de 25, 50 y 100 USD; modo normalizado en R con 1 contrato.

## Particiones (config/PROTOCOLO.yaml, sin cambios)
- Desarrollo: 2018-01-01 → 2021-12-31.
- Validación: 2022-01-01 → 2024-12-31.
- Prueba: 2025-01-01 → 2026-10-02.

El esquema 2015-2021 / 2022-2024 / 2025-2026 del encargo no es posible porque los datos empiezan en 2018.
