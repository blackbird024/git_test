# ORB 1h + estructura 1h + entrada 5m

Backtest reproducible de una estrategia de ruptura del rango de la primera hora (ORB) en futuros micro (MNQ, MES), con filtro de estructura de 1 hora y entrada por retesteo en velas de 5 minutos.

**Importante:** que las pruebas de software pasen no demuestra que la estrategia sea rentable. Los resultados con datos reales están en `results/` y son **negativos**.

## Instalación y uso (desde la raíz del repositorio)

```bash
pip install pandas numpy pyyaml matplotlib pytest exchange_calendars   # Python 3.11
python -m orb_backtest synthetic                                       # dataset SINTÉTICO de demostración
python -m orb_backtest test                                            # 30 pruebas (unitarias + integración)
python orb_backtest/tools/export_databento_csv.py                      # NQ/ES 5 min de la caché local → CSV (no descarga nada)
python -m orb_backtest --config orb_backtest/configs/mnq.yaml validate # valida los datos sin ejecutar el backtest
python -m orb_backtest --config orb_backtest/configs/mnq.yaml run      # backtest + informe en orb_backtest/output/
python -m orb_backtest --config orb_backtest/configs/mes.yaml run
```

- `report` es un alias de `run`: el informe se genera siempre al ejecutar.
- Códigos de salida:
  - 0: correcto.
  - 1: configuración inválida.
  - 2: datos inválidos.
  - 3: error de ejecución.
  - 4: pruebas fallidas.

## Archivos

| Archivo | Función |
|---|---|
| `config.py` | Carga y valida el YAML: instrumento, costes, estrategia, riesgo, fechas, partición y semilla |
| `configs/instruments.yaml` | Tick, valor del tick y del punto de MNQ y MES (sin verificar en CME) |
| `configs/config.example.yaml`, `mnq.yaml`, `mes.yaml` | Configuración de ejemplo (sintética) y real |
| `data_io.py` | Proveedor CSV y validación: duplicados, orden, OHLC, zona horaria, rejilla de ticks, saltos, velas ausentes |
| `bars.py` | Sesiones en America/New_York (IANA), calendario XNYS (festivos y medias jornadas) y velas de 1 h |
| `structure.py` | Pivotes 2/2 confirmados y sesgo de 1 h |
| `engine.py` | Rango ORB, señal (ruptura + retesteo), tamaño, simulación vela a vela, costes y registro |
| `stats.py` | Métricas, desgloses, bootstrap y partición 60/20/20 |
| `pipeline.py` | Orquestación, variantes (con/sin filtro), estrés de costes, sensibilidad y manifiesto |
| `report.py` | CSV, gráficos (matplotlib) e `INFORME.md` |
| `synthetic.py` | Generador del dataset SINTÉTICO (paseo aleatorio, semilla fija) |
| `tools/export_databento_csv.py` | Exporta las velas de Databento ya descargadas al esquema CSV |
| `data/PLANTILLA.csv` | Plantilla del esquema CSV |
| `tests/` | Pruebas con fixtures sintéticas de resultado conocido |
| `results/MNQ`, `results/MES` | Informes, operaciones, sesiones, resumen, bootstrap, gráficos y manifiesto de las ejecuciones reales |

## Otras sesiones e instrumentos

- **Londres:**
  - Configuraciones `configs/{mnq,mes}_london_cierre_{1425,1625}.yaml` y `configs/mgc_london.yaml`.
  - Usan `timezone: Europe/London` y `calendar: XLON`.
  - Rango 8:00–9:00, entradas hasta las 13:00 y cierre obligatorio a las 14:25 o a las 16:25, hora de Londres.
  - Las velas de 1 h siguen el reloj de Londres; el sesgo se fija a las 8:00 de Londres.
- **Oro:**
  - MGC (tick 0,10, 1 USD por tick).
  - Datos GC: `GC.v.0`, continuo por volumen.
  - Configuraciones `mgc_london.yaml` y `mgc_ny.yaml`.
- `calendar: null` desactiva el calendario de bolsa.

## Esquema del CSV

```
timestamp,open,high,low,close[,volume][,contract]
```

- **timestamp:** ISO 8601 con desplazamiento explícito (`2024-03-11T09:30:00-04:00` o `...Z`). Las marcas sin zona se rechazan.
- **Marca:** es la **apertura** de la vela.
- **Duración:** velas de `bar_minutes` (5).
- **Precios:** en puntos del índice.

## Decisiones técnicas (las no especificadas se resolvieron de forma conservadora)

1. **Sesiones:**
   - Velas que abren en [09:30, 16:00) en Nueva York, con la zona IANA (el cambio de horario lo gestiona tzdata).
   - Los festivos de la NYSE con Globex abierto se marcan como inválidos.
   - En medias jornadas, el cierre obligatorio es 5 minutos antes del cierre anticipado.
2. **Rango:**
   - Las 12 velas que abren en [09:30, 10:30). Si falta alguna, la sesión es inválida y se registra el motivo.
   - Solo se usa a partir del cierre de la vela de 10:25.
3. **Velas de 1 h:**
   - Horas en punto de Nueva York, con todas las velas de 5 minutos, incluida la sesión nocturna.
   - Necesitan al menos 6 de 12 velas de 5 minutos.
   - Se usan desde su cierre. La vela 9:00–10:00 está abierta a las 9:30, así que **no** participa en el sesgo.
4. **Pivotes:**
   - Estrictos 2/2.
   - Confirmados al cierre de la segunda vela posterior.
   - El sesgo se fija a las 9:30 para toda la sesión.
5. **Retesteo:**
   - |mínimo − OR_high| ≤ 2 ticks (lectura literal de "distancia máxima de dos ticks"; acepta tocar o atravesar el nivel hasta 2 ticks).
   - En las 3 velas posteriores a la de ruptura.
   - Cierre estrictamente por encima del nivel.
6. **Rupturas:**
   - Un cierre de vuelta dentro del rango invalida la ruptura.
   - Tras una ruptura fallida, otra ruptura exige antes un cierre dentro del rango (no se persigue el precio).
   - Un cierre al otro lado del rango descarta la ruptura y solo cuenta como ruptura contraria si el sesgo la permite.
7. **Hora límite de entrada:** 15:00. Lo es la vela de entrada, no la señal. Es configurable.
8. **Ejecución** (solo velas de 5 minutos, así que el orden dentro de la vela es desconocido):
   - Entrada en la apertura de la vela siguiente + slippage.
   - Stop: si la vela abre más allá, sale en la apertura (hueco); si no, en el stop. Siempre con slippage.
   - Objetivo límite: solo se llena si se supera en 1 tick. Si la vela abre más allá, se llena en la apertura.
   - Stop y objetivo en la misma vela: cuenta primero el stop.
   - Cierre obligatorio a las 15:55 a mercado.
9. **Tamaño:**
   - Se calcula al cierre del retesteo, con el precio estimado = cierre + slippage. Incluye la distancia al stop, las comisiones de ida y vuelta y el slippage de salida.
   - `floor()`, nunca hacia arriba. Con 0 contratos no se opera.
   - Si la apertura real se aleja, el riesgo real puede superar el presupuesto. Ocurre en el 23 % (MNQ) y el 16 % (MES) de las operaciones; queda registrado en `warnings`.
10. **R:** neto / (contratos × |entrada − stop| × valor del punto). Los costes no están en el denominador.
11. **Profit factor:** "infinito" sin pérdidas y "no definido" sin operaciones.
12. **Drawdown:** sobre el capital al cierre de cada operación.

## Datos y limitaciones

- **Fuente:**
  - NQ: Databento `NQ.c.0`, continuo por calendario, **sin ajuste de rollover**, en 5 minutos (construidas desde velas de 1 minuto), de enero de 2018 a octubre de 2026.
  - ES: archivo de una descarga anterior; se **supone** el mismo método, sin verificar.
  - Precios de NQ y ES usados como MNQ y MES (mismo subyacente y tick).
  - MNQ y MES cotizan desde mayo de 2019.
- **Contrato continuo sin ajuste:**
  - Los saltos de cada vencimiento pueden crear pivotes horarios falsos alrededor del rollover (unos 35 en el periodo).
  - La semana de vencimiento usa el contrato que expira, con menos liquidez.
- **Hueco de datos:** del viernes 20 de marzo de 2020 a las 9:25 al domingo 22 de marzo. La sesión del 20 queda inválida.
- **Sin volumen ni datos de mayor resolución** en el CSV: no se puede resolver el orden dentro de la vela.
- **Comisión de 0,62 USD por lado:** supuesto **no verificado**. No es una estimación exacta de rentabilidad real.
- **Contaminación de datos:** variantes de ORB con retesteo ya se probaron antes sobre estos mismos datos de NQ (laboratorio del repositorio). El test 2025-2026 no es una muestra completamente virgen. Las reglas de este proyecto las fijó el usuario y no se ajustó ningún parámetro.
