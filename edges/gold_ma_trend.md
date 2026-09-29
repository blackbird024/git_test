# GOLD_MA_TREND_v1.0: seguimiento de tendencia con cruce de medias en el oro (GC, diario)

*Ficha escrita el 29-sep-2026, ANTES de programar y de ejecutar. Reglas de la especificación del usuario. Todas las
decisiones de datos, costes, métricas y criterios se fijan aquí. No se cambian después de ver resultados.*

## Hipótesis
El oro tiene tendencias de meses. Una regla mecánica (SMA 50 frente a SMA 200 en diario) capta la dirección dominante
con la frecuencia suficiente para ganar a pesar de los falsos cruces y de los costes.

## Contexto honesto (conocimiento previo)
- En este proyecto ya se probó el seguimiento de tendencia de AQR (momentum de series temporales, diario) en GC, NQ y
  ES: Sharpe 0,18, t 0,79, negativo en el fuera de muestra.
- También se probaron cruces EMA con ADX intradía en MGC: 0 de 24 variantes.
- El cruce 50/200 diario es una regla distinta y clásica, pero la familia "tendencia en el oro" no es nueva.
- Se prueban **3 hipótesis** (A, B y C): hay riesgo de pruebas múltiples.

## Datos
- **Fuente:** Databento GLBX.MDP3, `ohlcv-1d`, contrato continuo por volumen (`GC.v.0`), en
  `data/raw/daily/GC.parquet`.
- **Rango:** 7-jun-2010 → 27-sep-2026. Es todo el histórico diario disponible en el proyecto.
- **Velas:** día natural en UTC (00:00-24:00 UTC). El GC cotiza casi 23 h, así que el corte de las 00:00 UTC cae en
  plena sesión (19:00-20:00 NY).
- **Domingos:** la vela del domingo (reapertura, unas 2 h y ~2 % del volumen de un día normal) se **une a la del
  lunes**: apertura del domingo, máximo y mínimo de las dos, cierre y contrato del lunes.
- **Última vela:** se elimina si es un domingo sin lunes (vela incompleta).
- **Contrato continuo:** ajuste **hacia atrás aditivo** en cada cambio de contrato: se suma a todo el pasado el salto
  apertura nueva − cierre anterior. Es la misma metodología que en los estudios anteriores (`ajustar_rolls`).
  - Las medias y el P&L en dólares se calculan con los precios ajustados. Las diferencias de precio son exactas, así
    que equivalen a mantener y rodar la posición.
  - Los porcentajes (Sharpe y drawdown %) se calculan sobre el **precio real** del contrato, porque el ajuste aditivo
    distorsiona los porcentajes antiguos.
- **Auditoría antes del backtest:** rango, número de velas, huecos, duplicados, valores faltantes, velas imposibles,
  mayores movimientos (y si coinciden con cambios de contrato) y número y tamaño de los saltos de contrato.

## Reglas exactas
**Medias:** SMA 50 y SMA 200 de los cierres diarios ajustados, cada una con las últimas N velas, incluida la de hoy.

**Régimen al cierre de la vela D:**
- SMA50 > SMA200 → LARGO;
- SMA50 < SMA200 → CORTO;
- iguales → se mantiene el régimen anterior.

**Operaciones:**
- **Cruce confirmado:** el régimen de D es distinto del de D−1.
- **Ejecución:** a la **apertura de la vela D+1**, nunca al cierre de D.
- **A (50/200, largos y cortos):**
  - en cada cruce se cierra la posición y se abre la contraria;
  - siempre dentro del mercado después del primer cruce;
  - la primera posición se abre en el primer cruce, no al empezar los datos.
- **B (50/200, solo largos):** largo en el cruce al alza y fuera en el cruce a la baja.
- **C (20/100, largos y cortos):** como A, con SMA 20 y SMA 100.
- Sin stop, sin objetivo, sin trailing, sin parciales y sin filtros.

**Tamaño:** 1 contrato GC (100 oz) fijo.
- P&L en $ = diferencia de precio ajustada × 100.
- Para los porcentajes: **1× el nocional** (valor de 1 contrato al precio real del día anterior, sin
  apalancamiento).

**R por operación:** P&L / (ATR(20) diario × 100) en la entrada. Es una unidad de volatilidad, porque la regla no
tiene stop. ATR simple de 20 días, calculado con velas cerradas hasta D.

## Costes (por contrato GC y lado)
| Escenario | Comisión | Deslizamiento | Por lado | Ida y vuelta |
|---|---|---|---|---|
| 0 (referencia) | 0 | 0 | 0 | 0 |
| 1 (realista) | 2,50 $ | 1 tick (0,10 $/oz = 10 $) | 12,50 $ | 25 $ |
| 2 (conservador) | 5,00 $ | 3 ticks (30 $) | 35 $ | 70 $ |

- **Cambios de contrato con posición abierta:** en la realidad hay que cerrar el contrato viejo y abrir el nuevo. Se
  cobra **un ida y vuelta** del escenario en cada cambio de contrato con posición abierta.
- **Referencia:** comprar y mantener (siempre largo 1 contrato, con los mismos costes de roll).

## Periodos
- **Desarrollo (70 %):** hasta el 8-nov-2021. **Fuera de muestra (30 %):** desde el 9-nov-2021 (`config/particion.json`,
  `diario_GC`, fijado hace tiempo). El fuera de muestra no se usa para decidir nada.
- **Una sola simulación continua y causal.** Las medias del inicio del fuera de muestra usan datos anteriores (es
  historia, no fuga).
  - **Desarrollo:** operaciones abiertas en desarrollo; la que siga abierta el 8-nov-2021 se cierra ese día a efectos
    del informe de desarrollo.
  - **Fuera de muestra:** operaciones abiertas desde el 9-nov-2021. La operación que pasa de un periodo al otro se
    informa aparte.
  - **Métricas diarias** (Sharpe, drawdown, exposición): días de cada periodo.
- **Periodos de mercado** (fijados por la historia conocida del oro, no por resultados):
  - 2010-2012: final del ciclo alcista;
  - 2013-2015: mercado bajista;
  - 2016-2018: lateral;
  - 2019-2020: alcista;
  - 2021-2023: lateral y volátil;
  - 2024-2026: alcista fuerte.

## Métricas
**Por operación:**
- operaciones, operaciones al año, neto, R medio, PF, acierto;
- ganancia y pérdida media, expectativa, mejor y peor operación;
- duración media y máxima, rachas.

**Diarias:**
- Sharpe y Sortino anualizados (252 días);
- drawdown máximo en $ y en %, y duración del peor drawdown;
- % de tiempo en el mercado y exposición larga y corta;
- t de los rendimientos diarios.

**Desgloses:**
- por año y por periodo de mercado;
- largos frente a cortos;
- distribución de resultados;
- duración de las tendencias (días entre cruces).

## Criterios de decisión (escenario 1, fijados ANTES de ejecutar)
Con tan pocas operaciones, la t por operación no es fiable (se informa, pero no decide). La significancia se mide con
la **t de los rendimientos diarios** (= Sharpe anual × √años, aproximadamente). Tiene autocorrelación, así que se lee
con cautela.

**VALIDATED** solo si se cumplen todos:
1. Desarrollo: neto > 0, PF > 1 y Sharpe > 0.
2. Fuera de muestra: neto > 0, PF > 1 y Sharpe ≥ 50 % del Sharpe de desarrollo.
3. Periodo completo: t de los rendimientos diarios ≥ 2.
4. Escenario 2: neto > 0 en el periodo completo.
5. No depende de una sola operación: neto sin la mejor operación > 0.
6. **Valor de la regla frente a comprar y mantener** (Sharpe del periodo completo):
   - en A y C (largos y cortos), el Sharpe de la estrategia es ≥ el de comprar y mantener;
   - en B (solo largos), su Sharpe es ≥ el de comprar y mantener, **o** tiene un Sharpe ≥ 80 % del de comprar y
     mantener con un drawdown máximo % menor que la mitad.
   Si no, la ganancia se debe a la subida del oro, no a la regla.

**FAILED:**
- neto < 0 con costes del escenario 1 (periodo completo); **o**
- desarrollo positivo y fuera de muestra con neto < 0 (**FAILED / OVERFIT**).

**INCONCLUSIVE:** cualquier otro caso (positivo pero sin significancia, sin valor frente a comprar y mantener, o
con muy pocas operaciones).

Cada hipótesis se clasifica por separado. Si las tres son FAILED, la investigación se detiene.
