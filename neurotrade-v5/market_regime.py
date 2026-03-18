"""
market_regime.py — Detectare regim de piata via SPY
FIX: Tratare robusta a datelor lipsa
"""
import logging
import alpaca_client as alpaca
from config import MARKET_INDEX, SAFE_MODE_DROP_PCT

log = logging.getLogger("MarketRegime")


def get_regime() -> dict:
    """
    Analizeaza starea generala a pietei.
    Returneaza: {safe_mode, spy_change_pct, trend, reason}
    Garantat nu arunca exceptii.
    """
    result = {
        "safe_mode": False,
        "spy_change_pct": 0.0,
        "trend": "NEUTRAL",
        "reason": "Date piata indisponibile — mod normal activ"
    }

    try:
        bars = alpaca.get_bars(MARKET_INDEX, limit=10, timeframe="1Day")

        # Verifica ca avem suficiente date
        if not bars or not isinstance(bars, list) or len(bars) < 2:
            log.warning(f"Date SPY insuficiente ({len(bars) if bars else 0} bare) — skip Safe Mode")
            return result

        # Schimbare % intre ultimele 2 zile
        prev_close = float(bars[-2].get("c", 0) or 0)
        last_close = float(bars[-1].get("c", 0) or 0)

        if prev_close == 0 or last_close == 0:
            log.warning("SPY close price este 0 — skip Safe Mode")
            return result

        change_pct = (last_close - prev_close) / prev_close
        result["spy_change_pct"] = round(change_pct * 100, 3)

        # Trend pe perioada disponibila
        first_close = float(bars[0].get("c", 0) or 0)
        if first_close > 0:
            trend_pct = (last_close - first_close) / first_close
            if trend_pct > 0.01:
                result["trend"] = "BULLISH"
            elif trend_pct < -0.01:
                result["trend"] = "BEARISH"
            else:
                result["trend"] = "LATERAL"

        # Safe Mode: drop brusc in ultima zi
        if change_pct <= -SAFE_MODE_DROP_PCT:
            result["safe_mode"] = True
            result["reason"] = (
                f"SPY a scazut {change_pct*100:.2f}% in ultima zi "
                f"(threshold: -{SAFE_MODE_DROP_PCT*100:.0f}%). "
                f"Safe Mode activ — nu cumparam!"
            )
            log.warning(f"SAFE MODE ACTIV: SPY {change_pct*100:.2f}%")
        else:
            result["reason"] = (
                f"Piata normala. SPY {change_pct*100:+.2f}% azi, "
                f"trend: {result['trend']}"
            )

    except Exception as e:
        log.error(f"Market regime error: {e}")
        # In caz de eroare, nu activam Safe Mode (nu penalizam botul)

    return result
