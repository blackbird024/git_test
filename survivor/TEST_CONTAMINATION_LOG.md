# TEST CONTAMINATION LOG

| Fecha | Análisis | Datos usados | ¿Fuera de muestra? | Nota |
|---|---|---|---|---|
| 29-sep-2026 | Paso 3 del RSI(2) (validación original) | NQ 2015-2026, "posterior" desde 2023-03-22 | Fue su fuera de muestra **una vez**; ya consumido | `edges/nq_rsi2.md` |
| antes del 29-sep-2026 | Estudio de origen de la zona de ruido (`archive/reports/estudio_noise_area.md`) | NQ 2015-2026 | Consumido: la versión se eligió viendo todo el periodo | Auditoría, riesgo ALTO |
| 30-sep-2026 | Auditoría (`auditoria/experimentos/20260930_0633`) | NQ 2015-2026 completo | NO | Etiquetado como "posterior (ya visto)" |
| 30-sep-2026 | Laboratorio: TEST 2024-05-23 → 2026-09-28 abierto una vez para el BOT 24.3 | Ese tramo | Solo para el BOT 24.3 | Para RSI2 y ZR ese tramo ya estaba visto |
| 30-sep-2026 | **SURVIVOR ANALYSIS v1.0: todos los análisis** | NQ 2015-01-02 → 2026-09-28 | **NOT OUT-OF-SAMPLE** | No se reserva ningún TEST: no queda ninguno limpio |
| 30-sep-2026 | ES/NQ | — | — | Datos no descargados (15,06 $). Si se descargan, cualquier resultado será EXPLORATORY ONLY |

Único dato limpio futuro: el **forward test** en la demo de Pepperstone (EA APEX_Multiestrategia) desde el 30-sep-2026.
