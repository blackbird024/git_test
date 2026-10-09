# ORB 5 min · MNQ — Fase 1 (auditoría) y Fase 2 (plan técnico)

Fecha: 9 de octubre de 2026. Detalle completo en `reports/auditoria_datos.json`. Script: `data_audit.py` (solo lectura).

## 1. Proyecto existente

- Repositorio `git_test`, rama `claude/chat-session-olkab4`. Python 3.11.15 del sistema (sin entorno virtual en este contenedor).
- Librerías instaladas: pandas 3.0.6, numpy 2.4.6, numba 0.68, pyarrow 25, PyYAML 6.0.1, databento 0.87.
- No están instalados pytest, matplotlib ni ningún calendario de mercado. `exchange_calendars` sí se puede instalar con pip.
- `alpaca/` contiene ~100 scripts de investigación anteriores, incluidos varios ORB sobre NQ en velas de 5 min. Uno de ellos es `orb5_retesteo.py`, de ruptura + retesteo, que ya se ejecutó sobre estos mismos datos (ver §5).
- Este estudio vive en una carpeta nueva, `orb_mnq/`. No se modifica nada de `alpaca/` ni de `.lab_cache/`.
- **El Acer Nitro y sus datos de MNQ 2015-2026 no son accesibles desde este entorno.** Solo he auditado lo que existe aquí.

## 2. Datos disponibles (verificados)

| Archivo | Contenido | Granularidad | Cobertura (UTC) | Filas | Columnas |
|---|---|---|---|---|---|
| `alpaca/.lab_cache/databento_nq_1m_2018_2024.pkl` | NQ.c.0 (E-mini, no micro) | 1 min | 2018-01-01 23:00 → 2024-09-30 23:59 | 2.353.165 | rtype, publisher_id, instrument_id, OHLC, volume, symbol |
| `alpaca/.lab_cache/databento_glbx_1m.pkl` | NQ.c.0 (+ ES, GC) | 1 min | 2024-10-01 00:00 → 2026-10-02 20:59 | 702.979 (NQ) | ídem |
| `alpaca/.lab_cache/dbn_NQ_5m.pkl` | NQ, ya agregado | 5 min | 2018-01-01 → 2026-10-02 | 614.269 | OHLC (sin volumen) |

- **Proveedor:** Databento, dataset GLBX.MDP3, esquema `ohlcv-1m`. Las velas se construyen con operaciones, no con bid/ask.
- **Zona horaria:** índice en UTC en los archivos de 1 min, y en America/New_York en el de 5 min.
- **Calidad:** índice ordenado, 0 timestamps duplicados, 0 NaN, 0 velas incoherentes y todos los precios múltiplos de 0,25. Los dos archivos de 1 min no se solapan y se pueden unir sin conflictos.
- **Sesiones con datos 9:30-16:00 NY:** 2.224 (1.715 + 509). 2.139 completas (390 velas de 1 min).
- **Sesiones incompletas: 85.**
  - 59 son festivos de EE. UU. (cerrado en NYSE) en los que el Globex opera hasta las 13:00; tienen ~210 velas.
  - 18 son medias jornadas (cierre anticipado, ~225 velas): 3 de julio, viernes después de Acción de Gracias, 24 de diciembre.
  - 8 tienen huecos de minutos sin operaciones (por ejemplo, marzo de 2020).
- **Ventana crítica 9:30-11:30:** de 2.224 sesiones, solo 4 tienen menos de 120 velas. En total faltan 160 velas de 1 min.
  - Ojo: Databento **no emite velas en minutos sin operaciones**. Una vela ausente significa que no hubo operaciones en ese minuto, no un error de datos.
- **No hay:** ticks, bid/ask, profundidad de mercado ni datos del contrato MNQ.

## 3. Construcción del contrato continuo (limitación importante)

- `NQ.c.0` = contrato más cercano a vencimiento ("calendar"). Hay 35 cambios de contrato detectados por `instrument_id`, siempre el domingo **después** del vencimiento trimestral.
- Consecuencia: durante la semana del vencimiento, la serie sigue en el contrato que vence, cuando la liquidez ya se ha pasado al siguiente.
  - **El volumen en esa semana es el 24 % del normal** (mediana; mínimo 14 %).
  - Son ~5 sesiones por trimestre, unas 20 al año (~8 % de las sesiones), con precios de un contrato poco líquido que no es el que se operaría.
- Los precios no están ajustados por rollover. Para un ORB intradía no afecta a la señal, pero sí a cualquier indicador que cruce días, como el ATR.

## 4. MNQ frente a NQ

- **MNQ empezó a cotizar el 6 de mayo de 2019.** No pueden existir datos de MNQ desde 2015; si en el Acer hay datos desde 2015, son de otro contrato (probablemente NQ). Hay que comprobarlo.
- MNQ y NQ tienen el mismo precio (mismo índice subyacente, mismo tick de 0,25). La diferencia es el multiplicador: 2 $ frente a 20 $ por punto.
- Usaré los precios de NQ como base y el valor de MNQ (2 $/punto) para los resultados. La liquidez de MNQ es menor, y eso se cubrirá con los escenarios de slippage, no con los datos.

## 5. Problema de honestidad metodológica: los datos ya están "vistos"

- En esta misma conversación ya probé muchas variantes de ORB sobre estos datos, de 2018 a 2026. Entre ellas, **la ruptura + retesteo (`alpaca/orb5_retesteo.py`), con resultado negativo**: ninguna de sus 24 variantes ganaba en los dos periodos.
- Por tanto, **ningún periodo de 2018-2026 es realmente "fuera de muestra"** para esta familia de estrategias. La partición cronológica sigue siendo útil para medir estabilidad, pero la única prueba verdaderamente independiente será el **forward test**: simulación desde hoy con datos nuevos.
- Aquella prueba anterior **no** coincide con tu especificación: usaba velas de 5 min y no tenía la tolerancia de 2 ticks, la confirmación con cierre, el SL en la vela de retesteo, la salida a las 11:30 ni el objetivo de 2R. Así que no la doy por concluyente.

## 6. Plan técnico (Fase 2)

**Partición propuesta**, ya que los datos empiezan en enero de 2018 y no en 2015. La fijo **antes** de ver los resultados:

| Periodo | Fechas | Uso |
|---|---|---|
| Desarrollo | 2018-01-02 → 2021-12-31 | Estrategia base y variantes |
| Validación | 2022-01-01 → 2024-12-31 | Comparar variantes sin tocar las reglas |
| Prueba final | 2025-01-01 → 2026-10-02 | Una sola evaluación al final |
| Forward | desde hoy | La única prueba realmente nueva |

**Criterios de decisión, fijados de antemano:**
- **A (prometedora):** esperanza neta > 0 en validación **y** en prueba final con el escenario de 2 ticks; intervalo bootstrap al 90 % de la esperanza por operación de todo 2022-2026 por encima de 0; ningún año civil con pérdida superior al 50 % de la ganancia del mejor año; probabilidad de tocar el límite de Topstep en la simulación < 20 %.
- **B (insuficiente):** positiva pero con el intervalo incluyendo 0, o menos de 100 operaciones en 2022-2026.
- **C (sin ventaja):** esperanza neta ≤ 0 con 1 tick de slippage en validación o en prueba final.
- **D (incompatible con Topstep):** cumple A o B, pero la probabilidad de incumplir las reglas es ≥ 20 %.

**Convenciones que fijaré** (en `config.yaml` y en tests):
- **Rango:** vela 09:30:00-09:34:59 ET, construida con las 5 velas de 1 min de 9:30 a 9:34.
- **Velas de señal:** 5 min alineadas a 9:35, 9:40, … construidas desde las de 1 min. La entrada es la apertura del primer minuto de la vela siguiente, y la gestión se hace con velas de 1 min.
- **Ventana de retesteo:** las 3 velas **posteriores** a la vela de ruptura (sin incluirla). Una vela de retesteo es la que toca ORH + 2 ticks o menos, y su cierre > ORH confirma la señal. La vela de ruptura no puede ser también la de retesteo.
- **Invalidación:** un cierre dentro del rango antes de confirmar invalida la configuración. Una ruptura en la dirección contraria antes de entrar cancela el día.
- **Orden de llegada dentro de un minuto:** si SL y TP caben en la misma vela de 1 min, cuenta el SL primero (conservador). Lo cuantificaré.
- **Huecos:** si la apertura de entrada ya está más allá del SL, se cancela. Si el precio salta más allá del SL, se ejecuta al precio de apertura, no al nivel del SL.
- **Calendario:** con `exchange_calendars` (XNYS). Se excluyen los festivos y se marcan las medias jornadas. Las semanas de rollover se analizan dentro y fuera del estudio.
- **Costes:** parámetros editables. Escenarios A/B/C con 1/2/3 ticks de slippage por ejecución (entrada y salida) + comisión + tasas.
- **Módulos** en `orb_mnq/`: `data_audit.py`, `session_calendar.py`, `orb_strategy.py`, `execution_simulator.py`, `cost_model.py`, `risk_engine.py`, `topstep_rules.py`, `backtest.py`, `statistics.py`, `report.py`, `config.yaml`, `tests/`.

## 7. Lo que falta o necesito confirmar

1. **Comisión y tasas reales de MNQ en tu cuenta de Topstep** (por contrato y por lado). Tu captura mostraba "Commis. 2,50 $" y "Fees 3,60 $" por fila, pero sin el número de contratos no puedo deducir el coste unitario.
2. **Tipo de cuenta:** tu panel dice "50K DLL COMBINE": objetivo 3.000 $, límite 49.561,70 $ y consistencia con mejor día < 55 % del objetivo. Faltan por confirmar:
   - El valor del Daily Loss Limit.
   - El máximo de contratos permitido.
   - Si el MLL se calcula con el saldo intradía o con el de cierre.
3. **Reglas oficiales de Topstep y especificaciones de CME:** este entorno **bloquea el acceso** a `help.topstep.com` y `cmegroup.com`, así que no las puedo verificar en la fuente oficial. Dejaré esos parámetros como "pendiente de confirmación" salvo que me pegues el texto oficial o una captura.
4. **Autorización para instalar** `exchange_calendars`, `pytest` y `matplotlib` con pip, solo en este contenedor.
5. **Opcional, con coste:** comprar NQ en 1 min con continuo por volumen (`NQ.v.0`, ~11 $ en Databento), para que las semanas de vencimiento usen el contrato líquido. Si no, las semanas de rollover se excluirán como análisis de sensibilidad.
6. **Opcional:** subir aquí los datos del Acer, si quieres usarlos en lugar de los de este entorno.
