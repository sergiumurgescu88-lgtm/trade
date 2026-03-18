import logging
import requests
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, ALPACA_DATA_URL

log = logging.getLogger("Alpaca")

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "Content-Type":        "application/json",
}

# Kraken pair -> (request_pair, response_key)
KRAKEN_MAP = {
    "BTC":   ("XBTUSD",   "XXBTZUSD"),
    "ETH":   ("ETHUSD",   "XETHZUSD"),
    "XRP":   ("XRPUSD",   "XXRPZUSD"),
    "LTC":   ("LTCUSD",   "XLTCZUSD"),
    "XLM":   ("XLMUSD",   "XXLMZUSD"),
    "SOL":   ("SOLUSD",   "SOLUSD"),
    "ADA":   ("ADAUSD",   "ADAUSD"),
    "DOGE":  ("XDGUSD",   "XDGUSD"),
    "DOT":   ("DOTUSD",   "DOTUSD"),
    "MATIC": ("MATICUSD", "MATICUSD"),
    "LINK":  ("LINKUSD",  "LINKUSD"),
    "AVAX":  ("AVAXUSD",  "AVAXUSD"),
    "ATOM":  ("ATOMUSD",  "ATOMUSD"),
    "UNI":   ("UNIUSD",   "UNIUSD"),
    "ALGO":  ("ALGOUSD",  "ALGOUSD"),
}

def get_account():
    try:
        r = requests.get(f"{ALPACA_BASE_URL}/account", headers=HEADERS, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        log.error(f"get_account: {e}")
        return {}

def get_positions():
    try:
        r = requests.get(f"{ALPACA_BASE_URL}/positions", headers=HEADERS, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        log.error(f"get_positions: {e}")
        return []

def is_market_open():
    try:
        r = requests.get(f"{ALPACA_BASE_URL}/clock", headers=HEADERS, timeout=5)
        return r.json().get("is_open", False)
    except:
        return False

def get_stock_price(symbol):
    try:
        r = requests.get(f"{ALPACA_DATA_URL}/stocks/{symbol}/trades/latest", headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return float(r.json()["trade"]["p"])
    except Exception as e:
        log.warning(f"Stock price {symbol}: {e}")
    return None

def get_crypto_price(symbol):
    """Pret crypto via Kraken public API"""
    base = symbol.split("/")[0].upper()
    mapping = KRAKEN_MAP.get(base)
    if not mapping:
        log.warning(f"Kraken: pereche necunoscuta {base}")
        return 0
    req_pair, resp_key = mapping
    try:
        r = requests.get(
            "https://api.kraken.com/0/public/Ticker",
            params={"pair": req_pair},
            timeout=10
        )
        result = r.json().get("result", {})
        data = result.get(resp_key) or result.get(req_pair) or (list(result.values())[0] if result else None)
        if data:
            return float(data["c"][0])
        return 0
    except Exception as e:
        log.warning(f"Kraken price {symbol}: {e}")
        return 0

def get_crypto_prices_bulk(symbols):
    """Preia toate preturile crypto dintr-un singur request Kraken"""
    req_pairs = []
    sym_map = {}
    for s in symbols:
        if "/" not in s:
            continue
        base = s.split("/")[0].upper()
        mapping = KRAKEN_MAP.get(base)
        if mapping:
            req_pair, resp_key = mapping
            req_pairs.append(req_pair)
            sym_map[resp_key] = s
            sym_map[req_pair] = s
    if not req_pairs:
        return {}
    try:
        r = requests.get(
            "https://api.kraken.com/0/public/Ticker",
            params={"pair": ",".join(req_pairs)},
            timeout=15
        )
        result = r.json().get("result", {})
        prices = {}
        for key, data in result.items():
            sym = sym_map.get(key)
            if sym:
                prices[sym] = float(data["c"][0])
        for s in symbols:
            if "/" in s and s not in prices:
                prices[s] = 0
        return prices
    except Exception as e:
        log.warning(f"Kraken bulk: {e}")
        return {s: 0 for s in symbols}

def get_price(symbol):
    if "/" in symbol:
        return get_crypto_price(symbol)
    return get_stock_price(symbol)

def place_order(symbol, qty, side):
    is_crypto = "/" in symbol
    alpaca_sym = symbol.replace("/", "") if is_crypto else symbol
    payload = {
        "symbol":        alpaca_sym,
        "qty":           str(qty),
        "side":          side,
        "type":          "market",
        "time_in_force": "gtc" if is_crypto else "day",
    }
    try:
        r = requests.post(f"{ALPACA_BASE_URL}/orders", headers=HEADERS, json=payload, timeout=10)
        if r.status_code in [200, 201]:
            log.info(f"Order OK: {side.upper()} {qty} {symbol}")
            return r.json()
        else:
            log.error(f"POST /orders -> {r.status_code}: {r.text[:200]}")
            return {}
    except Exception as e:
        log.error(f"place_order {symbol}: {e}")
        return {}

def get_bars(symbol, timeframe="1Hour", limit=50):
    try:
        from datetime import datetime, timedelta
        start = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")
        if "/" in symbol:
            sym = symbol.replace("/", "%2F")
            url = f"https://data.alpaca.markets/v1beta3/crypto/us/bars?symbols={sym}&timeframe={timeframe}&limit={limit}&start={start}"
        else:
            url = f"{ALPACA_DATA_URL}/stocks/{symbol}/bars?timeframe={timeframe}&limit={limit}&start={start}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if "/" in symbol:
                clean = symbol.replace("/", "")
                bars = data.get("bars", {})
                return bars.get(symbol, bars.get(clean, []))
            return data.get("bars", [])
    except Exception as e:
        log.warning(f"get_bars {symbol}: {e}")
    return []
