# Laboratorio cuantitativo Nasdaq: informe final

Fecha: 9 de octubre de 2026. Todo lo que aparece aquí se ha calculado con el código de `laboratorio/` y está guardado en `experiments/`, cada experimento con su `manifest.json`. Las cifras son de backtest. **No garantizan nada sobre el futuro.**

## Resumen en 6 líneas

1. **Ninguna estrategia ha superado los criterios fijados de antemano para ser CANDIDATA.** No hay nada "validado".
2. **La mejor señal es la zona de ruido intradía** (reglas originales, sin tocar). Es positiva en desarrollo, validación y prueba, robusta a parámetros y costes, y muy superior al azar. Pero:
   - Sus beneficios están muy concentrados: el 73 % viene de las 10 mejores operaciones, y un solo día (9 de abril de 2025) aporta el 57 % de la prueba.
   - En Topstep 50K pierde la cuenta más veces de las que la aprueba, incluso con 1 MNQ.
3. **El ORB de 5 minutos** con tus reglas (ruptura, cierre o retesteo; stop estructural; 2R; salida 11:30) **no muestra ventaja**: dos variantes rechazadas y una inconclusa con desarrollo negativo.
4. **La continuación de tendencia intradía** queda rechazada: pierde en la prueba final.
5. **En swing:**
   - Ninguna estrategia activa bate a comprar y mantener el Nasdaq-100 en rentabilidad.
   - Con la fiscalidad italiana de los ETF, la diferencia se vuelve enorme: una rentabilidad anual del 1–1,3 % frente al 17,6 % después de impuestos (2016-2026, simplificado).
6. **Recomendación:**
   - 200 €/mes a fondo de emergencia y luego a un PAC en ETF UCITS.
   - La zona de ruido solo en forward test simulado, sin dinero, durante 30 días, para medir la ejecución, no la rentabilidad.

## 1. Qué existía (fase 1)

| Elemento | Estado |
|---|---|
| NQ 1 min 2018-01 → 2026-10-02 (Databento, `NQ.c.0`) | Existe. Auditado en `orb_mnq/reports/auditoria_datos.json`: sin duplicados ni NaN, precios en múltiplos de 0,25. |
| MNQ/NQ desde **2015** | **No existe** en este entorno. MNQ cotiza desde el 6 de mayo de 2019; los datos de 2015-2017 serían de NQ y habría que comprarlos (no lo he hecho). |
| QQQ diario 2016 → 2026 | Se descargó gratis (Alpaca), con precios brutos y ajustados por dividendos. |
| `auditoria/experimentos/20260930_0633/INFORME_FINAL.md` y `AUDITORIA_CODIGO.md` | **No existen** en el repositorio ni en su historial git. Probablemente están en el Acer. |
| Zona de ruido | `alpaca/mnq_intraday_lab.py`, más el indicador `tradingview/BandasRuidoNY.pine`. **Reproducida exactamente**: PF 1,33, +2.791 $/año, peor racha −3.430 $, 8/9 años, igual que lo publicado en su día. |
| "Ruido PF 1,19–1,20" | En este repositorio, el PF de 1,19 corresponde a **otra estrategia** (EMA 9/21 + CHOP). No he encontrado una versión de la zona de ruido con PF 1,19–1,20; puede ser la del Acer. |
| "RSI(2) swing NQ, PF 1,46 / 1,93" | **No está en el repositorio.** Existe un RSI(2) de Connors en `alpaca/swing_lab.py`, sobre QQQ con precios sin ajustar. Lo he auditado con sus reglas originales. |
| ~100 scripts de investigación previos (`alpaca/`), indicadores (`tradingview/`) y EAs (`mt5/`) | Sin modificar. Problemas encontrados: ver `AUDITORIA_CODIGO.md`. |

## 2. Método

- **Laboratorio nuevo en `laboratorio/`**, sin tocar nada existente:
  - `data/`, `strategies/`, `backtests/`, `execution_costs/`, `risk/`, `validation/`, `config/`, `tests/` (27 tests que pasan) y `experiments/` (con manifiestos).
- **Ejecución intradía con velas de 1 minuto:**
  - Entrada en la apertura siguiente con deslizamiento.
  - Stop primero si stop y objetivo caben en el mismo minuto; si hay hueco más allá del stop, se ejecuta en la apertura.
  - El objetivo límite solo se llena si el precio lo cruza en 1 tick; sin objetivo en la vela de entrada de una orden stop.
  - Medias jornadas y festivos según el calendario XNYS. La conversión ET → Italia gestiona los dos cambios de horario.
- **Costes (provisionales):**
  - Bajo, base y alto: 1, 2 y 3 ticks por lado, más 0,75 $ fijos por lado y contrato.
  - **No conozco tu comisión real** (ver `config/CONFIG_COSTES.yaml`).
- **Partición:**
  - Intradía: desarrollo 2018-21, validación 2022-24, prueba 2025 → 2 oct 2026.
  - Swing: 2016-20, 2021-23 y 2024 → 8 oct 2026.
  - El esquema 2015-2020 que propusiste no es posible con estos datos.
- **Protocolo:**
  - Los criterios y las reglas de selección (`config/PROTOCOLO.yaml`) se escribieron **antes** de ver ningún resultado.
  - Las reglas se congelaron (`experiments/reglas_congeladas.yaml`, commit `52966a2`) **antes** de calcular la prueba final, que se evaluó una sola vez.
- **Advertencia honesta:**
  - En esta conversación ya se habían probado decenas de variantes de ORB y de ruido sobre NQ 2018-2026. Ningún periodo es una prueba "virgen" para estas familias.
  - La única prueba independiente será el forward test.

## 3. Sistema A: Topstep 50K intradía (MNQ)

Resultados por 1 MNQ con coste base. "Esperanza" = USD netos por operación. FM = fuera de muestra (2022 → 2026).

| Estrategia (regla congelada) | PF desarrollo / validación / prueba | Esperanza validación / prueba | IC90 de la esperanza FM | Top-10 ops / neto FM | Vecinos positivos | Clasificación |
|---|---|---|---|---|---|---|
| ORB inmediato, stop rango, 2R, 11:30, filtro vol. | 0,92 / 0,99 / 1,00 | −0,60 / −0,41 | [−9,6; 7,7] | — | 0 % | **RECHAZADA** |
| ORB cierre confirmado, stop rango, 2R, 11:30, filtro vol. | 0,90 / 1,06 / 1,07 | 3,30 / 5,74 | [−5,9; 13,5] | 137 % | 0 % | **INCONCLUSA** (desarrollo negativo, peor que el placebo en desarrollo) |
| ORB ruptura + retesteo (tu especificación) | 0,80 / 0,82 / 0,91 | −6,52 / −5,11 | [−14,4; 3,6] | — | — | **RECHAZADA** |
| ORB inmediato, sin objetivo, salida 15:55 (secundaria) | 1,02 / 1,15 / 1,04 | 11,59 / 4,10 | [−3,2; 22,9] | 139 % | 33 % | **INCONCLUSA** (elegida entre 9 secundarias: sesgo de selección) |
| Continuación de tendencia + VWAP | 0,87 / 1,07 / 0,72 | 2,59 / −16,08 | [−12,5; 4,3] | — | 0 % | **RECHAZADA** |
| **Zona de ruido (reglas originales)** | **1,29 / 1,31 / 1,18** | **15,13 / 12,51** | **[5,7; 23,3]** | **73 %** | **100 % (27/27)** | **INCONCLUSA** (falla solo el criterio de concentración) |

### Zona de ruido en detalle

- **Volumen y beneficio:**
  - Unas 240 operaciones al año, en ~140 días.
  - Acierto del 38–42 %; la ganancia media es 1,8–2,1 veces la pérdida media.
  - Resultado: +2.060, +3.765 y +3.117 $/año por MNQ en desarrollo, validación y prueba.
- **Robustez a los costes:** con 4 ticks más de deslizamiento por lado y comisión doble sigue en +9,6 $/operación en validación.
- **Diferencia con el azar:**
  - Con la misma hora de entrada y dirección aleatoria, la esperanza media es −4,8 $/operación.
  - La estrategia real queda por encima de las 20 réplicas aleatorias, tanto en desarrollo como en validación.
- **Debilidades:**
  - **Concentración:**
    - El 9 de abril de 2025 (rebote por la pausa arancelaria) aporta +3.131 $, el 57 % del neto de toda la prueba.
    - Por régimen de volatilidad, gana 23 $/operación con volatilidad alta y solo 7 $ con baja o media.
    - Es una estrategia que vive de días de tendencia fuerte.
  - **Drawdown:** 3.170 $ por MNQ en la prueba, **mayor que el MLL de 2.000 $** de la cuenta 50K.
  - **Sin stop-loss en las reglas originales.** Topstep exige controlar el riesgo y tu instrucción dice no operar sin un stop dentro del presupuesto. Añadir un stop sería una hipótesis nueva, que solo puede validarse con datos futuros.
  - **Variante del indicador de TradingView:** `BandasRuidoNY.pine` sale por defecto solo con la banda, sin la "media del día". Es la variante "sin media" del laboratorio original. Medida aparte, como comprobación de coherencia (no es la regla congelada):
    - PF 1,33 / 1,34 / 1,20 en desarrollo, validación y prueba.
    - IC90 fuera de muestra [7,3; 28,2] $/operación.
    - Top-10 = 70 %.
    - Mismas conclusiones. El forward test en papel con ese indicador es coherente con lo evaluado.
  - **Tiempo:** exige decidir cada 30 min entre las 10:00 y las 15:30 ET (16:00–21:30 en Italia). Son pocos minutos en total, pero repartidos en 5,5 horas. **No es compatible con "menos de una hora al día" sin alertas o automatización.**

### Simulación del Combine (`run_topstep.py`)

**Cómo se simula:**
- Un intento por cada día de inicio de 2022 a 2026, con días secuenciales (no barajados).
- MLL de 2.000 $ con trailing al cierre, que deja de subir al llegar a 50.000 $.
- DLL de 1.000 $ y consistencia (mejor día ≤ 55 % del beneficio).
- Stop diario personal de 300 $.
- El flotante intradía se aproxima con la peor excursión adversa (MAE) de cada operación.

| Estrategia · tamaño | Aprueba | Pierde la cuenta | Sin resolver en 250 días | Días hasta aprobar (mediana) |
|---|---|---|---|---|
| Zona de ruido · 1 MNQ | 31 % | 61 % | 7 % | 150 |
| Zona de ruido · 2 MNQ | 41 % | 58 % | 1 % | 74 |
| Zona de ruido · 3 MNQ | 29 % | 71 % | 0 % | 45 |
| Control aleatorio · 2 MNQ (3 semillas) | 5–17 % | 83–95 % | 0 % | — |
| ORB inmediato, salida 15:55 · riesgo 200 $ | 42 % | 58 % | 0 % | 51 |
| ORB con riesgo 50–100 $ | 0 % | 0–30 % | el resto | — (el stop del rango cuesta más que el presupuesto en el 40–90 % de los días) |

**Lectura:**
- La zona de ruido aprueba 2–8 veces más que el azar, pero **en ningún caso es más probable aprobar que perder la cuenta**.
- La regla del MLL de 2.000 $ es estrecha para la varianza de estas estrategias, incluso con el tamaño mínimo.

## 4. Sistema B: swing con capital propio

Datos: QQQ ajustado por dividendos, como proxy del Nasdaq-100. Ejecución en la apertura siguiente. Capital de 10.000; costes de 0,05 % por lado más 3 € por orden.

| Estrategia | PF desarrollo / validación / prueba | Rentabilidad anual en la prueba (2024-26) | Drawdown máx. en la prueba | MAR en la prueba | IC90 de la esperanza FM | Clasificación |
|---|---|---|---|---|---|---|
| B1 Ruptura de 20 sesiones (2×ATR, salida con mínimo de 10 días o a los 20 días) | 1,49 / 1,91 / 1,41 | 3,7 % | −13,5 % | 0,27 | [−0,01 %; 1,78 %] | **INCONCLUSA** |
| B2 + EMA200 / pendiente / volatilidad | filtros descartados en validación | — | — | — | — | no seleccionadas |
| B3 RSI(2) de Connors (reversión, ~3 días) | 1,20 / 2,03 / 2,57 | 6,6 % | −7,4 % | 0,89 | [0,17 %; 0,90 %] | **INCONCLUSA** (top-10 = 87 %; mejor año 50,4 %; no es un swing de 1–4 semanas) |
| B4 Retroceso a la EMA20 en tendencia | 4,55 / **0,75** / 2,57 | 8,3 % | −7,2 % | 1,15 | [−0,62 %; 1,32 %] | **RECHAZADA** (pierde en validación) |
| **Comprar y mantener QQQ** | — | **25,8 %** | −22,8 % | **1,13** | — | referencia |

**Fiscalidad italiana** (simplificada, **confírmalo con un asesor**):
- Las ganancias de un ETF tributan al 26 % como *redditi di capitale*.
- Las pérdidas son *redditi diversi* y no compensan esas ganancias.
- Con capital compuesto 2016-2026:

| | Antes de impuestos | Después de impuestos |
|---|---|---|
| B1 | 5,4 %/año | 1,3 %/año |
| B3 | 3,0 %/año | 1,1 %/año |
| Comprar y mantener (ETF de acumulación, impuesto al vender al final) | 20,4 %/año | 17,6 %/año |

**RSI(2) sobre NQ** (futuros, sesión regular), para comparar con tu "PF 1,46 / 1,93":
- PF 1,66 / 2,38 / 3,19, con 14 / 21 / 30 operaciones.
- Mismo signo, pero con muy pocas operaciones.

**MNQ como swing:**
- El stop de 2×ATR20 cuesta hoy ~1.650 $ por contrato (mediana histórica 950 $).
- El peor hueco nocturno fue de −2.000 $ por contrato; el nominal es de ~62.000 $.
- Con un capital de unos pocos miles de euros, **una sola posición mínima supera muchas veces el riesgo del 1 %. No es apropiado** y no voy a reducir el stop para que lo parezca.

**Capital pequeño:**
- Con 2.000 € y una comisión de 3 € por orden, el coste por operación (~0,4 % ida y vuelta) se come la mitad de la esperanza de B1 y B3.
- Además, con un riesgo del 1 % y un stop de 2×ATR, la posición sería de ~500 €, con lo que la comisión pesaría ~1,2 % ida y vuelta.

**ETF UCITS adecuados** (datos de memoria, **verificar en el KID y en IBKR**; no he podido acceder a justETF ni a IBKR desde aquí):

| ETF | Tipo |
|---|---|
| iShares Nasdaq 100 UCITS (CNDX / SXRV) | acumulación, Irlanda, TER ~0,30 % |
| Invesco EQQQ Nasdaq-100 UCITS (EQQQ) | distribución, ~0,30 % |
| Invesco EQQQ Acc (EQAC) | acumulación |
| Amundi Nasdaq-100 | réplica sintética, TER ~0,22 % |

- Un minorista de la UE no puede comprar QQQ (falta el KID de PRIIPs).
- Riesgo de divisa EUR/USD.
- Con IBKR (intermediario extranjero) estás en régimen *dichiarativo*: tú declaras las plusvalías y el IVAFE del 0,2 % anual.

## 5. Plan financiero (200 €/mes, `run_plan.py`)

1. **Fondo de emergencia:**
   - Los 200 € enteros hasta completarlo. Ejemplo: 3.000 €, unos 15 meses.
   - **Pon tu cifra real** (3–6 meses de gastos).
   - Comprar ETF por 50 € con una comisión de 3 € cuesta un 6 %, así que no merece la pena repartir.
2. **Después: PAC mensual en un ETF UCITS de acumulación sobre el Nasdaq-100.** Mejor aún si diversificas con un MSCI World, porque el Nasdaq-100 es un índice concentrado.
3. **Trading con capital propio: 0 €** hasta que una estrategia supere el forward test.
4. **Datos y herramientas: 0 €** (todo lo de este laboratorio es gratuito).
5. **Topstep: fuera de los 200 €.** Si sigues, es un gasto de formación con un tope que fijes tú, no una inversión.
   - Coste esperado de aprobar ≈ número de intentos esperados × meses por intento × cuota mensual + activación.
   - Con la zona de ruido a 2 MNQ: 1 / 0,41 ≈ **2,4 intentos** de ~70 días de mercado cada uno (~3,3 meses), es decir, **unos 8 meses de cuota por cada aprobado**.
   - No lo he podido verificar, pero **pon tu cuota real**.

Monte Carlo del ETF (volatilidad del 22 %, TER 0,30 %, IVAFE 0,2 %, 3 € por compra; **no son previsiones**). Mediana del valor invertido, con el percentil 5–95 entre paréntesis:

| Horizonte | Aportado al ETF | Adverso (0 %/año) | Moderado (5 %) | Favorable (9 %) | Prob. de valer menos que lo aportado (moderado) |
|---|---|---|---|---|---|
| 1 año | 0 € (todo al fondo) | — | — | — | — |
| 3 años | 4.200 € | 4.049 (3.132–5.321) | 4.232 (3.261–5.579) | 4.366 (3.383–5.750) | 48 % |
| 5 años | 9.000 € | 8.532 | 9.335 (6.293–14.214) | 9.924 | 44 % |
| 10 años | 21.000 € | 18.702 | 22.987 (12.835–45.097) | 27.751 | 40 % |

Más el fondo de emergencia de 3.000 €. Una caída del 35–80 % como las de 2022 o 2000-2002 cabe dentro de estos rangos.

## 6. Respuestas a tus cuatro preguntas

**1. ¿Qué ha demostrado una ventaja razonablemente robusta y qué se ha rechazado?**
- **Con ventaja estadística, pero sin aprobar todos los criterios:** la zona de ruido intradía.
  - Positiva en los tres periodos, IC90 por encima de 0 fuera de muestra, robusta a 27/27 parámetros y a costes altos, y muy por encima del azar.
  - Es INCONCLUSA solo por la concentración en pocos días de tendencia.
- **Rechazadas:**
  - ORB inmediato 2R + vol, ORB con retesteo (tu especificación), continuación de tendencia + VWAP y retroceso a la EMA20.
- **Inconclusas sin indicios fuertes:**
  - ORB con cierre confirmado y ORB inmediato con salida al cierre.
  - Ruptura de 20 sesiones y RSI(2). El RSI(2) tiene el IC por encima de 0, pero pocas operaciones, beneficio concentrado y un horizonte de 3 días.

**2. ¿Qué merece pasar a simulación prospectiva y en qué condiciones?**
- Solo la **zona de ruido**, en simulación (papel), con 1 MNQ y las reglas originales intactas.
- **Condición:** que puedas atender las alertas cada 30 min, o hacerlo con alertas de TradingView y registro automático.
- Objetivo de los primeros 30 días: medir la **fidelidad de ejecución**, no ganar dinero.
  - Deslizamiento real frente al modelado, señales perdidas, disciplina.
- En 30 días (~20 sesiones, ~35 operaciones) **es imposible validar la rentabilidad**: el IC90 de la esperanza con ~35 operaciones va de unos −37 a +63 $ por operación.

**3. ¿Qué riesgo y tamaño son compatibles con tus restricciones?**
- **Topstep 50K:**
  - Con lo demostrado hasta ahora, **ningún tamaño da más probabilidad de aprobar que de perder**.
  - 1 MNQ es el mínimo y aun así su drawdown histórico (3.170 $ en la prueba) supera el MLL.
  - Si operas, máximo 1–2 MNQ, stop diario personal de 300 $ y pausa si quedan menos de 500 $ hasta el MLL.
  - Hoy, con tu saldo de ~50.555 $ y el umbral en 49.561,70 $, tu colchón es de **~990 $**: menos que un mal día de cualquier estrategia probada.
- **Swing con capital propio:**
  - Sin apalancamiento.
  - MNQ es incompatible: un stop razonable cuesta 950–1.650 $ por contrato.
  - El ETF es viable, pero la estrategia activa no compensa los costes ni los impuestos frente al PAC pasivo.

**4. ¿Qué hacer en los próximos 30 días?** Detalle en `CHECKLIST_TOPSTEP.md` y `CHECKLIST_SWING.md`.
1. **Días 1–3:**
   - Pégame el texto oficial de Topstep: MLL, DLL, consistencia, contratos máximos y comisiones de MNQ. Actualizo `CONFIG_RIESGO.yaml` y `CONFIG_COSTES.yaml` y relanzo todo (5 minutos).
   - Decide tu cifra de fondo de emergencia.
2. **Combine actual:**
   - No operes en él el ORB que has estado usando: ninguna variante ha pasado los criterios.
   - Si no vas a seguir un sistema con evidencia, pausar la cuota es la decisión de menor riesgo.
3. **Días 1–30:**
   - Forward test **en papel** de la zona de ruido con el indicador `BandasRuidoNY.pine`, que ya tiene alertas. Anota cada señal en el diario.
   - Ojo: del 25 de octubre al 1 de noviembre la sesión se adelanta una hora en Italia (9:30 ET = 14:30).
4. **Cada semana:** revisión con `CHECKLIST_TOPSTEP.md` y comparación de las operaciones en papel con las que simula el backtest para los mismos días. Puedo hacerla yo si me lo pides con los datos.
5. **Swing / ahorro:**
   - Empieza el fondo de emergencia con los 200 €.
   - Verifica en IBKR la disponibilidad y el KID de un ETF UCITS de acumulación y su comisión real.
   - No hagas operaciones swing.
6. **Pasada la prueba en papel:** una decisión basada en criterios escritos (ver checklist), no en el P&L de 30 días.

## 7. Limitaciones principales

- **Reglas y costes sin verificar:**
  - Las reglas de Topstep y las comisiones no se han verificado (sitios bloqueados): **resultados provisionales**.
  - La interpretación de la consistencia y el valor del DLL son supuestos.
- **Datos de futuros:**
  - Datos desde 2018, no desde 2015.
  - El contrato continuo cambia tarde: unas 20 sesiones al año usan el contrato que vence, con ~24 % del volumen.
  - Sin ticks ni bid/ask: el deslizamiento es un supuesto, aunque se probaron hasta 6 ticks por lado.
  - Sensibilidad a esas semanas, fuera de muestra: excluirlas mejora todas las estrategias (zona de ruido de 14,2 a 15,0 $/operación; en esas semanas solo gana 4,0 $). No cambia ninguna conclusión. Comprar `NQ.v.0` (continuo por volumen) lo corregiría.
- **Datos de swing:**
  - QQQ no es el ETF UCITS que comprarías (cotiza en otro horario, en otra divisa y con otro TER).
  - La fiscalidad está simplificada.
- **Reutilización de datos:** ya se usaron para investigar estas familias. Ningún periodo es una prueba independiente.
- **Simulación de Topstep:**
  - Los intentos se solapan (no son independientes).
  - El flotante se aproxima con la MAE.
- **Errores conocidos pendientes:** ver `AUDITORIA_CODIGO.md` §3. Ninguno cambia las conclusiones, pero están documentados.

## 8. Cómo reproducirlo

```bash
cd laboratorio
python -m pytest -q tests                 # 27 tests
python data/fetch_etf_daily.py QQQ        # gratis (Alpaca); NQ 1 min ya está en alpaca/.lab_cache
python run_sistema_a.py                   # desarrollo + validación
python run_robustez_a.py
python run_sistema_a.py --prueba          # solo con reglas congeladas
python run_sistema_b.py --prueba
python run_swing_extra.py
python run_topstep.py
python run_plan.py
python run_clasificacion.py               # → reports/MATRIZ_ESTRATEGIAS.csv
python reports/make_charts.py             # → reports/graficos/
```

Entorno: Python 3.11.15 del sistema, el mismo que el del resto del proyecto. Python 3.12 existe, pero las dependencias (pandas 3.0, numpy 2.4, numba, databento, alpaca-py) están instaladas en la 3.11. Se añadieron `exchange_calendars`, `pytest` y `matplotlib`.
