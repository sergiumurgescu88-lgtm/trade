"""
forex_client.py — NeuroTrade V5 — Forex paper trading via Yahoo Finance
"""
import requests, logging, json, os
from datetime import datetime
from typing import Optional

log = logging.getLogger("Forex")
PAPER_FILE = "logs/forex_paper.json"
YAHOO_MAP = {
    "EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X",
    "AUDUSD":"AUDUSD=X","USDCAD":"USDCAD=X","USDCHF":"USDCHF=X",
}

def _load():
    try:
        if os.path.exists(PAPER_FILE):
            with open(PAPER_FILE) as f: return json.load(f)
    except: pass
    return {"positions":{}, "cash":1000.0, "trades":[]}

def _save(d):
    os.makedirs("logs", exist_ok=True)
    with open(PAPER_FILE,"w") as f: json.dump(d,f,indent=2,default=str)

def get_price(symbol):
    ys = YAHOO_MAP.get(symbol, f"{symbol}=X")
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ys}",
            headers={"User-Agent":"Mozilla/5.0"},
            params={"interval":"1m","range":"1d"}, timeout=8)
        if r.status_code == 200:
            res = r.json().get("chart",{}).get("result",[])
            if res:
                meta = res[0].get("meta",{})
                p = meta.get("regularMarketPrice") or meta.get("previousClose")
                if p: return float(p)
    except Exception as e: log.debug(f"Forex price {symbol}: {e}")
    return None

def get_prices_batch(symbols):
    return {s: p for s in symbols if (p := get_price(s))}

def get_closes(symbol, limit=60):
    ys = YAHOO_MAP.get(symbol, f"{symbol}=X")
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ys}",
            headers={"User-Agent":"Mozilla/5.0"},
            params={"interval":"1d","range":"3mo"}, timeout=10)
        if r.status_code == 200:
            res = r.json().get("chart",{}).get("result",[])
            if res:
                closes = res[0].get("indicators",{}).get("quote",[{}])[0].get("close",[])
                closes = [c for c in closes if c is not None]
                return closes[-limit:]
    except Exception as e: log.debug(f"Forex closes {symbol}: {e}")
    return []

def get_account():
    d = _load()
    return {"equity": d.get("cash",1000.0), "cash": d.get("cash",1000.0), "buying_power": d.get("cash",1000.0)}

def get_positions():
    d = _load(); result = []
    for sym, pos in d.get("positions",{}).items():
        cp = get_price(sym) or pos.get("entry_price",0)
        entry = pos.get("entry_price",cp); qty = pos.get("qty",0)
        unr = (cp-entry)*qty*1000
        result.append({"symbol":sym,"qty":qty,"avg_entry_price":entry,
            "current_price":cp,"market_value":qty*cp*1000,
            "unrealized_pl":unr,"unrealized_plpc":(cp-entry)/entry if entry>0 else 0})
    return result

def place_order(symbol, side, qty):
    price = get_price(symbol)
    if not price: return None
    d = _load(); positions = d.get("positions",{}); cash = d.get("cash",1000.0)
    cost = qty * 100
    if side == "buy":
        if cash < cost: return None
        d["cash"] -= cost
        if symbol in positions:
            old = positions[symbol]; tq = old["qty"]+qty
            positions[symbol] = {"qty":tq,"entry_price":(old["qty"]*old["entry_price"]+qty*price)/tq}
        else:
            positions[symbol] = {"qty":qty,"entry_price":price}
    elif side == "sell":
        if symbol not in positions: return None
        pos = positions[symbol]
        pl = (price - pos.get("entry_price",price)) * pos["qty"] * 1000
        d["cash"] += cost + pl
        del positions[symbol]
    d["positions"] = positions
    oid = f"FOREX_{symbol}_{side}_{int(datetime.now().timestamp())}"
    _save(d)
    return {"id":oid,"symbol":symbol,"side":side,"qty":qty,"price":price}

def close_position(symbol):
    d = _load(); pos = d.get("positions",{}).get(symbol)
    if not pos: return False
    return place_order(symbol,"sell",pos["qty"]) is not None

def test_connection():
    return get_price("EURUSD") is not None
