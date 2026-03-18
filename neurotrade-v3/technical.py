import logging
log = logging.getLogger("Technical")

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calc_ema(closes, period):
    if len(closes) < period:
        return []
    ema = [sum(closes[:period]) / period]
    k = 2 / (period + 1)
    for price in closes[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema

def calc_macd(closes):
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    if not ema12 or not ema26:
        return None, None, "none"
    min_len = min(len(ema12), len(ema26))
    macd_line = [ema12[-(min_len-i)] - ema26[-(min_len-i)] for i in range(min_len)]
    signal = calc_ema(macd_line, 9)
    if not signal or len(macd_line) < 2:
        return None, None, "none"
    crossover = "none"
    if macd_line[-1] > signal[-1] and macd_line[-2] <= signal[-2]:
        crossover = "bullish"
    elif macd_line[-1] < signal[-1] and macd_line[-2] >= signal[-2]:
        crossover = "bearish"
    return round(macd_line[-1], 4), round(signal[-1], 4), crossover

def analyze(bars, symbol):
    if not bars or len(bars) < 20:
        return {"rsi": 50, "macd_crossover": "none", "ema_trend": "neutral", "tech_score": 0, "signal": "NEUTRAL", "price": 0}
    closes = [float(b.get("c", b.get("close", 0))) for b in bars]
    price = closes[-1]
    rsi = calc_rsi(closes) or 50
    _, _, macd_cross = calc_macd(closes)
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    ema_trend = "neutral"
    if ema9 and ema21:
        if ema9[-1] > ema21[-1]: ema_trend = "bullish"
        elif ema9[-1] < ema21[-1]: ema_trend = "bearish"
    score = 0
    if rsi < 35: score += 2
    elif rsi < 50: score += 1
    elif rsi > 70: score -= 2
    elif rsi > 60: score -= 1
    if macd_cross == "bullish": score += 2
    elif macd_cross == "bearish": score -= 2
    if ema_trend == "bullish": score += 1
    elif ema_trend == "bearish": score -= 1
    if score >= 4: signal = "STRONG_BUY"
    elif score >= 2: signal = "BUY"
    elif score <= -4: signal = "STRONG_SELL"
    elif score <= -2: signal = "SELL"
    else: signal = "NEUTRAL"
    return {"rsi": round(rsi,1), "macd_crossover": macd_cross, "ema_trend": ema_trend, "tech_score": score, "signal": signal, "price": round(price,4)}
