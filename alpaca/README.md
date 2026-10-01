# Alpaca Markets

Cliente mínimo para conectarse a [Alpaca](https://alpaca.markets). Usa paper trading por defecto.

```bash
pip install -r requirements.txt
export APCA_API_KEY_ID=...        # no lo subas al repo
export APCA_API_SECRET_KEY=...
python alpaca_client.py           # cuenta y posiciones
python alpaca_client.py quote AAPL
python alpaca_client.py buy AAPL 1
```

Para la cuenta real: `export APCA_PAPER=false` (pide confirmación antes de cada orden).
