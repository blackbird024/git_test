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
| Efectivo | 45% | |

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
la estrategia intradía las cerraría. Por eso QQQ y GLD se usan solo en las intradía y no están en la de largo plazo.
Con el plan gratuito (datos IEX), QQQM e IAU tienen muchos minutos sin datos.

## Ruptura del rango de apertura: `orb_intraday.py`

Seguimiento de tendencia: marca el máximo y el mínimo de los primeros N minutos y opera la ruptura.
Pensada para el oro, donde la reversión a la VWAP perdía dinero.

```bash
python orb_intraday.py --backtest 180 --symbols GLD   # compara 9 variantes
python orb_intraday.py --live                         # GLD: rango 60 min, stop en el medio, sale al cierre
```

En vivo usa la variante que fue positiva en las dos mitades del backtest: rango de 9:30 a 10:30,
stop en el punto medio del rango y salida a las 15:50. Una operación por día, 0.5% de riesgo.

## Cripto intradía: `crypto_intraday.py` (solo backtest)

VWAP y ruptura de rango en BTC, ETH, SOL (solo compras, comisión de Alpaca incluida).

```bash
python crypto_intraday.py --backtest 180 --symbols BTC/USD ETH/USD
```

Resultado (180 días): sin comisiones algunas variantes ganan, pero con la comisión de ~0.25% por lado
**todas pierden mucho dinero**. No es viable operar cripto intradía en Alpaca con estas comisiones.

## Cripto diaria: `crypto_trend.py`

BTC, ETH y SOL a partes iguales ($10,000 en total), cada una solo mientras su cierre diario esté
sobre la media de 200 días. Se ejecuta una vez al día.

```bash
python crypto_trend.py --backtest   # compara estrategias diarias desde 2021
python crypto_trend.py              # simulación de hoy
python crypto_trend.py --execute    # envía las órdenes
```

Backtest 2021-2026 con comisiones (cartera de las tres): +65% anual con caída máxima del 40%,
frente a +86% anual y caída del 85% comprando y manteniendo.

## Laboratorio de estrategias: `strategy_lab.py`

Compara 8 estrategias intradía (2 años de velas de 1 minuto SIP) y 5 de varios días (desde 2016)
con los mismos datos, costes y métricas, incluidas el peor día y la caída máxima (reglas de prop firms).

```bash
python strategy_lab.py --symbols QQQ GLD SPY
```

## Laboratorio de swing trading: `swing_lab.py`

12 estrategias de días a semanas (RSI(2), Double 7s, IBS, Bollinger, Donchian, MACD...) en velas
diarias desde 2016, con resumen de robustez entre activos.

```bash
python swing_lab.py --symbols QQQ SPY DIA IWM GLD
```

Mejor resultado: **IBS** (comprar al cierre si cerró en el 20% inferior del rango del día, vender
cuando cierre en el 20% superior). Positiva en las dos mitades en los 5 activos y estable con
otros parámetros. Cartera QQQ + GLD a partes iguales: +14% anual, caída máxima -9.7%.

## IBS swing: `ibs_swing.py`

La estrategia de swing ganadora (ver `swing_lab.py`) en QQQ y GLD, $10,000 cada uno.
Igual que el EA `mt5/IbsSwing.mq5`. Hay que ejecutarla una vez al día entre las 15:50 y las 16:00 de Nueva York.

```bash
python ibs_swing.py             # muestra el IBS y lo que haría
python ibs_swing.py --execute   # envía las órdenes (solo dentro del horario)
```
