# Forward testing de las supervivientes (desde el 30-sep-2026)

| Archivo | Uso |
|---|---|
| `survivors.csv` | Registro de operaciones forward (campos del pre-registro del Survivor Analysis) |
| `comparar.py` | `python -m forward_testing.comparar --ea <ruta>/APEX_registro.csv` importa el registro del EA y compara con el backtest |
| `deriva.py` | Avisos de deriva (WARNING/ALERT) con la expectativa móvil de 50 op. (ZR) / 15 op. (RSI2). **Solo avisa: no apaga nada** |
| `bandas_deriva.json`, `referencia_backtest.json` | Valores históricos (NOT OUT-OF-SAMPLE), generados por `python -m survivor.run_survivor` |

**Regla:** no se modifica ninguna estrategia porque aparezca una operación incómoda. Antes de 50 operaciones (ZR) o 15 (RSI2), las comparaciones son solo descriptivas.
