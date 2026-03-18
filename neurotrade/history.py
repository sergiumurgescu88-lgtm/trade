"""
history.py — Istoricul tranzactiilor
"""
import json
import logging
import os
from datetime import datetime

log = logging.getLogger("History")
HISTORY_FILE = "logs/trade_history.json"


def _load() -> list:
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Load history: {e}")
    return []


def _save(data: list):
    try:
        os.makedirs("logs", exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save history: {e}")


def add_trade(symbol: str, action: str, qty: int, price: float,
              confidence: int, close_type: str = "SIGNAL",
              order_id: str = "", pl: float = 0.0):
    """Adauga o tranzactie."""
    h = _load()
    h.append({
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "action": action,
        "qty": qty,
        "price": round(price, 4),
        "value": round(qty * price, 2),
        "confidence": confidence,
        "close_type": close_type,   # SIGNAL / STOP_LOSS / TAKE_PROFIT / TRAILING_STOP
        "pl": round(pl, 2),
        "order_id": order_id
    })
    _save(h)
    return len(h)


def get_summary() -> dict:
    h = _load()
    if not h:
        return {"total": 0, "buys": 0, "sells": 0, "wins": 0,
                "stop_losses": 0, "take_profits": 0, "total_pl": 0.0,
                "best_trade": 0.0, "worst_trade": 0.0}
    buys        = sum(1 for t in h if t.get("action") == "BUY")
    sells       = sum(1 for t in h if t.get("action") == "SELL")
    stop_losses = sum(1 for t in h if t.get("close_type") == "STOP_LOSS")
    take_profits= sum(1 for t in h if t.get("close_type") == "TAKE_PROFIT")
    trailing    = sum(1 for t in h if t.get("close_type") == "TRAILING_STOP")
    sell_trades = [t.get("pl", 0) for t in h if t.get("action") == "SELL"]
    total_pl    = sum(sell_trades)
    wins        = sum(1 for p in sell_trades if p > 0)
    best_trade  = max(sell_trades) if sell_trades else 0.0
    worst_trade = min(sell_trades) if sell_trades else 0.0
    return {
        "total": len(h),
        "buys": buys,
        "sells": sells,
        "wins": wins,
        "stop_losses": stop_losses,
        "take_profits": take_profits,
        "trailing_stops": trailing,
        "total_pl": round(total_pl, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2)
    }


def get_total_trades() -> int:
    return len(_load())

def get_all_trades() -> list:
    """Returneaza toate tranzactiile inregistrate."""
    try:
        import json, os
        log_file = "logs/trade_history.json"
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []
