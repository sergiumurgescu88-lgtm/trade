"""
kraken_client.py — NeuroTrade Bot v5.0
Crypto trading via Kraken Demo Futures (inlocuieste Binance)
"""
import hashlib, hmac, base64, time, urllib.parse, requests, logging
from config import KRAKEN_API_KEY, KRAKEN_SECRET_KEY, KRAKEN_BASE_URL

log = logging.getLogger("Kraken")

SYMBOL_MAP = {
    "XBT/USD":"PF_XBTUSD","ETH/USD":"PF_ETHUSD","SOL/USD":"PF_SOLUSD",
    "ADA/USD":"PF_ADAUSD","DOGE/USD":"PF_DOGEUSD","AVAX/USD":"PF_AVAXUSD","DOT/USD":"PF_DOTUSD",
    "BTC/USDT":"PF_XBTUSD","ETH/USDT":"PF_ETHUSD","SOL/USDT":"PF_SOLUSD",
    "DOGE/USDT":"PF_DOGEUSD","ADA/USDT":"PF_ADAUSD","AVAX/USDT":"PF_AVAXUSD",
}

def _sign(endpoint, nonce, post_data):
    sign_path = "/api/v3" + endpoint
    message = (post_data + nonce + sign_path).encode("utf-8")
    sha256 = hashlib.sha256(message).digest()
    secret = base64.b64decode(KRAKEN_SECRET_KEY)
    sig = hmac.new(secret, sha256, hashlib.sha512)
    return base64.b64encode(sig.digest()).decode()

def _auth_headers(endpoint, post_data=""):
    nonce = str(int(time.time() * 1000))
    return {"APIKey": KRAKEN_API_KEY, "Nonce": nonce, "Authent": _sign(endpoint, nonce, post_data)}

def get_price(symbol):
    kraken_sym = SYMBOL_MAP.get(symbol)
    if not kraken_sym: return 0.0
    try:
        r = requests.get(f"{KRAKEN_BASE_URL}/derivatives/api/v3/tickers",
            params={"symbol": kraken_sym}, timeout=10)
        if r.status_code == 200:
            for t in r.json().get("tickers", []):
                if t.get("symbol") == kraken_sym:
                    return float(t.get("last") or t.get("markPrice") or 0)
    except Exception as e: log.error(f"Kraken get_price {symbol}: {e}")
    return 0.0

def get_account():
    sign_endpoint = "/accounts"
    url_endpoint = "/derivatives/api/v3/accounts"
    try:
        r = requests.get(f"{KRAKEN_BASE_URL}{url_endpoint}",
            headers=_auth_headers(sign_endpoint), timeout=10)
        if r.status_code == 200:
            flex = r.json().get("accounts", {}).get("flex", {})
            equity  = float(flex.get("portfolioValue", flex.get("balanceValue", 0)) or 0)
            balance = float(flex.get("availableMargin", equity) or equity)
            return {"equity": equity, "cash": balance, "buying_power": balance}
    except Exception as e: log.error(f"Kraken get_account: {e}")
    return {"equity": 10000, "cash": 10000, "buying_power": 10000}

def get_positions():
    endpoint = "/derivatives/api/v3/openpositions"
    try:
        r = requests.get(f"{KRAKEN_BASE_URL}{endpoint}",
            headers=_auth_headers(endpoint), timeout=10)
        if r.status_code == 200:
            result = []
            for p in r.json().get("openPositions", []):
                sym = p.get("symbol", "")
                internal = next((k for k, v in SYMBOL_MAP.items() if v == sym), sym)
                qty = float(p.get("size", 0))
                entry = float(p.get("price", 0))
                current = get_price(internal)
                pl = (current - entry) * qty if entry > 0 else 0
                pl_pct = (pl / (entry * qty)) if entry * qty > 0 else 0
                result.append({"symbol": internal, "qty": qty,
                    "avg_entry_price": entry, "current_price": current,
                    "market_value": current * qty, "unrealized_pl": pl,
                    "unrealized_plpc": pl_pct, "side": p.get("side", "long")})
            return result
    except Exception as e: log.error(f"Kraken get_positions: {e}")
    return []

def place_order(symbol, side, qty_usd):
    kraken_sym = SYMBOL_MAP.get(symbol)
    if not kraken_sym: return {}
    price = get_price(symbol)
    if price <= 0: return {}
    size = round(qty_usd / price, 6)
    endpoint = "/derivatives/api/v3/sendorder"
    post_data = urllib.parse.urlencode({
        "orderType": "mkt", "symbol": kraken_sym,
        "side": side.lower(), "size": size
    })
    try:
        nonce = str(int(time.time() * 1000))
        headers = {"Content-Type": "application/x-www-form-urlencoded",
            "APIKey": KRAKEN_API_KEY, "Nonce": nonce,
            "Authent": _sign(endpoint, nonce, post_data)}
        r = requests.post(f"{KRAKEN_BASE_URL}{endpoint}", data=post_data,
            headers=headers, timeout=15)
        if r.status_code == 200 and r.json().get("result") == "success":
            log.info(f"✅ Kraken {side.upper()} {symbol}: {size} @ ${price:.4f}")
            return {"symbol": symbol, "side": side, "qty": size, "price": price, "status": "filled"}
    except Exception as e: log.error(f"Kraken place_order {symbol}: {e}")
    return {}

def close_position(symbol):
    for pos in get_positions():
        if pos.get("symbol") == symbol:
            qty = float(pos.get("qty", 0))
            side = "sell" if pos.get("side", "long") == "long" else "buy"
            if qty > 0:
                return place_order(symbol, side, qty * float(pos.get("current_price", 1)))
    return {}

def test_connection():
    try:
        r = requests.get(f"{KRAKEN_BASE_URL}/derivatives/api/v3/instruments", timeout=8)
        if r.status_code == 200:
            log.info("✅ Kraken Demo conectat")
            return True
    except Exception as e: log.error(f"Kraken test: {e}")
    return False
