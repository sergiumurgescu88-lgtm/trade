"""
indicators.py — Indicatori tehnici calculati din preturile istorice
RSI, MACD, EMA — fara librarii externe (doar math standard Python)
"""
import logging
from typing import Optional

log = logging.getLogger("Indicators")


# ============================================================
# EMA — Exponential Moving Average
# ============================================================

def ema(prices: list, period: int) -> list:
    """Calculeaza EMA pentru o lista de preturi."""
    if len(prices) < period:
        return []
    k = 2 / (period + 1)
    result = [sum(prices[:period]) / period]  # primul EMA = SMA
    for price in prices[period:]:
        result.append(price * k + result[-1] * (1 - k))
    return result


def ema_last(prices: list, period: int) -> Optional[float]:
    """Returneaza ultimul EMA calculat."""
    e = ema(prices, period)
    return e[-1] if e else None


# ============================================================
# RSI — Relative Strength Index
# ============================================================

def rsi(prices: list, period: int = 14) -> Optional[float]:
    """
    Calculeaza RSI pe ultimele N preturi.
    Returneaza valoarea RSI curenta (0-100) sau None daca date insuficiente.
    """
    if len(prices) < period + 1:
        return None

    deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    # Media initiala (SMA)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Smoothed moving average (metoda Wilder)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


# ============================================================
# MACD — Moving Average Convergence/Divergence
# ============================================================

def macd(prices: list, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """
    Calculeaza MACD, Signal Line si Histogram.
    Returneaza: {macd, signal, histogram, crossover}
    crossover: 'bullish' (MACD a trecut deasupra Signal), 'bearish', sau 'none'
    """
    result = {
        "macd": None,
        "signal": None,
        "histogram": None,
        "crossover": "none"
    }

    if len(prices) < slow + signal:
        return result

    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)

    # Aliniaza lungimile
    diff = len(ema_fast) - len(ema_slow)
    ema_fast_aligned = ema_fast[diff:] if diff > 0 else ema_fast
    ema_slow_aligned = ema_slow[-diff:] if diff < 0 else ema_slow

    if len(ema_fast_aligned) != len(ema_slow_aligned):
        return result

    macd_line = [f - s for f, s in zip(ema_fast_aligned, ema_slow_aligned)]

    if len(macd_line) < signal:
        return result

    signal_line = ema(macd_line, signal)
    if not signal_line:
        return result

    # Aliniaza pentru histogram
    offset = len(macd_line) - len(signal_line)
    macd_aligned = macd_line[offset:]

    histogram = [m - s for m, s in zip(macd_aligned, signal_line)]

    result["macd"] = round(macd_aligned[-1], 6)
    result["signal"] = round(signal_line[-1], 6)
    result["histogram"] = round(histogram[-1], 6)

    # Detectare crossover (ultimele 2 bare)
    if len(histogram) >= 2:
        if histogram[-2] < 0 and histogram[-1] >= 0:
            result["crossover"] = "bullish"   # Golden cross
        elif histogram[-2] > 0 and histogram[-1] <= 0:
            result["crossover"] = "bearish"   # Death cross

    return result


# ============================================================
# ANALIZA COMPLETA
# ============================================================

def analyze_all(prices: list, rsi_period: int = 14,
                macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                ema_fast: int = 20, ema_slow: int = 50) -> dict:
    """
    Ruleaza toti indicatorii si returneaza un dict complet.
    Include si recomandarea tehnica agregata.
    """
    rsi_val = rsi(prices, rsi_period)
    macd_val = macd(prices, macd_fast, macd_slow, macd_signal)
    ema_fast_val = ema_last(prices, ema_fast)
    ema_slow_val = ema_last(prices, ema_slow)
    current_price = prices[-1] if prices else None

    # Trend EMA
    ema_trend = "neutral"
    if ema_fast_val and ema_slow_val:
        if ema_fast_val > ema_slow_val:
            ema_trend = "bullish"   # EMA20 deasupra EMA50 = trend up
        else:
            ema_trend = "bearish"

    # Scor tehnic agregat (-3 la +3)
    tech_score = 0

    if rsi_val is not None:
        if rsi_val < 30:
            tech_score += 2    # puternic supravandut = semnal BUY puternic
        elif rsi_val < 45:
            tech_score += 1    # RSI favorabil BUY
        elif rsi_val > 70:
            tech_score -= 2    # puternic supracumparat = semnal SELL puternic
        elif rsi_val > 55:
            tech_score -= 1    # RSI favorabil SELL

    if macd_val["crossover"] == "bullish":
        tech_score += 1
    elif macd_val["crossover"] == "bearish":
        tech_score -= 1

    if ema_trend == "bullish":
        tech_score += 1
    elif ema_trend == "bearish":
        tech_score -= 1

    # Recomandare tehnica
    if tech_score >= 2:
        tech_recommendation = "STRONG_BUY"
    elif tech_score == 1:
        tech_recommendation = "BUY"
    elif tech_score == -1:
        tech_recommendation = "SELL"
    elif tech_score <= -2:
        tech_recommendation = "STRONG_SELL"
    else:
        tech_recommendation = "NEUTRAL"

    return {
        "rsi": rsi_val,
        "macd": macd_val["macd"],
        "macd_signal": macd_val["signal"],
        "macd_histogram": macd_val["histogram"],
        "macd_crossover": macd_val["crossover"],
        "ema_fast": round(ema_fast_val, 4) if ema_fast_val else None,
        "ema_slow": round(ema_slow_val, 4) if ema_slow_val else None,
        "ema_trend": ema_trend,
        "tech_score": tech_score,
        "tech_recommendation": tech_recommendation,
        "current_price": current_price
    }
