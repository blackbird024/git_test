# Dataset necesario

## Qué falta

Barras **15M de XAUUSD** con **OHLC + volumen** (tick volume vale, siempre que se declare), sin huecos
artificiales, idealmente **≥ 8 años** (p. ej. 2017-2026). La regla es muy estricta y genera pocas señales. Con
menos histórico, el mínimo pre-registrado de 150 trades en TRAIN+VALIDATION probablemente no se alcanza.

No se necesitan datos de 1M/5M. Si el proveedor solo entrega 1M, `crt_xauusd.data.aggregate_to_15m`
los agrega a 15M antes de cualquier lógica; la estrategia nunca ve información de menos de 15M.

Fuentes razonables:
- **Export MT5 del broker con el que se operaría** (lo preferido: mismo feed, mismo tick volume, columna de spread).
  En MT5: ventana de símbolos → barras → XAUUSD M15 → exportar.
- Dukascopy (tick o M1 con volumen); hay que agregarlo a 15M.

## Archivos

```
data/XAUUSD_M15.csv
data/XAUUSD_M15.meta.json
```

### Formato A: `generic` (CSV)

```
timestamp,open,high,low,close,volume[,spread]
2024-01-10T07:15:00Z,2034.12,2035.40,2033.80,2035.02,1834,0.18
```
- `timestamp` = **apertura** de la barra. Con offset o `Z`, se usa tal cual; si no lleva zona, se interpreta con `timestamp_tz`.
- `spread` (opcional) en unidades de precio (USD).

### Formato B: `mt5` (export directo de MetaTrader 5)

```
<DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>
```

### Metadata (`XAUUSD_M15.meta.json`), obligatoria

```json
{
  "source": "MT5 export, broker X, account type Y",
  "broker": "X",
  "format": "mt5",
  "timestamp_tz": "NY+7",
  "timestamp_convention": "bar_open",
  "price_side": "bid",
  "volume_type": "tick",
  "spread_units_per_price": 100
}
```
- `timestamp_tz`: nombre IANA (`UTC`, `Europe/Athens`, ...) o `NY+7`, el reloj típico de servidor MT4/MT5
  (GMT+2 en invierno y GMT+3 en verano siguiendo el DST de EE. UU., que equivale exactamente a la hora de New York + 7 h).
  **Nunca un offset fijo.**
- `volume_type`: `tick` | `real` | `unknown`. Se muestra en el informe.

## Controles automáticos al cargar

Timestamps duplicados, desalineados o ambiguos por DST, OHLC inválidos (se descartan y se cuentan); barras con volumen 0;
huecos que no corresponden a la pausa diaria ni al fin de semana; buckets 4H incompletos. Todo queda en
`reports/DATA_AUDIT.json`.
