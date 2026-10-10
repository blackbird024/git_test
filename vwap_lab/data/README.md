# Datos del laboratorio VWAP + EMA

El VWAP necesita **volumen real**. Cada instrumento necesita un CSV con velas de 5 minutos.

```
timestamp,open,high,low,close,volume,contract
```

- **timestamp:** ISO 8601 con zona horaria y la marca en la **apertura** de la vela.
- **contract:** identificador del contrato. Si cambia, es un rollover.

## MNQ (disponible)
`python vwap_lab/tools/build_5m_from_databento.py` genera `data/cache/MNQ_5m.csv`.
- **Origen:** velas de 1 minuto de Databento `NQ.c.0` ya descargadas, de 2018 a octubre de 2026, con volumen.
- **Contrato:** continuo por calendario, sin ajuste. `contract` es el `instrument_id` de Databento (35 rollovers).

## MGC (NO disponible)
- **Datos que hay:**
  - Las velas de 5 minutos de GC que existen (`alpaca/.lab_cache/dbn_GC_5m.pkl`) **no tienen volumen**.
  - Las de 1 minuto con volumen (`GC.c.0`) solo tienen 25.000 velas en 2 años: el contrato del mes en curso del oro casi no se negocia.
- **Qué hace falta:** OHLCV de 1 minuto de `GC.v.0` o `MGC.v.0` (continuo por volumen) de Databento, de 2018 a 2026.
  - Coste estimado con `metadata.get_cost`, el 10 de octubre de 2026: **GC.v.0 ≈ 11,16 USD; MGC.v.0 ≈ 10,37 USD**.
  - **No se ha comprado:** requiere tu autorización.
- **Después de comprarlos:**
  - Construir `data/cache/MGC_5m.csv` con el mismo esquema.
  - Ejecutar `python -m vwap_lab.run_all --step all`.
