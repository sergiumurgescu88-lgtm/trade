import logging, requests
from datetime import datetime
from config import SUPABASE_URL, SUPABASE_KEY, STARTING_CAPITAL, STOP_LOSS_PCT, TAKE_PROFIT_PCT

log = logging.getLogger("Supabase")
HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

def _post(table, data, upsert=False):
    try:
        h = dict(HEADERS)
        if upsert:
            h["Prefer"] = "resolution=merge-duplicates,return=minimal"
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=h, json=data, timeout=10)
        if r.status_code in [200,201]: return True
        log.warning(f"POST {table}: {r.status_code} {r.text[:100]}")
        return False
    except Exception as e:
        log.error(f"POST {table}: {e}")
        return False

def _patch(table, data, filter_str):
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?{filter_str}", headers=HEADERS, json=data, timeout=10)
        return r.status_code in [200,204]
    except Exception as e:
        log.error(f"PATCH {table}: {e}")
        return False

def _delete(table, filter_str):
    try:
        r = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}?{filter_str}", headers=HEADERS, timeout=10)
        return r.status_code in [200,204]
    except Exception as e:
        log.error(f"DELETE {table}: {e}")
        return False

def push_portfolio(account, positions, regime, cycle, stats):
    eq = float(account.get("equity",0) or 0)
    cash = float(account.get("cash",0) or 0)
    pnl = eq - STARTING_CAPITAL
    pnl_pct = (pnl / STARTING_CAPITAL * 100) if STARTING_CAPITAL > 0 else 0
    data = {
        "id": 1, "cycle": cycle,
        "equity": round(eq,2), "cash": round(cash,2),
        "buying_power": round(float(account.get("buying_power",0) or 0),2),
        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,4),
        "market_trend": regime.get("trend","NEUTRAL"),
        "open_positions": len(positions),
        "total_trades": stats.get("total",0),
        "total_pl": round(stats.get("total_pl",0),2),
        "updated_at": datetime.utcnow().isoformat(),
    }
    ok = _patch("portfolio_snapshot", data, "id=eq.1")
    if not ok:
        ok = _post("portfolio_snapshot", data, upsert=True)
    return ok

def push_positions(positions, prices):
    _delete("open_positions", "id=gte.0")
    if not positions: return True
    from config import CRYPTO_SYMBOLS
    rows = []
    for p in positions:
        sym = p.get("symbol","")
        entry = float(p.get("avg_entry_price",0) or 0)
        display_sym = sym
        for cs in CRYPTO_SYMBOLS:
            if sym == cs.replace("/",""):
                display_sym = cs
                break
        price = prices.get(display_sym) or prices.get(sym) or float(p.get("current_price", entry) or entry)
        rows.append({
            "symbol": display_sym,
            "qty": float(p.get("qty",0) or 0),
            "avg_entry": round(entry,4),
            "current_price": round(price,4),
            "market_value": round(float(p.get("market_value",0) or 0),2),
            "unrealized_pl": round(float(p.get("unrealized_pl",0) or 0),2),
            "unrealized_pct": round(float(p.get("unrealized_plpc",0) or 0)*100,4),
            "stop_loss": round(entry*(1-STOP_LOSS_PCT),4),
            "take_profit": round(entry*(1+TAKE_PROFIT_PCT),4),
            "asset_type": "crypto" if "/" in display_sym else "stock",
            "updated_at": datetime.utcnow().isoformat(),
        })
    return _post("open_positions", rows)

def push_signal(symbol, action, confidence, price, tech, reasoning, risk, executed, block_reason):
    return _post("signals", {
        "symbol": symbol, "action": action, "confidence": confidence,
        "price": round(price,4), "rsi": tech.get("rsi"),
        "macd": tech.get("macd_crossover","none"),
        "ema_trend": tech.get("ema_trend","neutral"),
        "tech_score": tech.get("tech_score",0),
        "reasoning": (reasoning or "")[:400],
        "risk_level": risk, "executed": executed,
        "block_reason": block_reason or None,
        "asset_type": "crypto" if "/" in symbol else "stock",
        "updated_at": datetime.utcnow().isoformat(),
    })

def push_trade(symbol, action, qty, price, confidence, close_type, pl, order_id):
    return _post("trades", {
        "symbol": symbol, "action": action, "qty": qty,
        "price": round(price,4), "value": round(qty*price,2),
        "confidence": confidence, "close_type": close_type,
        "pl": round(pl,2), "order_id": order_id or "",
        "asset_type": "crypto" if "/" in symbol else "stock",
        "timestamp": datetime.utcnow().isoformat(),
    })

def push_cycle_log(cycle, message, level="INFO"):
    return _post("cycle_logs", {
        "cycle": cycle, "level": level,
        "message": message[:500],
        "timestamp": datetime.utcnow().isoformat(),
    })

def test_connection():
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/portfolio_snapshot?select=id&limit=1", headers=HEADERS, timeout=8)
        if r.status_code == 200:
            log.info("Supabase OK")
            return True
        return False
    except Exception as e:
        log.error(f"Supabase test: {e}")
        return False
