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

## MGC (disponible desde el 10 de octubre de 2026)
- **Datos que hay:**
  - Las velas de 5 minutos de GC que existen (`alpaca/.lab_cache/dbn_GC_5m.pkl`) **no tienen volumen**.
  - Las de 1 minuto con volumen (`GC.c.0`) solo tienen 25.000 velas en 2 años: el contrato del mes en curso del oro casi no se negocia.
- **Qué hace falta:** OHLCV de 1 minuto de `GC.v.0` o `MGC.v.0` (continuo por volumen) de Databento, de 2018 a 2026.
  - Coste estimado con `metadata.get_cost`, el 10 de octubre de 2026: **GC.v.0 ≈ 11,16 USD; MGC.v.0 ≈ 10,37 USD**.
  - **No se ha comprado:** requiere tu autorización.
- **Comprado** con autorización el 10 de octubre de 2026, por 11,16 USD: GC.v.0, 3.057.355 velas de 1 minuto.
  - `python vwap_lab/tools/download_gc_databento.py` genera `data/cache/MGC_5m.csv` (no vuelve a descargar si `GC_v0_1m.pkl` existe).
  - Databento marca algunos días como de calidad reducida (por ejemplo, 2018-10-21, 2019-01-15 y 2019-02-22).
  - 44 rollovers. Las sesiones con cobertura < 90 % se excluyen.
