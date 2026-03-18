#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  NeuroTrade HERMES — Kraken Futures Crypto Bot                  ║
║  Strategy : AI Sentiment (Grok-4) + RSI + Momentum             ║
║  Exchange : Kraken Futures Demo (24/7)                          ║
║  Symbols  : BTC ETH SOL XRP ADA LINK DOT                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, time, hmac, hashlib, base64, logging, json
import requests
import numpy as np
from datetime import datetime, timezone
from urllib.parse import urlencode

import subprocess as _sp

import time as _time

def _xai_post_with_retry(url, headers, json_data, max_attempts=3, timeout=30):
    """Wrapper cu retry exponential pentru xAI API (evita 403/429)."""
    import requests as _req
    last_err = None
    for attempt in range(max_attempts):
        try:
            r = _req.post(url, headers=headers, json=json_data, timeout=timeout)
            if r.status_code not in (403, 429, 500, 502, 503):
                return r
            if r.status_code == 403:
                print(f"[xAI] 403 la attempt {attempt+1} — key invalida sau quota")
                break
            wait = 2 ** attempt
            print(f"[xAI] {r.status_code} la attempt {attempt+1}, astept {wait}s...")
            _time.sleep(wait)
            last_err = r
        except Exception as e:
            print(f"[xAI] Eroare attempt {attempt+1}: {e}")
            _time.sleep(2 ** attempt)
    return last_err



def init_db():
    """Creeaza tabelele daca nu exista via psql"""
    import requests as _req
    _url = "https://rjyyyuizsfrqpjogwfse.supabase.co"
    _key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqeXl5dWl6c2ZycXBqb2d3ZnNlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzQ5OTQ2NCwiZXhwIjoyMDg5MDc1NDY0fQ.NDyJMccbMkbfIARLxLLMZmUEIYvla8hLx69rR89X-N0"
    _h = {"apikey": _key, "Authorization": f"Bearer {_key}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    # Insereaza portfolio_snapshot initial
    try:
        _req.post(f"{_url}/rest/v1/portfolio_snapshot",
            headers=_h,
            json={"id":1,"equity":10000,"cash":10000,"pnl":0,"pnl_pct":0,"total_pl":0,"open_positions":0},
            timeout=5)
    except: pass

try:
    init_db()
except: pass



# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HERMES] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/var/log/neurotrade-hermes.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("HERMES")

# ── Config ─────────────────────────────────────────────────────────────────
KRAKEN_PUBLIC  = os.getenv("KRAKEN_PUBLIC",  "")
KRAKEN_PRIVATE = os.getenv("KRAKEN_PRIVATE", "")
KRAKEN_BASE    = "https://demo-futures.kraken.com/derivatives/api/v3"
KRAKEN_CHARTS  = "https://demo-futures.kraken.com/api/charts/v1"

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

XAI_API_KEY  = os.getenv("XAI_API_KEY",  "")
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
GEMINI_KEY    = os.getenv("GEMINI_API_KEY", "")
NVIDIA_KEY    = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE   = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL  = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

CRYPTOPANIC_KEY = os.getenv("CRYPTOPANIC_KEY", "")
NEWSAPI_KEY     = os.getenv("NEWSAPI_KEY",     "")
COINGECKO_KEY   = os.getenv("COINGECKO_API_KEY", "")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def tg(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        import requests as _r
        _r.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"⚡ HERMES | {msg}", "parse_mode": "HTML"},
            timeout=5
        )
    except Exception:
        pass


# Kraken Futures Perpetual symbols
SYMBOLS = {
    "BTC":  "PF_XBTUSD",
    "ETH":  "PF_ETHUSD",
    "SOL":  "PF_SOLUSD",
    "XRP":  "PF_XRPUSD",
    "ADA":  "PF_ADAUSD",
    "LINK": "PF_LINKUSD",
    "DOT":  "PF_DOTUSD",
}

RISK_PCT       = 0.05   # 5% margin per trade
MAX_POSITIONS  = 4      # max open at once
MIN_CONFIDENCE = 65     # Grok min confidence to act
TAKE_PROFIT    = 3.0    # % profit target
STOP_LOSS      = 2.0    # % stop loss
CYCLE_SLEEP    = 300    # seconds between cycles (5 min)

# ── Kraken Futures Auth ────────────────────────────────────────────────────
def kraken_sign(endpoint: str, post_data: str, nonce: str) -> str:
    """HMAC-SHA512 signature — signing path is /api/v3/..."""
    sign_path = "/api/v3" + endpoint   # e.g. /api/v3/sendorder
    message   = (post_data + nonce + sign_path).encode("utf-8")
    sha256    = hashlib.sha256(message).digest()
    secret    = base64.b64decode(KRAKEN_PRIVATE)
    sig       = hmac.new(secret, sha256, hashlib.sha512).digest()
    return base64.b64encode(sig).decode()

def kraken_get(endpoint: str, params: dict = None) -> dict:
    url   = f"{KRAKEN_BASE}{endpoint}"
    nonce = str(int(time.time() * 1000))
    sig   = kraken_sign(endpoint, "", nonce)
    headers = {"APIKey": KRAKEN_PUBLIC, "Nonce": nonce, "Authent": sig}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        return r.json()
    except Exception as e:
        log.error(f"Kraken GET {endpoint}: {e}")
        return {}

def kraken_post(endpoint: str, params: dict = None) -> dict:
    params    = params or {}
    nonce     = str(int(time.time() * 1000))
    post_data = urlencode(params)
    sig       = kraken_sign(endpoint, post_data, nonce)
    headers   = {
        "APIKey":       KRAKEN_PUBLIC,
        "Nonce":        nonce,
        "Authent":      sig,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    url = f"{KRAKEN_BASE}{endpoint}"
    try:
        r = requests.post(url, headers=headers, data=post_data, timeout=10)
        return r.json()
    except Exception as e:
        log.error(f"Kraken POST {endpoint}: {e}")
        return {}

# ── Market Data ────────────────────────────────────────────────────────────
def get_all_tickers() -> dict:
    """Returns dict symbol -> ticker data"""
    data = kraken_get("/tickers")
    if not data or "tickers" not in data:
        return {}
    return {t["symbol"]: t for t in data["tickers"]}

def get_ohlc(symbol: str, resolution: str = "15m") -> list:
    """Get OHLCV candles via Kraken Futures charts API"""
    try:
        r = requests.get(
            f"{KRAKEN_CHARTS}/trade/{symbol}/{resolution}",
            timeout=10
        )
        return r.json().get("candles", [])
    except Exception as e:
        log.error(f"get_ohlc {symbol}: {e}")
        return []

def calc_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_g  = np.mean(gains[-period:])
    avg_l  = np.mean(losses[-period:])
    if avg_l == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_g / avg_l)), 2)

def get_technicals(symbol: str) -> dict:
    """Returns price, rsi, momentum, volatility"""
    candles = get_ohlc(symbol)
    if not candles or len(candles) < 20:
        return {"price": 0, "rsi": 50, "momentum": 0, "volatility": 0}
    closes = [float(c["close"]) for c in candles if c.get("close")]
    if len(closes) < 15:
        return {"price": 0, "rsi": 50, "momentum": 0, "volatility": 0}
    rsi  = calc_rsi(closes)
    mom  = round((closes[-1] - closes[-5]) / closes[-5] * 100, 3) if closes[-5] else 0
    vola = round(float(np.std(np.diff(closes) / closes[:-1]) * 100), 3)
    return {
        "price":      closes[-1],
        "rsi":        rsi,
        "momentum":   mom,
        "volatility": vola,
    }

# ── News & AI Sentiment ────────────────────────────────────────────────────
# CoinGecko coin ID map
COIN_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "XRP": "ripple",  "ADA": "cardano",  "LINK": "chainlink", "DOT": "polkadot",
}

def get_news(coin: str) -> list:
    """Fetch sentiment signals from CoinGecko (trending + market data)"""
    headlines = []
    coin_id   = COIN_IDS.get(coin, coin.lower())
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}",
            params={
                "x_cg_demo_api_key":       COINGECKO_KEY,
                "localization":            "false",
                "tickers":                 "false",
                "market_data":             "true",
                "community_data":          "true",
                "developer_data":          "false",
            },
            timeout=10
        )
        data = r.json()
        md   = data.get("market_data", {})
        cd   = data.get("community_data", {})

        # Price change signals
        chg1h  = md.get("price_change_percentage_1h_in_currency",  {}).get("usd", 0) or 0
        chg24h = md.get("price_change_percentage_24h",  0) or 0
        chg7d  = md.get("price_change_percentage_7d",   0) or 0
        vol    = md.get("total_volume", {}).get("usd", 0) or 0
        mcap   = md.get("market_cap",   {}).get("usd", 1) or 1
        ath_pct = md.get("ath_change_percentage", {}).get("usd", 0) or 0

        # Sentiment votes
        up_pct  = data.get("sentiment_votes_up_percentage",   50) or 50
        dn_pct  = data.get("sentiment_votes_down_percentage", 50) or 50

        # Twitter/Reddit followers as proxy for momentum
        twitter = cd.get("twitter_followers", 0) or 0

        # Build synthetic headlines from data
        headlines.append(f"{coin} 1h change: {chg1h:+.2f}%")
        headlines.append(f"{coin} 24h change: {chg24h:+.2f}%, 7d: {chg7d:+.2f}%")
        headlines.append(f"{coin} community sentiment: {up_pct:.0f}% bullish, {dn_pct:.0f}% bearish")
        headlines.append(f"{coin} volume/mcap ratio: {vol/mcap*100:.2f}%")
        headlines.append(f"{coin} distance from ATH: {ath_pct:.1f}%")
        if twitter > 0:
            headlines.append(f"{coin} Twitter followers: {twitter:,}")

        log.info(f"    CoinGecko {coin}: 1h={chg1h:+.2f}% 24h={chg24h:+.2f}% sentiment={up_pct:.0f}%bull")

    except Exception as e:
        log.warning(f"CoinGecko [{coin}]: {e}")

    return headlines

def grok_sentiment(coin: str, headlines: list, tech: dict) -> dict:
    """Ask Gemini for a trading signal"""
    if not headlines:
        return {"action": "HOLD", "confidence": 0, "reasoning": "no news available"}

    news_block = "\n".join(f"- {h}" for h in headlines)
    prompt = f"""You are a professional crypto trading AI. Analyze {coin}/USD and produce a trading signal.

MARKET DATA:
{news_block}

TECHNICAL INDICATORS:
- Current price : ${tech['price']:.4f}
- RSI(14)       : {tech['rsi']} (oversold <30, overbought >70)
- 5-bar momentum: {tech['momentum']}%
- Volatility    : {tech['volatility']}%

RESPOND WITH VALID JSON ONLY — no markdown, no extra text:
{{"action": "BUY" or "SELL" or "HOLD", "confidence": 0-100, "reasoning": "max 15 words"}}

Rules:
- BUY  → sentiment bullish AND RSI < 68 AND momentum > -3%
- SELL → sentiment bearish AND RSI > 52
- HOLD → mixed signals
- confidence > 65 to act"""

    try:
        r = requests.post(
            f"{NVIDIA_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"},
            json={
                "model":      NVIDIA_MODEL,
                "messages":   [{"role": "user", "content": prompt}],
                "max_tokens": 150,
            },
            timeout=25
        )
        raw = r.json()["choices"][0]["message"]["content"].strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        # Extract JSON from response
        import re
        match = re.search(r'\{[^}]+\}', raw, re.DOTALL)
        if match:
            raw = match.group(0)
        result = json.loads(raw)
        if result.get("action") not in ("BUY", "SELL", "HOLD"):
            result["action"] = "HOLD"
        result["confidence"] = max(0, min(100, int(result.get("confidence", 0))))
        return result
    except Exception as e:
        log.error(f"NVIDIA error [{coin}]: {e}")
        return {"action": "HOLD", "confidence": 0, "reasoning": "ai_error"}

# ── Kraken Account & Orders ────────────────────────────────────────────────
def get_account_summary() -> dict:
    return kraken_get("/accounts")

def get_open_positions() -> list:
    data = kraken_post("/openpositions")
    return data.get("openPositions", [])

def place_order(symbol: str, side: str, size: float) -> dict:
    """Market order — side: 'buy' or 'sell'"""
    params = {
        "orderType": "mkt",
        "symbol":    symbol,
        "side":      side,
        "size":      str(size),
    }
    result = kraken_post("/sendorder", params)
    log.info(f"  → sendorder {side} {size} {symbol}: {result.get('result','?')}")
    return result

def close_position(symbol: str, side: str, size: float) -> dict:
    close_side = "sell" if side == "buy" else "buy"
    return place_order(symbol, close_side, abs(size))

# ── Supabase Logging ───────────────────────────────────────────────────────
def sb_upsert(table: str, data: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                "apikey":        SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type":  "application/json",
                "Prefer":        "resolution=merge-duplicates",
            },
            json=data,
            timeout=5
        )
    except Exception as e:
        log.warning(f"Supabase [{table}]: {e}")

def log_trade(coin, action, price, size, conf, reasoning, rsi, pl=0.0):
    import requests as _req
    _url = "https://rjyyyuizsfrqpjogwfse.supabase.co"
    _key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqeXl5dWl6c2ZycXBqb2d3ZnNlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzQ5OTQ2NCwiZXhwIjoyMDg5MDc1NDY0fQ.NDyJMccbMkbfIARLxLLMZmUEIYvla8hLx69rR89X-N0"
    _h = {"apikey": _key, "Authorization": f"Bearer {_key}", "Content-Type": "application/json", "Prefer": "return=minimal"}
    try:
        _req.post(f"{_url}/rest/v1/trades", headers=_h, json={
            "symbol": coin, "action": action, "price": price,
            "qty": size, "confidence": conf, "pl": pl,
            "close_type": "SIGNAL", "timestamp": datetime.now(timezone.utc).isoformat(),
        }, timeout=5)
    except Exception as e:
        log.warning(f"log_trade error: {e}")

def update_portfolio(equity, cash, n_pos):
    sb_upsert("portfolio_snapshot", {
        "id":            1,
        "equity":        equity,
        "cash":          cash,
        "open_positions": n_pos,
        "strategy":      "HERMES_GROK4",
        "bot_version":   "1.0",
        "updated_at":    datetime.now(timezone.utc).isoformat(),
    })

# ── Main Loop ──────────────────────────────────────────────────────────────
def run():
    log.info("╔══════════════════════════════════════════════╗")
    log.info("║  HERMES CRYPTO BOT STARTING — Kraken Demo   ║")
    log.info("╚══════════════════════════════════════════════╝")
    log.info(f"Symbols: {list(SYMBOLS.keys())}")
    tg("🚀 HERMES pornit — Kraken Demo Futures 24/7")
    log.info(f"Risk: {RISK_PCT*100}% per trade | Max pos: {MAX_POSITIONS} | MinConf: {MIN_CONFIDENCE}")

    cycle = 0
    while True:
        cycle += 1
        log.info(f"═══ HERMES CYCLE {cycle} ═══════════════════════════════")

        try:
            # ── Account info ──────────────────────────────────────────────
            acc     = get_account_summary()
            flex    = acc.get("accounts", {}).get("flex", {})
            equity  = float(flex.get("portfolioValue",  10000))
            margin  = float(flex.get("availableMargin", 10000))
            positions = get_open_positions()
            n_pos   = len(positions)

            log.info(f"💼 equity=${equity:.2f} | avail_margin=${margin:.2f} | {n_pos} open positions")
            update_portfolio(equity, margin, n_pos)

            # ── Manage existing positions ─────────────────────────────────
            tickers = get_all_tickers()
            for pos in positions:
                sym   = pos.get("symbol", "")
                side  = pos.get("side", "long")  # "long" or "short"
                size  = abs(float(pos.get("size", 0)))
                entry = float(pos.get("price", 0))

                ticker  = tickers.get(sym, {})
                current = float(ticker.get("last", entry))
                if entry <= 0 or current <= 0:
                    continue

                pnl_pct = (current - entry) / entry * 100
                if side == "short":
                    pnl_pct = -pnl_pct

                coin = next((k for k, v in SYMBOLS.items() if v == sym), sym)
                log.info(f"  📊 {coin} {side} | entry=${entry:.4f} now=${current:.4f} | P&L={pnl_pct:+.2f}%")

                order_side = "long"  # track for close
                if pnl_pct >= TAKE_PROFIT:
                    log.info(f"  ✅ TAKE PROFIT {coin}: +{pnl_pct:.2f}%")
                    close_position(sym, order_side, size)
                    log_trade(coin, "CLOSE_TP", current, size, 95,
                              f"TP +{pnl_pct:.2f}%", 50)
                elif pnl_pct <= -STOP_LOSS:
                    log.info(f"  🛑 STOP LOSS  {coin}: {pnl_pct:.2f}%")
                    close_position(sym, order_side, size)
                    log_trade(coin, "CLOSE_SL", current, size, 95,
                              f"SL {pnl_pct:.2f}%", 50)

            # ── Scan for new signals ──────────────────────────────────────
            positions_now = get_open_positions()
            open_syms     = {p.get("symbol") for p in positions_now}
            n_pos_now     = len(positions_now)

            signals = []
            for coin, sym in SYMBOLS.items():
                if sym in open_syms:
                    log.info(f"  ⏭  {coin}: already in position, skip")
                    continue

                # Get technicals
                tech = get_technicals(sym)
                if tech["price"] <= 0:
                    log.warning(f"  ⚠️  {coin}: no price data")
                    continue

                # Get news
                headlines = get_news(coin)
                log.info(f"  📰 {coin}: {len(headlines)} headlines fetched")

                # Ask Grok-4
                signal = grok_sentiment(coin, headlines, tech)
                signal.update({"symbol": sym, "coin": coin, **tech})

                emoji = "🟢" if signal["action"] == "BUY" else "🔴" if signal["action"] == "SELL" else "⚪"
                log.info(
                    f"  {emoji} {coin}: {signal['action']} "
                    f"conf={signal['confidence']} RSI={tech['rsi']} "
                    f"mom={tech['momentum']:+.2f}% | {signal.get('reasoning','')[:60]}"
                )

                if signal["action"] in ("BUY", "SELL") and signal["confidence"] >= MIN_CONFIDENCE:
                    signals.append(signal)

            # Sort by confidence, execute top signals
            signals.sort(key=lambda x: x["confidence"], reverse=True)

            for sig in signals:
                if n_pos_now >= MAX_POSITIONS:
                    log.info(f"  🔒 Max positions ({MAX_POSITIONS}) reached, skipping remaining")
                    break

                price = sig["price"]
                if price <= 0:
                    continue

                trade_margin = margin * RISK_PCT
                size         = round(trade_margin / price, 4)
                if size <= 0:
                    log.warning(f"  ⚠️  {sig['coin']}: size=0, skip")
                    continue

                side   = "buy"  if sig["action"] == "BUY"  else "sell"
                result = place_order(sig["symbol"], side, size)

                if result.get("result") == "success" or "sendStatus" in result:
                    log.info(
                        f"  🚀 ORDER SENT: {sig['action']} {size} {sig['coin']} "
                        f"@ ${price:.4f} | conf={sig['confidence']}"
                    )
                    tg(f"🚀 {sig['action']} {size} {sig['coin']} @ ${price:.4f} | conf={sig['confidence']}%")
                    log_trade(
                        sig["coin"], sig["action"], price, size,
                        sig["confidence"], sig.get("reasoning", ""), sig["rsi"]
                    )
                    n_pos_now += 1
                    margin    -= trade_margin
                else:
                    log.error(f"  ❌ Order FAILED {sig['coin']}: {result}")

            log.info(
                f"═══ HERMES CYCLE {cycle} END | "
                f"{len(signals)} signals | {n_pos_now}/{MAX_POSITIONS} pos ═══"
            )

        except Exception as e:
            log.error(f"Cycle {cycle} error: {e}", exc_info=True)

        log.info(f"  💤 Sleeping {CYCLE_SLEEP}s until next cycle...")
        time.sleep(CYCLE_SLEEP)

if __name__ == "__main__":
    run()
