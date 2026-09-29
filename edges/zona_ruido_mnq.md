# ZONA_RUIDO_MNQ_v1.0: momentum intradía con "zona de ruido" en el Nasdaq (1 MNQ)

*Ficha escrita el 29-sep-2026. La estrategia NO es nueva: es la regla de Zarattini, Aziz y Barbon (2024), "Beat the
Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)". Ya se validó en este proyecto
(`archive/reports/estudio_noise_area.md`: la versión con 1 contrato fijo cumplió PF 1,19, t 2,15 y fue positiva en el
desarrollo y en el fuera de muestra). Ahora se porta al marco actual (`src/strategies/zona_ruido.py`) para usarla a
diario en papel.*

## La idea en una frase
Cada día el Nasdaq tiene un "ruido normal" alrededor de la apertura. Si a una hora concreta el precio está más lejos
de lo normal para esa hora, es que hay un desequilibrio de verdad: se sigue ese movimiento hasta el cierre, o hasta que
el precio pierde el VWAP.

## Reglas (5 pasos, sin interpretación)
1. **Antes de abrir (se sabe la víspera):** para cada media hora del día hay un porcentaje de "ruido normal" (sigma):
   cuánto se ha alejado el precio de la apertura, a esa hora, de media en los últimos 14 días.
2. **A las 09:30 NY (15:30 en Italia), con la apertura del día:**
   - banda superior = max(apertura, cierre de ayer) × (1 + sigma);
   - banda inferior = min(apertura, cierre de ayer) × (1 − sigma).
   Cada media hora tiene su par de bandas.
3. **Cada media hora, de 10:00 a 15:30 NY (16:00-21:30 en Italia),** se mira el cierre de la vela de 1 minuto anterior:
   - Sin posición: si está **por encima de la banda superior → COMPRAR**; si está **por debajo de la inferior →
     VENDER**; si está entre las dos, nada.
4. **Con posición, en cada media hora:**
   - **Largo:** se cierra si el precio está por debajo del máximo entre la banda superior y el VWAP. Si además está bajo
     la banda inferior, se da la vuelta a corto.
   - **Corto:** simétrico, con el mínimo entre la banda inferior y el VWAP.
5. **Todo se cierra al final de la sesión** (16:00 NY = 22:00 en Italia). Nunca queda nada abierto de noche.

**Tamaño:** 1 MNQ fijo. **Costes en el backtest:** 1 tick de deslizamiento en la entrada y en la salida, más 1 $ por
contrato y lado.

**Horas en Italia:** casi todo el año son NY + 6 h. En las semanas de desajuste del cambio de hora (marzo y
octubre/noviembre) son NY + 5 h. La herramienta diaria da siempre la hora de Italia correcta.

## Estado de la evidencia (honesto)
- **Ventaja pequeña:** unos +7 $ por operación con 1 MNQ, después de costes, y unas 230 operaciones al año.
- **Años negativos:** 2016, 2017 y 2019.
- **Ya no queda fuera de muestra "virgen":** el periodo desde 2023 ya se ha visto. La siguiente prueba honesta es
  **hacia delante**, en papel o demo.
- **No sirve para aprobar Apex en 30 días.** Además, la versión validada no tiene stop duro entre medias horas, y la
  versión con stop duro no cumplió (t 1,2).

## Prueba hacia delante en papel (criterios fijados ANTES de empezar)
- **Duración:** 3 meses naturales desde el primer día operado.
- **Registro:** cada operación en `papel/zona_ruido_registro.csv` (señal, precio de la herramienta, precio real,
  diferencia en ticks y resultado).
- **Qué se evalúa (no si "gana"):**
  1. Disciplina: 0 señales saltadas o inventadas.
  2. Deslizamiento real medio ≤ 1 tick por lado (es lo que asume el backtest).
  3. Resultado dentro del rango esperado: el P&L de 3 meses en papel no está por debajo del **percentil 5** de los
     P&L de 3 meses del backtest (se calcula en `reports/ZONA_RUIDO_MNQ_v1.0/`).
- **Se abandona antes** si la caída desde el máximo en papel supera el **percentil 95** del drawdown de 3 meses del
  backtest.
