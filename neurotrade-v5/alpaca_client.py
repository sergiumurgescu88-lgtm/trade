"""
alpaca_client.py — Alpaca Paper Trading + Market Data
FIX: get_bars cu fallback Yahoo Finance pentru date istorice gratuite
"""
import requests
import logging
from typing import Optional
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, ALPACA_DATA_URL

log = logging.getLogger("Alpaca")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "Content-Type": "application/json"
}


def _get(endpoint: str, base: str = ALPACA_BASE_URL) -> Optional[dict]:
    try:
        r = requests.get(f"{base}{endpoint}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        log.warning(f"GET {endpoint} -> {r.status_code}: {r.text[:150]}")
        return None
    except Exception as e:
        log.error(f"GET exception: {e}")
        return None


def _post(endpoint: str, data: dict) -> Optional[dict]:
    try:
        r = requests.post(f"{ALPACA_BASE_URL}{endpoint}", headers=HEADERS, json=data, timeout=10)
        if r.status_code in [200, 201]:
            return r.json()
        log.error(f"POST {endpoint} -> {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        log.error(f"POST exception: {e}")
        return None


def _delete(endpoint: str) -> bool:
    try:
        r = requests.delete(f"{ALPACA_BASE_URL}{endpoint}", headers=HEADERS, timeout=10)
        return r.status_code in [200, 204]
    except Exception as e:
        log.error(f"DELETE exception: {e}")
        return False


# ---- Account ----

def get_account() -> Optional[dict]:
    return _get("/account")


def test_connection() -> bool:
    return get_account() is not None


# ---- Positions ----

def get_positions() -> list:
    r = _get("/positions")
    return r if isinstance(r, list) else []


def get_position(symbol: str) -> Optional[dict]:
    return _get(f"/positions/{symbol}")


def close_position(symbol: str) -> bool:
    return _delete(f"/positions/{symbol}")


# ---- Orders ----

def get_orders(status: str = "open") -> list:
    r = _get(f"/orders?status={status}&limit=50")
    return r if isinstance(r, list) else []


def place_order(symbol: str, side: str, qty: int,
                order_type: str = "market") -> Optional[dict]:
    return _post("/orders", {
        "symbol": symbol,
        "qty": str(qty),
        "side": side,
        "type": order_type,
        "time_in_force": "day"
    })


# ---- Prices ----

def get_price(symbol: str) -> Optional[float]:
    """Pret curent: SIP quote → IEX trade → Yahoo fallback."""
    # Incearca SIP quote
    try:
        d = _get(f"/stocks/{symbol}/quotes/latest", base=ALPACA_DATA_URL)
        if d:
            q = d.get("quote", {})
            ask = float(q.get("ap", 0) or 0)
            bid = float(q.get("bp", 0) or 0)
            if ask > 0 and bid > 0:
                return round((ask + bid) / 2, 4)
    except Exception:
        pass

    # Incearca IEX trade
    try:
        d = _get(f"/stocks/{symbol}/trades/latest?feed=iex", base=ALPACA_DATA_URL)
        if d:
            p = d.get("trade", {}).get("p")
            if p:
                return float(p)
    except Exception:
        pass

    # Fallback Yahoo Finance
    try:
        price = _get_yahoo_price(symbol)
        if price:
            return price
    except Exception:
        pass

    log.warning(f"Pret indisponibil: {symbol}")
    return None


def _get_yahoo_price(symbol: str) -> Optional[float]:
    """Obtine pretul curent de la Yahoo Finance (fallback gratuit)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=8,
                         params={"interval": "1m", "range": "1d"})
        if r.status_code == 200:
            data = r.json()
            result = data.get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice") or meta.get("previousClose")
                if price:
                    return float(price)
    except Exception as e:
        log.debug(f"Yahoo price {symbol}: {e}")
    return None


def get_prices_batch(symbols: list) -> dict:
    """Preturi batch pentru mai multe simboluri."""
    prices = {}

    # Incearca batch Alpaca
    syms = ",".join(symbols)
    try:
        d = _get(f"/stocks/quotes/latest?symbols={syms}", base=ALPACA_DATA_URL)
        if d and "quotes" in d:
            for sym, q in d["quotes"].items():
                ask = float(q.get("ap", 0) or 0)
                bid = float(q.get("bp", 0) or 0)
                if ask > 0 and bid > 0:
                    prices[sym] = round((ask + bid) / 2, 4)
    except Exception as e:
        log.warning(f"Batch prices error: {e}")

    # Fallback individual pentru simbolurile lipsa
    for sym in symbols:
        if sym not in prices:
            p = get_price(sym)
            if p:
                prices[sym] = p

    return prices


# ---- Historical Bars ----

def get_bars(symbol: str, limit: int = 60, timeframe: str = "1Day") -> list:
    """
    Returneaza bare OHLCV istorice.
    Incearca Alpaca → fallback Yahoo Finance.
    Garantat returneaza lista (goala sau cu date).
    """
    # Incearca Alpaca (SIP feed - necesita subscriptie pentru unele feed-uri)
    bars = _get_bars_alpaca(symbol, limit, timeframe)
    if bars and len(bars) >= 10:
        log.debug(f"{symbol}: {len(bars)} bare de la Alpaca")
        return bars

    # Fallback Yahoo Finance (100% gratuit)
    bars = _get_bars_yahoo(symbol, limit)
    if bars and len(bars) >= 10:
        log.debug(f"{symbol}: {len(bars)} bare de la Yahoo Finance")
        return bars

    log.warning(f"{symbol}: nu am putut obtine date istorice (returnam [])")
    return []


def _get_bars_alpaca(symbol: str, limit: int, timeframe: str) -> list:
    """Bare istorice de la Alpaca (SIP sau IEX feed)."""
    # Incearca SIP (poate necesita abonament)
    for feed in ["sip", "iex"]:
        try:
            endpoint = (
                f"/stocks/{symbol}/bars"
                f"?timeframe={timeframe}&limit={limit}"
                f"&feed={feed}&adjustment=raw"
            )
            d = _get(endpoint, base=ALPACA_DATA_URL)
            if d and isinstance(d, dict):
                bars = d.get("bars", [])
                if bars and isinstance(bars, list) and len(bars) > 0:
                    # Normalizeaza formatul
                    normalized = []
                    for b in bars:
                        if isinstance(b, dict) and "c" in b:
                            normalized.append(b)
                    if len(normalized) >= 10:
                        return normalized
        except Exception as e:
            log.debug(f"Alpaca bars {feed} {symbol}: {e}")
    return []


def _get_bars_yahoo(symbol: str, limit: int) -> list:
    """
    Bare istorice de la Yahoo Finance — complet gratuit, fara API key.
    Returneaza format compatibil cu cel Alpaca: [{c, o, h, l, v, t}, ...]
    """
    try:
        # Calculeaza perioada necesara
        days_needed = max(limit + 10, 90)  # extra buffer
        if days_needed <= 90:
            period = "3mo"
        elif days_needed <= 180:
            period = "6mo"
        else:
            period = "1y"

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        params = {
            "interval": "1d",
            "range": period,
            "includeAdjustedClose": "true"
        }
        r = requests.get(url, headers=headers, params=params, timeout=10)

        if r.status_code != 200:
            log.warning(f"Yahoo bars {symbol}: HTTP {r.status_code}")
            return []

        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return []

        chart = result[0]
        timestamps = chart.get("timestamp", [])
        quotes = chart.get("indicators", {}).get("quote", [{}])[0]

        closes  = quotes.get("close", [])
        opens   = quotes.get("open", [])
        highs   = quotes.get("high", [])
        lows    = quotes.get("low", [])
        volumes = quotes.get("volume", [])

        bars = []
        for i in range(len(timestamps)):
            c = closes[i] if i < len(closes) else None
            if c is None:
                continue
            bars.append({
                "t": timestamps[i],
                "o": opens[i]   if i < len(opens)   else c,
                "h": highs[i]   if i < len(highs)   else c,
                "l": lows[i]    if i < len(lows)    else c,
                "c": float(c),
                "v": volumes[i] if i < len(volumes) else 0,
            })

        # Returneaza ultimele `limit` bare
        return bars[-limit:] if len(bars) > limit else bars

    except Exception as e:
        log.error(f"Yahoo bars {symbol}: {e}")
        return []


def get_closes(symbol: str, limit: int = 60) -> list:
    """Returneaza doar preturile de inchidere. Garantat lista (goala sau cu valori)."""
    bars = get_bars(symbol, limit=limit)
    if not bars:
        return []
    return [float(b["c"]) for b in bars if isinstance(b, dict) and "c" in b and b["c"]]

def is_market_open() -> bool:
    try:
        from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
        import requests as _r
        r = _r.get("https://paper-api.alpaca.markets/v2/clock",
            headers={"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY},
            timeout=5)
        return r.json().get("is_open", False)
    except:
        return False
