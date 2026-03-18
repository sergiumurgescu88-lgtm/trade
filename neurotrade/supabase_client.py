"""
supabase_client.py — NeuroTrade Bot v3.0
Proiect: lgrllhsfgvnngtmlwwug (productie)
"""
import logging
import requests
from datetime import datetime

log = logging.getLogger("Supabase")

SUPABASE_URL = "https://lgrllhsfgvnngtmlwwug.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxncmxsaHNmZ3Zubmd0bWx3d3VnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU5NTM4NiwiZXhwIjoyMDg3MTcxMzg2fQ.zXnxQ9C6xuOWibkmXRcVelUKmuQNqNxFvv4d7bp2ZHw"

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}


def _post(table: str, data, upsert: bool = False) -> bool:
    try:
        headers = dict(HEADERS)
        if upsert:
            headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                          headers=headers, json=data, timeout=10)
        if r.status_code in [200, 201]:
            return True
        log.warning(f"Supabase POST {table}: {r.status_code} — {r.text[:150]}")
        return False
    except Exception as e:
        log.error(f"Supabase POST {table}: {e}")
        return False


def _patch(table: str, data: dict, filter_str: str) -> bool:
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?{filter_str}",
                           headers=HEADERS, json=data, timeout=10)
        return r.status_code in [200, 204]
    except Exception as e:
        log.error(f"Supabase PATCH {table}: {e}")
        return False


def _delete(table: str, filter_str: str) -> bool:
    try:
        r = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}?{filter_str}",
                            headers=HEADERS, timeout=10)
        return r.status_code in [200, 204]
    except Exception as e:
        log.error(f"Supabase DELETE {table}: {e}")
        return False


def push_portfolio(account: dict, positions: list,
                   regime: dict, cycle: int, stats: dict) -> bool:
    from config import STARTING_CAPITAL
    eq   = float(account.get("equity", 0) or 0)
    cash = float(account.get("cash", 0) or 0)
    bp   = float(account.get("cash", 0) or 0)
    pnl  = eq - STARTING_CAPITAL
    pnl_pct = (pnl / STARTING_CAPITAL * 100) if STARTING_CAPITAL > 0 else 0
    data = {
        "id":             1,
        "cycle":          cycle,
        "equity":         round(eq, 2),
        "cash":           round(cash, 2),
        "buying_power":   round(bp, 2),
        "pnl":            round(pnl, 2),
        "pnl_pct":        round(pnl_pct, 4),
        "safe_mode":      regime.get("safe_mode", False),
        "spy_change_pct": round(max(min(float(regime.get("spy_change_pct", 0) or 0), 99.9999), -99.9999), 4),
        "market_trend":   regime.get("trend", "NEUTRAL"),
        "v1_open_positions": len(positions),
        "total_trades":   stats.get("total", 0),
        "total_pl":       round(stats.get("total_pl", 0), 2),
        "updated_at":     datetime.utcnow().isoformat(),
    }
    ok = _patch("v1_portfolio_snapshot", data, "id=eq.1")
    if not ok:
        ok = _post("v1_portfolio_snapshot", data, upsert=True)
    return ok


def push_positions(positions: list, prices: dict) -> bool:
    _delete("v1_open_positions", "id=gte.0")
    if not positions:
        return True
    from config import STOP_LOSS_PCT, TAKE_PROFIT_PCT
    rows = []
    for p in positions:
        sym   = p.get("symbol", "")
        entry = float(p.get("avg_entry_price", 0) or 0)
        price = prices.get(sym) or float(p.get("current_price", entry) or entry)
        rows.append({
            "symbol":        sym,
            "qty":           float(p.get("qty", 0) or 0),
            "avg_entry":     round(entry, 4),
            "current_price": round(price, 4),
            "market_value":  round(float(p.get("market_value", 0) or 0), 2),
            "unrealized_pl": round(float(p.get("unrealized_pl", 0) or 0), 2),
            "unrealized_pct": round(float(p.get("unrealized_plpc", 0) or 0) * 100, 4),
            "stop_loss":     round(entry * (1 - STOP_LOSS_PCT), 4),
            "take_profit":   round(entry * (1 + TAKE_PROFIT_PCT), 4),
            "updated_at":    datetime.utcnow().isoformat(),
        })
    return _post("v1_open_positions", rows)


def push_signal(symbol: str, action: str, confidence: int,
                price: float, tech: dict, reasoning: str,
                risk: str, executed: bool, block_reason: str) -> bool:
    return _post("v1_signals", {
        "symbol":       symbol,
        "action":       action,
        "confidence":   confidence,
        "price":        round(price, 4),
        "rsi":          tech.get("rsi"),
        "macd":         tech.get("macd_crossover", "none"),
        "ema_trend":    tech.get("ema_trend", "neutral"),
        "tech_score":   tech.get("tech_score", 0),
        "reasoning":    (reasoning or "")[:400],
        "risk_level":   risk,
        "executed":     executed,
        "block_reason": (block_reason or None),
        "updated_at":   datetime.utcnow().isoformat(),
    })


def push_trade(symbol: str, action: str, qty: float, price: float,
               confidence: int, close_type: str, pl: float, order_id: str) -> bool:
    return _post("v1_trades", {
        "symbol":     symbol,
        "action":     action,
        "qty":        qty,
        "price":      round(price, 4),
        "value":      round(qty * price, 2),
        "confidence": confidence,
        "close_type": close_type,
        "pl":         round(pl, 2),
        "order_id":   order_id or "",
        "timestamp":  datetime.utcnow().isoformat(),
    })


def push_cycle_log(cycle: int, message: str, level: str = "INFO") -> bool:
    return _post("cycle_logs", {
        "cycle":     cycle,
        "level":     level,
        "message":   message[:500],
        "timestamp": datetime.utcnow().isoformat(),
    })


def test_connection() -> bool:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/portfolio_snapshot?select=id&limit=1",
            headers=HEADERS, timeout=8
        )
        if r.status_code == 200:
            log.info("Supabase OK")
            return True
        log.warning(f"Supabase test: {r.status_code}")
        return False
    except Exception as e:
        log.error(f"Supabase test: {e}")
        return False
