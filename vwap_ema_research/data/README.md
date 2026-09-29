# Datos

Nunca se inventan ni se rellenan datos. Los minutos que faltan se cuentan y las sesiones incompletas no se operan.

| Instrumento | Fuente | Estado |
|---|---|---|
| MNQ, NQ | `../data/raw/NQ_1m_*.parquet` — Databento GLBX.MDP3, `NQ.v.0` (continuo por volumen), 1 min, UTC, 2015-01 → 2026-09 | disponible |
| MGC, GC | `../data/raw/GC_1m_*.parquet` — Databento GLBX.MDP3, `GC.v.0`, 1 min, UTC, 2015-01 → 2026-09 | disponible |
| XAUUSD | ninguno (`../data/mt5/` vacío) | **falta** |

Los parquet no están en git (licencia de Databento); copia privada en el repositorio `apex-datos`.

## Añadir XAUUSD
Exporta desde MT5 (Herramientas → Centro de historial, o `copy_rates_range` del paquete MetaTrader5) velas de 1 min o
15 min a `../data/mt5/XAUUSD_M1.csv` con columnas `time, open, high, low, close, tick_volume`. Indica la zona del
servidor en `instruments.XAUUSD.data_timezone_if_naive` (Pepperstone: `Etc/GMT-2` en invierno / `-3` en verano: si el
servidor cambia de hora, conviértelo antes a UTC). El volumen de un CFD es de **ticks**, no negociado: su VWAP no es
comparable con el de los futuros.
