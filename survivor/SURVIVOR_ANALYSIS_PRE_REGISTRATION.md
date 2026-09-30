# SURVIVOR ANALYSIS v1.0 — PRE-REGISTRO

30-sep-2026. Escrito **antes** de ejecutar ningún análisis y guardado en git antes del primer cálculo.

- No se cambian las preguntas, los umbrales ni las reglas de interpretación después de ver resultados.
- Cualquier patrón nuevo va a `POST_HOC_OBSERVATIONS.md` como **OBSERVATION — NOT VALIDATED**.
- **Nada de este análisis modifica las estrategias ni el EA.**

## 0. Objeto y alcance
- **RSI2_SURVIVOR_V1** y **NOISE_ZONE_SURVIVOR_V1**: código original sin cambios (ver `SURVIVOR_PROJECT_AUDIT.md`).
- **Periodo:** 2015-01-02 → 2026-09-28. Todo **NOT OUT-OF-SAMPLE** (ver `TEST_CONTAMINATION_LOG.md`).
- **Unidades:**
  - $ con 1 MNQ;
  - % del precio de entrada;
  - P&L normalizado por ATR: neto en puntos / ATR(14) diario RTH del día anterior (ambas estrategias);
  - R del proyecto para el RSI(2): rendimiento / volatilidad de 20 sesiones.
- **Semilla:** 20260930. **Bootstrap:** bloques de 20 sesiones sobre el P&L diario, 5.000 réplicas (2.000 en celdas de régimen).

## 1. Preguntas (confirmatorias)
| # | Pregunta |
|---|---|
| Q1 | ¿El edge del RSI(2) persiste al descomponerlo por régimen? |
| Q2 | ¿Y el de la zona de ruido? |
| Q3 | ¿En qué condiciones funciona cada una? |
| Q4 | ¿En cuáles falla? |
| Q5 | ¿Las ganadoras y las perdedoras difieren ANTES de entrar? |
| Q6 | ¿El edge es estructural o está concentrado en el tiempo? |
| Q7 | ¿Explotan fenómenos distintos? |
| Q8 | ¿Su combinación reduce el drawdown a igual riesgo? |
| Q9 | ¿Lo que ayuda a una perjudica a la otra? |
| Q10 | ¿Qué hay que vigilar en el forward? |

## 2. Rasgos previos a la entrada (solo información conocida antes de la entrada)
"Día anterior" = última sesión RTH completa antes de la entrada. Para el RSI(2), que entra a las 18:00, es la sesión que acaba de cerrar.

| Rasgo | Definición | Clases |
|---|---|---|
| VOL (ATR relativo) | ATR(14)/ATR(250) diario RTH del día anterior | BAJA < 0,8 ≤ NORMAL ≤ 1,2 < ALTA (umbrales fijos del laboratorio) |
| VOL (realizada) | Desviación de 20 días de los rendimientos diarios RTH, en tercil **expansivo** (cuantiles con los días anteriores; mínimo 250 días) | baja / media / alta |
| TENDENCIA | ER20 = \|C − C₋₂₀\| / Σ\|ΔC\| y signo de C − C₋₂₀ | TREND UP (ER > 0,3 y subida), TREND DOWN (ER > 0,3 y bajada), RANGE |
| DISTANCIA VWAP | **ZR:** (cierre del minuto anterior − VWAP RTH) / ATR14 diario, con signo a favor de la operación. **RSI2:** (cierre de la sesión − VWAP de la sesión CME) / ATR14 | cerca / moderado / extremo por terciles de \|valor\| de cada estrategia (descriptivo) |
| HUECO | (apertura RTH − cierre RTH anterior) / ATR14 | terciles de \|hueco\| (descriptivo) y signo |
| POSICIÓN DE LA APERTURA | apertura RTH respecto al rango RTH anterior | encima del máximo / mitad alta / mitad baja / debajo del mínimo |
| RETORNO NOCTURNO | (precio a las 09:29 − apertura de Globex a las 18:00) / ATR14 | terciles (descriptivo) |
| RANGO NOCTURNO | (máx − mín 18:00-09:29) / ATR14 | terciles |
| RANGO DEL DÍA ANTERIOR | rango RTH anterior / ATR14 | < 0,8 contracción; 0,8-1,2 normal; > 1,2 expansión |
| HORA (solo ZR) | hora NY de entrada | 10:00, 10:30-11:00, 11:30-13:30 (mediodía), 14:00-15:30 (tarde) |
| DÍA | día de la semana de la entrada (NY) | — |
| RSI2 específico | RSI(2) en la señal (< 5 / 5-10 / 10-20); rendimiento de la sesión de la señal en ATR (terciles); distancia a la SMA200 (terciles) | — |

- **ZR:** los rasgos de "hoy" (hueco, apertura, noche) son conocidos antes de las 10:00 ✓.
- **RSI2:** el hueco, la apertura y la noche se refieren a la sesión de la señal. La noche **posterior** a la entrada no es un rasgo previo y no se usa.

## 3. Pruebas y reglas de interpretación (fijadas ahora)
Veredictos: **CONFIRMATION** / **WEAK EVIDENCE** / **CONTRADICTION** / **INCONCLUSIVE**. "Celda con muestra" = ≥ 30 operaciones (ZR) o ≥ 15 (RSI2).

| Prueba | CONFIRMATION | WEAK EVIDENCE | CONTRADICTION | INCONCLUSIVE |
|---|---|---|---|---|
| Q1/Q2 régimen (por cada variable: VOL, TENDENCIA) | Expectativa > 0 en ≥ 2/3 de las celdas con muestra y ninguna con IC95 superior < 0 | Mayoría > 0, alguna ≤ 0 | Alguna celda con IC95 superior < 0, o > 100 % del neto viene de una sola celda con el resto ≤ 0 | < 2 celdas con muestra |
| Q5 ganadoras/perdedoras | Diferencias pequeñas: el edge no se explica por un rasgo previo único (informativo) | — | — | Siempre descriptivo; p de Mann-Whitney con Bonferroni sobre los rasgos |
| Q6 concentración temporal (años) | ≥ 60 % de años > 0 y ningún año > 50 % del neto | Una de las dos falla | Las dos fallan | < 5 años |
| Rachas | Racha máxima perdedora y ganadora dentro del p5-p95 de 5.000 permutaciones | Una fuera | — | — |
| Costes ×1,5 / ×2 / ×3 | Expectativa > 0 con ×2 | > 0 con ×1,5 y ≤ 0 con ×2 (**COST FRAGILITY**) | ≤ 0 con ×1,5 | — |
| Deslizamiento +1/+2/+3 ticks por ejecución | > 0 con +2 | > 0 solo con +1 | ≤ 0 con +1 | — |
| Retraso +1/+2/+3/+5 min (entrada y salidas) | > 0 con +3 | > 0 con +1 pero no con +3 | ≤ 0 con +1 | — |
| Sensibilidad (uno a uno) | Todas las perturbaciones > 0 | ≥ 2/3 > 0 | < 2/3 > 0 | — |
| Valores atípicos (quitar los 1/3/5/10 mejores) | > 0 sin los 5 mejores | > 0 sin el mejor pero no sin los 5 | ≤ 0 sin el mejor | — |
| Concentración | Informativo: los 10 % mejores > 100 % del neto → **TAIL DEPENDENCE** (etiqueta, no veredicto) | | | |
| Walk-forward congelado (ZR trimestral y anual; RSI2 anual) | ≥ 60 % de ventanas > 0 | 45-60 % | < 45 % | — |
| Subperiodos (2015-17, 2018-20, 2021-23, 2024-26) | Los 4 > 0 | 3 de 4 | ≤ 2 de 4 | — |
| Crisis (ver §4) | Expectativa en días de crisis ≥ 0 | < 0 con IC que incluye 0 | IC95 superior < 0 | < 15 operaciones |
| Aleatorización (ver §5) | p ≤ 0,05 | 0,05 < p ≤ 0,20 | p > 0,20 | — |
| Monte Carlo (1 MNQ, 1 año) | P(DD ≥ 5.000 $) < 10 % | 10-25 % | > 25 % | — |
| Q7 ¿mismo edge? | Correlación diaria \|ρ\| < 0,2 y todas las condicionadas \|ρ\| < 0,3 → fenómenos distintos | Global < 0,2 pero alguna condicionada ≥ 0,3 | Global ≥ 0,2 | — |
| Q8 cartera | Con igual riesgo (misma volatilidad diaria que la ZR sola), alguna mezcla tiene DD95 de Monte Carlo menor que 100/0 **y** 0/100 | Menor que una de las dos | Ninguna | — |

## 4. Crisis / extremos (metodología objetiva, sin elegir eventos)
- **Días de volatilidad extrema:** volatilidad realizada de 20 días del día anterior en el percentil ≥ 95 **expansivo**.
- **Días de crash:** rendimiento RTH del día anterior ≤ percentil 2 expansivo.
- **Tendencia fuerte:** \|rendimiento de 20 días\| del día anterior ≥ percentil 95 expansivo.
- Todo es causal. También se informa, como **descripción no causal**, el resultado en los días que *ellos mismos* fueron extremos (percentil del día, calculado a posteriori).

## 5. Pruebas de aleatorización (1.000 réplicas cada una, mismos costes)
**ZR-N1 (dirección aleatoria):**
- mismas horas de entrada y de salida que cada operación real, con sentido aleatorio;
- estadístico: expectativa neta;
- p = proporción de réplicas ≥ la real.

**ZR-N2 (momento aleatorio):**
- mismos días y mismo número de operaciones por día;
- entrada en un chequeo aleatorio (10:00-15:30), con sentido aleatorio;
- duración tomada de una operación real al azar, con salida como máximo al cierre;
- precios de apertura de 1 min y 1 tick + 1 $ por lado.

**RSI2-N1 (días aleatorios con el filtro SMA200):**
- mismo número de operaciones;
- entradas en sesiones al azar con cierre > SMA200;
- duración tomada de las operaciones reales;
- mismos costes;
- mide si el RSI<20 añade algo sobre "estar comprado en tendencia alcista".

**RSI2-N2 (días aleatorios sin filtro):** igual que N1, sin el filtro.

## 6. Sensibilidad (uno a uno, NO es optimización; no se elige nada)
| Estrategia | Parámetro | Valores |
|---|---|---|
| RSI2 | entrada | 18, 19, [20], 21, 22 |
| RSI2 | salida | 65, [70], 75 |
| RSI2 | máximo de sesiones | 4, [5], 6 |
| RSI2 | SMA | 180, [200], 220 |
| ZR | días de ruido | 13, [14], 15 |
| ZR | multiplicador | 0,9, [1,0], 1,1 |

## 7. Cartera (igual riesgo)
- **Series diarias:**
  - la ZR con P&L diario (cierra en el día);
  - el RSI(2) con **mark-to-market diario**: variación del valor de la posición al cierre de cada sesión y la salida en la apertura, más costes. Así el drawdown no se subestima. También se informa la serie por día de salida de la auditoría.
- **Presupuesto de riesgo:** la volatilidad diaria de la ZR sola con 1 MNQ.
  - Pesos por reparto de riesgo 100/0, 75/25, 50/50, 25/75, 0/100 (ZR/RSI2): `w_i ∝ reparto_i / σ_i`, reescalados para que la volatilidad de la cartera = σ_ZR.
  - σ estimadas **solo con datos hasta el 2023-03-21** (desarrollo del proyecto), como en la auditoría.
  - **Se presentan todas; no se elige ninguna.**
- **Métricas:**
  - rentabilidad anual, Sharpe, Sortino, DD máximo, Calmar;
  - peor año, % de años negativos, peor mes;
  - Monte Carlo a 1 año: DD p50/p95/p99, P(año negativo), P(DD ≥ 5.000 $), P(algún día ≤ −1.000 $).
  - Los límites son los del EA: 1.000 $ diarios y 5.000 $ de caída.
- **Correlaciones:** diaria, mensual y de drawdown.
- **Correlaciones condicionadas** por régimen de VOL (3 clases) y de TENDENCIA (3), y por franja de la ZR (P&L de la ZR con entradas a las 10:00-11:00 frente a 14:00-15:30, contra el RSI2 del mismo día).
- **Solapamiento:** días con ambas posiciones abiertas; mismo sentido (ZR largo mientras el RSI2 está largo) y sentido opuesto.

## 8. Forward (desde el 30-sep-2026)
- **Registro:** `forward_testing/survivors.csv` más el `APEX_registro.csv` del EA.
- **Deriva:** expectativa móvil de las últimas 50 operaciones (ZR) o 15 (RSI2) comparada con el percentil 5 de la distribución histórica de medias de 50/15 operaciones consecutivas (bootstrap por bloques). Por debajo → **WARNING**, sin apagar ni cambiar nada.
- **Comparaciones:** solo con ≥ 50 operaciones de la ZR o ≥ 15 del RSI2. Antes de eso, solo se describen.

## 9. Pruebas múltiples
- **Confirmatorio:** solo las celdas de §3 para las preguntas de §1.
- **Exploratorio:** todo lo demás (día de la semana, hora, meses, rasgos específicos). Ninguna p < 0,05 exploratoria se presenta como evidencia.
- Q5 usa Bonferroni sobre los rasgos.
