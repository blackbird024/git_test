# PROJECT AUDIT — Trading Bot Lab (30-sep-2026)

Diagnóstico hecho ANTES de escribir código del laboratorio.

## 1. Existing architecture
| Carpeta | Qué contiene | Estado |
|---|---|---|
| `src/` | Núcleo del proyecto: horas y zonas horarias (`horas.py`), datos (`data/`), motor de ejecución (`engine/`), métricas (`metrics/`), riesgo (`risk/`), estrategias (`strategies/`), informes (`report/`), alertas Telegram (`alerts/`) | En uso |
| `auditoria/` | Auditoría del 30-sep: métricas con bootstrap por bloques, reproducción de las 2 validadas, re-ejecución de las rechazadas, cartera y simulación de riesgo | En uso, resultados congelados en `auditoria/experimentos/20260930_0633/` |
| `vwap_mnq_strategy/`, `vwap_ema_research/` | Subproyectos independientes (VWAP direccional, VWAP+EMAs 15 m) con su propio motor | Cerrados (negativos) |
| `archive/` | Primera generación de estudios (ORB, reversión a la media, cruces de medias, MACD, PO3, momentum de cierre, TSMOM, noise area) | Cerrado; **cuenta como hipótesis ya probadas** |
| `edges/`, `reports/` | Fichas pre-registradas y resultados de cada estrategia | Documentación |
| `mt5/` | EA en producción (demo): zona de ruido + RSI(2) | En forward test desde el 30-sep-2026 |

## 2. Existing backtest engine
- `src/engine/ejecucion.py`: simulación por operación sobre velas de 1 min. Señal al cierre de la vela y entrada en la apertura de la siguiente. Si el stop y el objetivo caen en la misma vela, cuenta como stop. Los huecos se ejecutan en la apertura. El objetivo es una orden límite sin deslizamiento y hay salida por tiempo. Tiene órdenes límite y guarda el recorrido del P&L. Es correcto pero lento (bucles de Python y `pd.Timestamp` por vela) para barrer muchas variantes.
- `src/engine/costes.py`: 1 $/lado de comisión y 1 tick de deslizamiento, 2 ticks en las aperturas de Londres, NY y Globex, con multiplicador para el estrés.
- `src/engine/lookahead.py`: prueba de truncamiento (las señales anteriores a T no cambian al quitar los datos posteriores a T).
- Las estrategias validadas tienen motor propio: `zona_ruido.py` (vectorizado por día) y `nq_rsi2.py` (sesiones diarias con precios ajustados por cambio de contrato).

## 3. Existing data
| Datos | Fuente | Periodo | Notas |
|---|---|---|---|
| NQ 1 min (`data/processed/NQ_1M.parquet`, 4,09 M velas) | Databento GLBX.MDP3 `NQ.v.0` | 2015-01-02 → 2026-09-29 | UTC, volumen real, `instrument_id` (se ven los cambios de contrato); 65 sesiones ilíquidas excluidas con regla causal |
| GC 1 min | Databento `GC.v.0` | igual | |
| GC y SI diarios (`data/raw/daily/`) | Databento | 2010 → 2026 | Día natural UTC |
| **ES 1 min** | — | **no existe** | Necesario para los BOT 25 y 26 (NQ/ES). Descargarlo cuesta **15,06 $** en Databento (consultado, no descargado) |

## 4. Existing strategies (resultados de la auditoría del 30-sep, periodo 2015-2026)
| BOT | Estrategia | Operaciones | PF | Estado |
|---|---|---|---|---|
| 01 | RSI(2) NQ diario (Connors) | 158 | 1,69 | Validada, en forward |
| 02 | Zona de ruido NQ (Zarattini) | 2.725 | 1,20 | Validada, en forward |
| 03 | SMC/ICT kill zones | 14-31 | <1 | No validada |
| 04 | Rango 30 min + London + VWAP | 2.637 | 1,07 | IC incluye 0 |
| 05 | Cruce VWAP 15m 1:2 | 4.645 | 1,02 | IC incluye 0 |
| 06 | VWAP direccional | 3.794 | 0,85 | Negativa |
| 07-08 | VWAP+EMAs MNQ / MGC | 3.600-7.000 | 0,68-0,97 | Negativas |
| 09-10 | Zona de ruido / RSI(2) en oro | 2.784 / 150 | 0,91 / 1,24 | Negativa / insuficiente |
| 11 | Pares oro/plata | 84 | — | Insuficiente |
| 12 | Oferta/demanda XAUUSD | 1.275 | 0,98 | Insuficiente |

**Hipótesis ya probadas en `archive/` sobre NQ que se solapan con este encargo** (hay que tenerlas en cuenta en el recuento de pruebas múltiples):

| Estudio archivado | Resultado |
|---|---|
| ORB 5/15/30 min con 2R | Negativo, t entre −3,7 y −4,6 |
| ORB 5/15/30 min con salida por tiempo | t entre −0,2 y 1,3 |
| Reversión a la media con desviación en ATR | Negativa, t entre −1,5 y −3,3 |
| Cruces de medias 9-21 y 20-50, con y sin ADX | Negativos o nulos |
| MACD 5m/15m | Negativo o nulo |
| PO3 | Negativo o nulo |
| Momentum de cierre | t = −5,2 |

**Consecuencia:** los BOT 14 (ORB), 13 (reversión a VWAP) y 15 (tendencia) son en parte re-pruebas de ideas que ya fallaron. Se prueban igualmente con el nuevo motor, porque las reglas son distintas, pero la expectativa previa es baja y se declara.

## 5. Existing tests
112 pruebas pasan (`python -m pytest -q tests auditoria/tests`). Cubren:
- zonas horarias y cambio de hora;
- look-ahead por truncamiento en datos reales;
- stop y objetivo en la misma vela;
- estrategias concretas;
- métricas y bootstrap de la auditoría;
- Telegram.

Los subproyectos tienen 24 y 16 pruebas propias.

## 6. Existing metrics
- `src/metrics/metricas.py` y `detalle.py`: PF, R medio, t, drawdown, rachas y desgloses por año, mes y día de la semana.
- `auditoria/src/metricas.py`:
  - P&L diario por sesión;
  - Sharpe y Sortino diarios anualizados;
  - IC por **bootstrap por bloques** de 20 sesiones y IC iid;
  - tablas por periodo.
- **Faltan:** Calmar, drawdown medio, payoff, MAE/MFE, asimetría y curtosis, percentiles, peor día/semana/mes/año y expectativa en R para todas las estrategias.

## 7. Existing validation tools
| Herramienta | Dónde |
|---|---|
| Truncamiento para look-ahead | `src/engine/lookahead.py` |
| Bootstrap por bloques | `auditoria/src/metricas.ic_bloques` |
| Monte Carlo por permutación | `src/metrics/montecarlo.py` |
| Simulación de riesgo por bloques con parada por caída | `auditoria/src/cartera.simular_riesgo` |
| Vecindades de parámetros | `auditoria/src/validadas.py` |
| Correlaciones de cartera | `auditoria/src/cartera.py` |
| Drawdown trailing de Apex | `archive/src/risk/apex_trailing.py` |

**No hay** walk-forward genérico, ni partición 60/20/20, ni clasificación automática A-E.

## 8. What can be reused (sin modificar los originales)
| Se reutiliza | Para qué |
|---|---|
| `src.data.datos.velas_1m`, `excluidos`, `sesiones` | Datos, días excluidos y sesiones diarias ajustadas |
| `src.horas` | Zonas horarias |
| `src.strategies.zona_ruido` y `nq_rsi2` | BOT 01/02 y base del BOT 18 |
| `auditoria/src/metricas` | P&L diario, IC por bloques |
| `auditoria/src/cartera` | Simulación de riesgo por bloques |
| `src.engine.lookahead.comprobar` | Pruebas de truncamiento |

Se conservan las **reglas del motor existente** (entrada en la vela siguiente, stop primero, huecos, objetivo límite) y los **costes base de la auditoría** (1 $/lado y 1-2 ticks).

## 9. What is missing
1. **Motor rápido** para cientos de variantes. Se escribe uno nuevo en `bot_lab/core/motor.py` (numba) con las mismas reglas conservadoras. Se prueba contra casos de juguete y contra el motor antiguo.
2. **Indicadores intradía causales comunes:**
   - velas de 5 y 15 min con la marca "disponible";
   - VWAP de RTH y de Globex con bandas de desviación;
   - ATR, EMA, ADX y ratio de eficiencia;
   - rango de la noche y niveles del día anterior;
   - ajuste causal por cambio de contrato para los indicadores.
3. Partición 60/20/20 con TEST bloqueado, registro de investigación y fichas de hipótesis.
4. Walk-forward, sensibilidad y estabilidad, estrés de costes ×2/×3, regímenes, MAE/MFE y distribución.
5. Correlación entre bots, carteras A/B/C, módulo de prop firm, dimensionamiento y clasificación A-E.
6. Datos de ES (BOT 25/26): **pendiente de autorización del gasto (15,06 $)**.

## 10. Proposed implementation plan
1. `bot_lab/CRITERIOS.md`: partición, costes, presupuesto de parámetros, puertas de cada fase y reglas A-E, **escritos antes de ejecutar nada**.
2. Núcleo:
   - `core/datos.py`: contexto con arrays de 1 min, sesiones y velas de 5/15 min;
   - `core/indicadores.py`;
   - `core/motor.py`: numba; entrada a mercado u orden stop OCO, stop, objetivo fijo, en R o dinámico (VWAP), trailing, salida por tiempo, MAE/MFE y costes;
   - `core/metricas.py`.
3. Estrategias:
   - un módulo por familia (BOT 13-19 en la fase 1; 23, 24 y 26 en la fase 2);
   - cada módulo tiene su hipótesis, su configuración base y sus variantes **pre-registradas** (una cosa cada vez, sin rejillas completas).
4. Protocolo:
   - **Fase 1:** cribado en TRAIN.
   - **Selección:** con una regla fija y registrada, sobre TRAIN.
   - **VALIDATION:** solo de la variante elegida.
   - **Finalistas:** walk-forward 12m/3m, sensibilidad, costes ×2/×3, regímenes, bootstrap y Monte Carlo.
   - **TEST:** se desbloquea una sola vez, al final, para los finalistas congelados.
5. Fase 2:
   - regímenes de volatilidad, hora y día (BOT 20-22) sobre todas las estrategias, incluidas las 01/02;
   - nuevas familias 23, 24 y 26 (oro/plata con datos diarios);
   - 25/26 NQ/ES si se autoriza la descarga.
6. Cartera A/B/C, correlaciones, dimensionamiento 0,25/0,5/1 % y prop firm.
7. `RESEARCH_LOG.md`, `reports/FINAL_REPORT.md` y un panel HTML. Todas las pruebas antiguas y nuevas deben pasar.

**Nota sobre fuera de muestra.** Todo el periodo 2015-2026 ya se usó en investigaciones anteriores del proyecto. El TEST del laboratorio (el último 20 %) está reservado para **estas reglas nuevas**, pero **no es fuera de muestra puro**: el investigador ya ha visto ese mercado. El único dato realmente nuevo será el forward test.
