# BOT 21 — Hora del día (deriva nocturna)

Ficha pre-registrada el 30-sep-2026, antes de ejecutar ningún backtest del laboratorio. Se genera desde el módulo `bot_lab/strategies/time_of_day.py`.

**Hipótesis:** Los rendimientos de los futuros de índices de EE. UU. se concentran fuera del horario regular, sobre todo en torno a la apertura europea (Boyarchenko, Larsen y Whelan, 2023).

**Mercado:** NQ/MNQ (salvo el BOT 26: oro/plata). **Marco:** 1m. **Sesión:** noche. **Frecuencia:** intradia.

## Reglas
BOT 21 — HORA DEL DÍA. Parte 1 (investigación): deriva media de NQ por franja horaria (no es una estrategia; ver
validation/regimenes.deriva_por_franja). Parte 2 (estrategias con hipótesis previa de la literatura):

Hipótesis: la "deriva nocturna" de los futuros de índices (Boyarchenko, Larsen y Whelan, 2023, "The Overnight
Drift", Review of Financial Studies): los rendimientos de los futuros de EE. UU. se concentran fuera del horario
regular, sobre todo en torno a la apertura europea (≈ 02:00-04:00 NY).

  21.1 Largo desde la reapertura de Globex (18:00 NY) hasta las 09:25 NY.
  21.2 Largo de 02:00 a 04:00 NY.
Sin stop (stop de catástrofe al 10 %) y sin objetivo; entrada y salida por tiempo con deslizamiento.
Se excluyen las sesiones en las que el contrato continuo cambia durante la posición (el salto de roll no es P&L).

## Variantes pre-registradas (2)
| Variante | Parámetros |
|---|---|
| 21.1 largo 18:00→09:25 NY | `{'desde': 1080, 'hasta': 565, 'cruza_medianoche': True}` |
| 21.2 largo 02:00→04:00 NY | `{'desde': 120, 'hasta': 240, 'cruza_medianoche': False}` |

**Base:** 21.2 largo 02:00→04:00 NY

**Vecindad de sensibilidad (se aplica a la variante que resulte elegida):** ver `vecindad()` en el módulo.
