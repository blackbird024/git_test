# Alpaca Markets

Herramientas para operar en [Alpaca](https://alpaca.markets). Usa paper trading por defecto.

```bash
pip install -r requirements.txt
export APCA_API_KEY_ID=...        # nunca lo subas al repo
export APCA_API_SECRET_KEY=...
```

## Cliente manual: `alpaca_client.py`

```bash
python alpaca_client.py           # cuenta y posiciones
python alpaca_client.py quote AAPL
python alpaca_client.py buy AAPL 1
```

## Estrategia automática: `auto_strategy.py`

La estrategia y las cuentas se definen en `strategy_config.json`.

```bash
python auto_strategy.py                     # simula en todas las cuentas
python auto_strategy.py --execute           # envía órdenes (solo si el mercado está abierto)
python auto_strategy.py --account principal # solo una cuenta
```

Estrategia "conservadora" incluida:

| ETF | Peso | Filtro de tendencia |
|-----|------|---------------------|
| SPY (S&P 500) | 20% | sí |
| VIG (dividendos crecientes) | 10% | sí |
| BND (bonos agregados) | 15% | no |
| SHY (Tesoro 1-3 años) | 10% | no |
| GLD (oro) | 5% | sí |
| Efectivo | 40% | |

- **Filtro de tendencia:** si el precio está bajo su media de 200 días, ese peso pasa a efectivo.
- **Rebalanceo:** solo cuando una posición se desvía más de un 20% de su objetivo.
- **Freno de emergencia:** si la cuenta cae un 5% bajo `initial_capital`, vende todo lo que tiene filtro de tendencia.
- **Seguridad:** las cuentas reales (`"paper": false`) solo operan con `--allow-live`. Si hay órdenes abiertas o el mercado está cerrado, no opera.

### Replicar en otras cuentas

1. Agrega la cuenta en `strategy_config.json`:
   ```json
   {"name": "cuenta2", "key_env": "CUENTA2_KEY", "secret_env": "CUENTA2_SECRET",
    "paper": true, "initial_capital": 50000}
   ```
2. Define esas variables de entorno con las claves de la cuenta.
3. Para otra estrategia, copia `strategy_config.json`, cambia los pesos y usa `--config`.

## Estrategia intradía: `vwap_intraday.py`

Reversión a la VWAP, la misma lógica que el EA de MT5 (`mt5/VwapReversion.mq5`). Solo cuentas PAPER.
Cierra todo a las 15:50 de Nueva York.

```bash
python vwap_intraday.py --backtest 90                    # QQQ, últimos 90 días
python vwap_intraday.py --backtest 90 --symbols QQQ GLD
python vwap_intraday.py --live                           # opera QQQ hasta el cierre
```

**Ojo:** si la cuenta también tiene posiciones de largo plazo en el mismo símbolo (QQQ, GLD),
la estrategia intradía las cerraría. Por eso QQQ se usa solo en la intradía y no está en la de largo plazo.
Con el plan gratuito (datos IEX), QQQM e IAU tienen muchos minutos sin datos.

## Ruptura del rango de apertura: `orb_intraday.py` (solo backtest)

Seguimiento de tendencia: marca el máximo y el mínimo de los primeros N minutos y opera la ruptura.
Pensada para el oro, donde la reversión a la VWAP perdía dinero.

```bash
python orb_intraday.py --backtest 180 --symbols GLD   # compara 9 variantes
```
