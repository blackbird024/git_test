"""Lógica de señales COPIADA LITERALMENTE de `mt5_live_bot.py` (repositorio privado apex-datos), sin cambios.
Solo se ha quitado la dependencia de MetaTrader5. No editar a mano: regenerar desde el bot si cambia."""
import numpy as np
import pandas as pd

ZONE_LOOKBACK = 100
ZONE_MAX_AGE = 100
ZONE_TOUCHES_REQUIRED = 2
MITIGATION_THRESHOLD = 0.85
MIN_CONFLUENCE_SIGNALS = 2
TREND_MA = 200
SL_ATR_MULT = 1.2
TP_RATIO = 2.5
MAX_ATR_MULT_FILTER = 3.0

# # INDICADORES Y DETECCION DE ZONAS (misma logica validada en backtest)
# ===================================================================

def calc_indicators(df):
    high, low, close = df['high'].values, df['low'].values, df['close'].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = pd.Series(tr).rolling(14).mean().values
    ma = pd.Series(close).rolling(TREND_MA).mean().values
    return atr, ma


def find_zones(df, start, end):
    highs, lows, closes = df['high'].values, df['low'].values, df['close'].values
    demand, supply = [], []
    for i in range(max(start, 1), end - 1):
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1] and closes[i] > lows[i]:
            span = max((highs[max(start, i - 20):i + 1].max() - lows[max(start, i - 20):i + 1].min()) * 0.05, 0.0001)
            zone_low, zone_high = lows[i], lows[i] + span
            touches = sum(1 for j in range(max(start, i - 50), i) if lows[j] <= zone_high and highs[j] >= zone_low)
            if touches >= ZONE_TOUCHES_REQUIRED:
                demand.append(dict(low=zone_low, high=zone_high, touches=touches, index=i))
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1] and closes[i] < highs[i]:
            span = max((highs[max(start, i - 20):i + 1].max() - lows[max(start, i - 20):i + 1].min()) * 0.05, 0.0001)
            zone_high, zone_low = highs[i], highs[i] - span
            touches = sum(1 for j in range(max(start, i - 50), i) if lows[j] <= zone_high and highs[j] >= zone_low)
            if touches >= ZONE_TOUCHES_REQUIRED:
                supply.append(dict(low=zone_low, high=zone_high, touches=touches, index=i))
    return demand, supply


def is_mitigating(df, i, zone, zone_type):
    recent_low = df['low'].values[max(0, i - 4):i + 1].min()
    recent_high = df['high'].values[max(0, i - 4):i + 1].max()
    span = zone['high'] - zone['low']
    if span <= 0:
        return False
    pen = (zone['high'] - recent_low) / span if zone_type == "DEMAND" else (recent_high - zone['low']) / span
    return pen >= MITIGATION_THRESHOLD


def count_confirmations(df, i, zone, zone_type, atr, ma):
    conf = 0
    open_, close_ = df['open'].values[i], df['close'].values[i]
    if zone_type == "DEMAND" and close_ > open_:
        conf += 1
    elif zone_type == "SUPPLY" and close_ < open_:
        conf += 1
    if zone['touches'] >= 3:
        conf += 1
    if not np.isnan(ma[i]):
        if zone_type == "DEMAND" and close_ < ma[i]:
            conf += 1
        elif zone_type == "SUPPLY" and close_ > ma[i]:
            conf += 1
    if not np.isnan(atr[i]):
        recent_atr_avg = np.nanmean(atr[max(0, i - 50):i + 1])
        if recent_atr_avg > 0 and atr[i] < recent_atr_avg * MAX_ATR_MULT_FILTER:
            conf += 1
    return conf


def get_sl_tp(entry, direction, zone, atr_value, min_sl):
    sl_distance = max((atr_value * SL_ATR_MULT) if atr_value and not np.isnan(atr_value) else min_sl, min_sl)
    if direction == "BUY":
        if entry < zone['low']:
            return None
        sl = zone['low'] - sl_distance
        risk = entry - sl
    else:
        if entry > zone['high']:
            return None
        sl = zone['high'] + sl_distance
        risk = sl - entry
    if risk < sl_distance * 0.5:
        return None
    tp = entry + risk * TP_RATIO if direction == "BUY" else entry - risk * TP_RATIO
    return sl, tp, risk


def find_signal(df):
    """Devuelve (direction, sl, tp, risk) o None, usando SOLO velas ya cerradas."""
    atr, ma = calc_indicators(df)
    n = len(df)
    i = n - 1  # ultima vela cerrada
    if i < max(ZONE_LOOKBACK, TREND_MA):
        return None
    window_start = max(0, i - ZONE_MAX_AGE)
    demand, supply = find_zones(df, window_start, i)
    close = df['close'].values[i]
    min_sl = close * 0.001  # piso de SL: 0.1% del precio, por si ATR viene raro

    for zone_type, zones in [("DEMAND", demand), ("SUPPLY", supply)]:
        for zone in reversed(zones):
            if is_mitigating(df, i, zone, zone_type):
                conf = count_confirmations(df, i, zone, zone_type, atr, ma)
                if conf >= MIN_CONFLUENCE_SIGNALS:
                    direction = "BUY" if zone_type == "DEMAND" else "SELL"
                    result = get_sl_tp(close, direction, zone, atr[i], min_sl)
                    if result:
                        sl, tp, risk = result
                        return direction, sl, tp, risk
    return None
