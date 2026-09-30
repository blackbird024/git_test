# git_test — CRT XAUUSD 4H + 15M (research, Phase 1)

Investigación objetiva de una regla CRT sobre XAUUSD usando solo 4H, 15M, precio, volumen y Kill Zones.
**Objetivo: saber si hay edge, no construir un bot.** La fase 2 (automatización) solo empieza si la fase 1 sobrevive.

**Estado actual: NO EVALUADO. No hay dataset** (ver `docs/AUDIT.md` y `docs/DATA_REQUIREMENTS.md`).

```
pip install -r requirements.txt
python -m pytest -q                      # reglas, DST, ejecución, lookahead, pipeline (datos sintéticos solo en tests)
python -m crt_xauusd.run                 # TRAIN + VALIDATION; TEST queda bloqueado
python -m crt_xauusd.run --unlock-test   # solo con las reglas congeladas; queda registrado
```

| Archivo | Contenido |
|---|---|
| `CONFIG.json` | Todos los parámetros (pre-registro v2.0.0) |
| `docs/PREREGISTRATION.md` | Reglas exactas, casos ambiguos, criterios, contabilidad de pruebas múltiples |
| `docs/DATA_REQUIREMENTS.md` | Formato exacto del dataset que falta |
| `docs/AUDIT.md` | Auditoría del repositorio y de las fuentes de datos |
| `crt_xauusd/` | `data` (carga, TZ, calidad), `signals` (sweep + engulfing), `execution`, `metrics`, `analysis` (splits, WF, regímenes), `falsification`, `report`, `run` |
| `reports/` | Salidas: `CRT_XAUUSD_FINAL.md`, CSVs, `charts/`, `RUN_MANIFEST.json` (commit, hashes) |
