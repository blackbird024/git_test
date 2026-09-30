# SURVIVOR ANALYSIS — PROJECT AUDIT (30-sep-2026)

Diagnóstico hecho ANTES de ejecutar ningún análisis y de modificar código.

## 1. Exact RSI2 implementation
Código: `src/strategies/nq_rsi2.py`. Último cambio: commit `b3dd6d2`, "Step 3: RSI(2) on NQ passes all pre-registered validation criteria". SHA-256 `24716d14…c898`. Ficha: `edges/nq_rsi2.md`.

**Velas**
- Diarias por sesión de CME (18:00 → 17:00 NY), construidas desde 1 min (`src.data.datos.sesiones`).
- Los indicadores usan cierres **ajustados multiplicativamente** por cambio de contrato (`close_aj`, `open_aj`), solo con el pasado.

**Indicadores**
- `RSI(2)` de Wilder sobre `close_aj`: `sube = EWM(α=1/2)` de max(Δ, 0) y `baja` igual con max(−Δ, 0). RSI = 100 − 100/(1 + sube/baja); vale 100 si `baja` = 0.
- `SMA200` = media simple de 200 sesiones de `close_aj`.

**Reglas**
- **Señal al cierre de la sesión i:** `close_aj[i] > SMA200[i]` y `RSI[i] < 20`.
- **Entrada:** apertura de la sesión i+1 (reapertura de Globex, 18:00 NY), a precio real `open[i+1]`.
- **Salida:** en la apertura de la sesión k+1, siendo k la primera sesión desde la entrada con `RSI[k] > 70` o con `k − e + 1 ≥ 5`.
- **Una posición a la vez:** tras una salida en x, la siguiente señal puede darse al cierre de x.

**Resultado de cada operación**
- `ret = open_aj[x]/open_aj[e] − 1`.
- `neto = (open[e]·ret − deslizamiento)·2 $ − comisión`.
- `deslizamiento = (ticks(t_entrada) + ticks(t_salida))·0,25`: 2 ticks en la reapertura de Globex, así que 4 ticks en total.
- `comisión = 2·1 $`.
- `r = ret_neto / std(ret, 20 sesiones)`.

Sin stop. Solo largos. 1 MNQ.

**Sesiones excluidas:** las 65 sesiones ilíquidas (regla causal `dias_iliquidos`). Si la sesión de entrada está excluida, no se entra.

## 2. Exact Noise Zone implementation
Código: `src/strategies/zona_ruido.py` (`ZONA_RUIDO_MNQ_v1.0`). Último cambio: commit `c56bb98`. SHA-256 `a00839d1…2cdb`. Ficha: `edges/zona_ruido_mnq.md`. Es la regla de Zarattini, Aziz y Barbon (2024).

**Datos de cada día (RTH 09:30-16:00 NY)**
- `minute` = minutos desde las 09:30.
- `move[d, m] = |close[d, m]/open[d] − 1|`.
- `sigma[d, m]` = media de `move` de los **14 días anteriores** (mínimo 10), con `rolling(14).mean().shift(1)`.
- `prev_close` = cierre RTH anterior. El día de cambio de contrato se usa la apertura del día.

**Bandas**
- `sup = max(open, prev_close)·(1 + sigma)`
- `inf = min(open, prev_close)·(1 − sigma)`

**Chequeos** cada 30 min, de 10:00 a 15:30 NY (m = 30, 60, …, 360). Se usa el cierre del minuto m−1 y las bandas de m−1, y se ejecuta en la apertura del minuto m.
- **Sin posición:** si `C > sup` → largo; si `C < inf` → corto.
- **Largo:** sale si `C < max(sup, VWAP)`. Tras salir, en el mismo chequeo puede entrar en el otro sentido.
- **Corto:** simétrico, con `min(inf, VWAP)`.
- El VWAP es el de la sesión RTH, con precio típico y volumen.
- **Cierre forzado:** cierre de la vela de 15:59.

**Costes y tamaño:** 1 tick por lado y 1 $ por lado. 1 MNQ. Sin stop. Mismas sesiones excluidas.

## 3. Original parameters
| Estrategia | Parámetros |
|---|---|
| RSI(2) | entrada 20, salida 70, máximo 5 sesiones, SMA 200, RSI de 2 |
| Zona de ruido | 14 días de ruido (mínimo 10), multiplicador 1,0, chequeos cada 30 min de 10:00 a 15:30 |

## 4. Original datasets
- NQ 1 min de Databento GLBX.MDP3 `NQ.v.0` (contrato continuo por volumen, sin ajustar), 2015-01-01 → 2026-09-29, en `data/processed/NQ_1M.parquet`, con copia privada en `apex-datos`. Tiene volumen real e `instrument_id`.
- Diarios de ES (2010-2026, día UTC) se usaron en el paso 3 del RSI(2) como "otro mercado". **No están en este contenedor.**

## 5. Original backtest periods
2015-01-02 → 2026-09-28. La partición original del proyecto fija el desarrollo hasta el 2023-03-21 (`config/particion.json`).
- **RSI(2):** desarrollo con 97 operaciones y PF 1,46; posterior con 61 y PF 1,93.
- **Zona de ruido:** desarrollo con 1.924 operaciones y PF 1,19; posterior con 800 y PF 1,22.

## 6. Original TEST period
- **Partición del proyecto:** "posterior" desde el 2023-03-22. Ya se ha **visto** para las dos estrategias: el RSI(2) lo usó en su paso 3 y la zona de ruido en el estudio de origen.
- **Laboratorio:** TEST desde el 2024-05-23, abierto una sola vez para el BOT 24.3. Para RSI(2) y zona de ruido ese periodo **ya estaba visto** (está dentro del "posterior").
- **Consecuencia:** para las dos supervivientes **no existe ningún tramo fuera de muestra**. Todo lo que se haga aquí es **NOT OUT-OF-SAMPLE**. El único dato nuevo es el forward test en la demo, desde el 30-sep-2026.

## 7. Existing trade files
| Archivo | Contenido |
|---|---|
| `auditoria/experimentos/20260930_0633/operaciones_zona_ruido.csv` | 2.725 operaciones de la zona de ruido |
| `auditoria/experimentos/20260930_0633/operaciones_rsi2.csv` | 158 operaciones del RSI(2) |
| `reports/ZONA_RUIDO_MNQ_v1.0/trades.csv` | Informe original de la zona de ruido |
| `bot_lab/research/experiments/20260930_0900_test/pnl_diario_bots.csv` | P&L diario |

La zona de ruido no guarda MAE/MFE, así que hay que calcularlos a partir del 1 min.

## 8. Existing metrics
`auditoria/src/metricas.py` y `bot_lab/core/metricas.py` calculan PF, expectativa, t, IC por bloques, Sharpe, Sortino, drawdown, rachas, distribución y tablas por periodo.

## 9. Existing Monte Carlo
- `auditoria/src/cartera.simular_riesgo`: bootstrap por bloques de 20 sesiones, 252 sesiones, con parada por caída.
- `bot_lab/validation/montecarlo.distribucion`.
- `src/metrics/montecarlo.py`: permutación.

## 10. Existing walk-forward
La auditoría usó "walk-forward con reglas congeladas" = **ventanas anuales**. El laboratorio tiene un walk-forward de 12/3 meses con re-selección, que aquí **no se usa** porque no se recalibra nada.

## 11. Existing tests
181 pruebas pasan. Las que afectan a las supervivientes:
- `tests/test_zona_ruido.py`, `test_lookahead_real.py`, `test_misma_vela.py`;
- `auditoria/tests/test_auditoria.py`, que comprueba que la variante con retardo 0 = original.

## 12. Data available for regime analysis
A partir del 1 min de NQ se pueden calcular:
- ATR diario;
- volatilidad realizada;
- ratio de eficiencia y pendiente de la EMA;
- VWAP de RTH y de Globex;
- hueco, posición de la apertura, rango y retorno nocturnos, rango del día anterior;
- hora y día.

Todo con información anterior a la entrada. Además, el ajuste causal por cambio de contrato está en `bot_lab/core/datos.py`.

## 13. Missing data
- **ES de 1 min:** para el NQ/ES.
- **Datos del CFD NAS100 de Pepperstone:** la ejecución real es en CFD, con otro precio, spread, swap y VWAP de volumen de ticks.
- **Operaciones forward reales:** el EA acaba de empezar.
- **MAE/MFE de la zona de ruido:** no se guardaron, pero se pueden reconstruir.

## 14. Potential contamination risks
1. **Todo el histórico está visto** (ver el punto 6). Nada de lo que salga aquí es fuera de muestra.
2. **Pruebas múltiples:** este análisis genera decenas de tablas. Solo cuentan como confirmatorias las preguntas pre-registradas, y cualquier patrón nuevo va a `POST_HOC_OBSERVATIONS.md`.
3. **Tentación de filtrar a posteriori** (por ejemplo "solo en volatilidad alta"): **prohibido**. Nada de este análisis cambia las reglas del EA.
4. **Diferencias entre backtest y EA:**
   - el EA opera un CFD con otro horario de servidor y VWAP de volumen de ticks;
   - el RSI(2) del EA usa las velas diarias del CFD, no las sesiones de CME del futuro.
   Solo el forward lo medirá.
5. **Los umbrales de régimen por cuantiles calculados con toda la muestra usan información futura para la clasificación.** Se usan umbrales fijos o cuantiles *expansivos* (causales) y se dice cuál es cuál.

## 15. ES/NQ data requirements
| Campo | Valor |
|---|---|
| Dataset | GLBX.MDP3 |
| Esquema | ohlcv-1m |
| Símbolo | `ES.v.0` (continuo por volumen) |
| Periodo | 2015-01-01 → 2026-09-30 |

## 16. Exact Databento cost estimation plan (ejecutado, sin descargar)
Se llamó a `metadata.get_cost`, `metadata.get_record_count` y `metadata.get_billable_size` con esos parámetros:

```text
ES DATA REQUEST

Dataset:            GLBX.MDP3
Schema:             ohlcv-1m
Period:             2015-01-01 → 2026-09-30
Symbols:            ES.v.0 (stype_in = continuous)
Records:            4,125,371
Estimated size:     231,020,776 bytes (≈ 231 MB)
Estimated cost:     15.06 USD
Available credit:   desconocido (el cliente Historical de Databento no expone el saldo)

DOWNLOAD NOT EXECUTED
```

Además, **no se puede reservar un TEST limpio para NQ/ES**: todo el periodo del NQ ya está visto. Cualquier resultado sería **EXPLORATORY ONLY**.

## 17. Implementation plan
1. **Congelar:** `survivor/congeladas.py` con `RSI2_SURVIVOR_V1` y `NOISE_ZONE_SURVIVOR_V1`. Llaman al código original sin cambios, fijan los parámetros y comprueban el SHA-256 de los archivos fuente. Una prueba verifica que reproducen **operación a operación** los CSV de la auditoría.
2. **Pre-registro** en `SURVIVOR_ANALYSIS_PRE_REGISTRATION.md`: preguntas, métricas, umbrales, pruebas y reglas de interpretación (CONFIRMATION / WEAK EVIDENCE / CONTRADICTION / INCONCLUSIVE). Se guarda en git antes de ejecutar.
3. **Módulos (`survivor/src/`):**
   - `caracteristicas.py`: rasgos anteriores a la entrada, por operación;
   - `trayectorias.py`: MAE/MFE, P&L a horizontes fijos y tiempo hasta fallar;
   - `estres.py`: costes ×1,5/×2/×3, +1/+2/+3 ticks, retraso de 1/2/3/5 min con copias fieles con un único cambio y una prueba de identidad con cambio 0, y sensibilidad ±;
   - `falsacion.py`: pruebas de aleatorización (dirección aleatoria, momento aleatorio, días aleatorios);
   - `temporal.py`: años, meses, ventanas móviles, subperiodos, walk-forward congelado, crisis, concentración y valores atípicos;
   - `cartera.py`: mark-to-market diario del RSI(2), correlaciones condicionadas, solapamiento, pesos de riesgo igual 100/75/50/25/0 y Monte Carlo.
4. **Forward:**
   - `forward_testing/survivors.csv` (plantilla);
   - `forward_testing/deriva.py`: bandas históricas de expectativa móvil de 50 operaciones, avisos sin apagar nada;
   - `forward_testing/comparar.py`: live frente a backtest, incluido un lector del `APEX_registro.csv` del EA.
5. **Registros:** `TEST_CONTAMINATION_LOG.md` y `POST_HOC_OBSERVATIONS.md`.
6. **Informe:** `reports/SURVIVOR_ANALYSIS_FINAL.md`, con resumen, tabla de evidencia, tabla de carteras y árbol de decisión.
