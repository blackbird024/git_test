# BOT 26 — Spread estadístico oro/plata

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/statistical_spread.py`.

**Hipótesis:** Los extremos del z-score del spread normalizado oro/plata revierten.

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 1D. **Sesión:** día UTC. **Frecuencia:** diaria.

## Reglas
BOT 26 — SPREAD ESTADÍSTICO. Parte oro/plata (GC/SI diarios de Databento). La parte NQ/ES queda pendiente de datos
(ver RESEARCH_LOG.md).

Hipótesis: los extremos del z-score del spread normalizado oro/plata revierten.

Reglas:
  1. Spread s = ln(GC ajustado) − ln(SI ajustado); z = (s − media 60 d) / desviación 60 d, al cierre diario.
  2. z < −Z -> largo spread (largo oro, corto plata); z > +Z -> corto spread. Entrada en la apertura siguiente.
  3. Salida en la apertura siguiente a que z cruce 0, o tras 20 sesiones.
Tamaño: 25.000 $ nocionales por pata (≈ 1 MGC y 1 SIL). Costes por operación completa: comisiones 1 $/lado/pata y
1 tick por lado y pata (MGC 1 $, SIL 5 $) = 16 $ × multiplicador.
Relación con el BOT 11 (pares oro/plata, 84 operaciones, insuficiente): misma familia; aquí con z-score fijo y
umbrales pre-registrados ±1 / ±1,5 / ±2. Días naturales UTC (liquidez a medianoche UTC: coste quizá infravalorado).

## Variantes pre-registradas (3)
| Variante | Parámetros |
|---|---|
| 26.1 z ±1.0 | `{'z': 1.0, 'ventana': 60, 'max_dias': 20}` |
| 26.2 z ±1.5 | `{'z': 1.5, 'ventana': 60, 'max_dias': 20}` |
| 26.3 z ±2.0 | `{'z': 2.0, 'ventana': 60, 'max_dias': 20}` |

**Base:** 26.2 z ±1.5

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
