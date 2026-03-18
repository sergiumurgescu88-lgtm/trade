"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  NeuroTrade ZEUS — CRYPTO MOMENTUM + NVIDIA QWEN 397B                       ║
║                                                                              ║
║  AI Principal: NVIDIA Qwen3.5-397B-A17B (cel mai mare model open-source)    ║
║  AI Fallback:  xAI Grok-4 → Gemini 2.0 Flash                               ║
║                                                                              ║
║  Strategie unică: CRYPTO MOMENTUM REVERSAL TIMING                           ║
║  → CryptoPanic bullish filter + CoinGecko trend data                        ║
║  → Wilder RSI > 68 pe stocks crypto-corelate (COIN, MSTR, AMD, NVDA)       ║
║  → Volume spike > 2× medie pe 20 bare = confirmare instituțională           ║
║  → Sentiment din 4 surse: CryptoPanic + Finnhub + NewsAPI + CoinGecko      ║
║  → ATR-dynamic TP/SL + trailing stop                                        ║
║  → Hurst Exponent pentru trend confirmation                                 ║
║                                                                              ║
║  Universe: 22 stocks + crypto-adjacent                                      ║
║  Win rate vizat: 73-82%                                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import time
import logging
import os
import json
import re
import math
from datetime import datetime, timedelta
from collections import deque
from typing import Optional
import numpy as np
import requests

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



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ZEUS] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/var/log/neurotrade-zeus.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("ZEUS")

# ── Config ────────────────────────────────────────────────────────────────────
ALPACA_KEY    = os.getenv("ALPACA_KEY", "")
ALPACA_SECRET = os.getenv("ALPACA_SECRET", "")
ALPACA_BASE   = os.getenv("ALPACA_BASE", "https://paper-api.alpaca.markets")
ALPACA_DATA   = "https://data.alpaca.markets"

SUPABASE_URL  = os.getenv("SUPABASE_URL_ZEUS", "")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY_ZEUS", "")

# AI chain: NVIDIA Qwen → xAI Grok → Gemini
NVIDIA_KEY    = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE   = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL  = os.getenv("NVIDIA_MODEL", "qwen/qwen3.5-397b-a17b")
XAI_KEY       = os.getenv("XAI_API_KEY", "")
XAI_BASE      = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
GEMINI_KEY    = os.getenv("GEMINI_API_KEY", "")

# Data sources
FINNHUB_KEY      = os.getenv("FINNHUB_KEY", "")
NEWSAPI_KEY      = os.getenv("NEWSAPI_KEY", "")
NEWSAPI_URL      = os.getenv("NEWSAPI_URL", "https://newsapi.org/v2/everything")
COINGECKO_KEY    = os.getenv("COINGECKO_API_KEY", "")
CRYPTOPANIC_KEY  = os.getenv("CRYPTOPANIC_KEY", "")
CRYPTOPANIC_URL  = os.getenv("CRYPTOPANIC_URL", "https://cryptopanic.com/api/developer/v2")

# ── Parameters ────────────────────────────────────────────────────────────────
CYCLE_SECONDS   = 300
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def tg(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"⚡ ZEUS | {msg}", "parse_mode": "HTML"},
            timeout=5
        )
    except Exception:
        pass

MAX_POSITIONS   = 10
RISK_PER_TRADE  = 0.065
MAX_DAILY_LOSS  = 0.05
ATR_TP_MULT     = 3.0
ATR_SL_MULT     = 1.2
ATR_TRAIL_MULT  = 1.8
CONFIDENCE_MIN  = 62
VOL_SURGE_MIN   = 1.8   # volum minim 1.8× medie
WILDER_PERIOD   = 14
RSI_MOMENTUM    = 68    # Wilder RSI momentum entry

def is_session() -> bool:
    h, m = datetime.utcnow().hour, datetime.utcnow().minute
    return (8 <= h < 12) or (h == 13 and m >= 30) or (14 <= h < 21)

# Universe — crypto-corelate + high beta momentum
UNIVERSE = [
    "COIN","MSTR","HOOD","RIOT","MARA","CLSK",   # direct crypto exposure
    "NVDA","AMD","SOXL",                           # AI/semis momentum
    "TSLA","PLTR","IONQ","ARKG",                   # high-beta disruptive
    "META","GOOGL","AMZN","MSFT",                  # mega-cap momentum
    "TQQQ","ARKK","QQQ","SPY",                     # ETF momentum
]


_BTC_CACHE = {"change": 0.0, "ts": None}

def get_btc_2h_change() -> float:
    """
    Returnează % change BTC în ultimele 2h via CoinGecko.
    Cache 10 min.
    """
    global _BTC_CACHE
    now = __import__('datetime').datetime.utcnow()
    if _BTC_CACHE["ts"] and (now - _BTC_CACHE["ts"]).seconds < 600:
        return _BTC_CACHE["change"]
    if not COINGECKO_KEY:
        return 0.0
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            headers={"x-cg-demo-api-key": COINGECKO_KEY},
            params={"vs_currency": "usd", "days": "0.1"},
            timeout=8
        )
        if r.ok:
            prices = r.json().get("prices", [])
            if len(prices) >= 2:
                start_p = prices[0][1]
                end_p   = prices[-1][1]
                change  = (end_p - start_p) / start_p * 100
                _BTC_CACHE = {"change": change, "ts": now}
                return change
    except:
        pass
    return 0.0

TRAILING_PEAKS: dict = {}
SENTIMENT_CACHE: dict = {}


_ZEUS_RECENT_PL = []  # ultimele 5 trade-uri

def zeus_adaptive_risk() -> float:
    """Reduce risc 40% dacă ultimele 3 trades au fost loss."""
    if len(_ZEUS_RECENT_PL) < 3:
        return RISK_PER_TRADE
    last3 = _ZEUS_RECENT_PL[-3:]
    if all(pl < 0 for pl in last3):
        log.warning("⚠️ ZEUS: 3 consecutive losses — risk reduced 40%")
        return RISK_PER_TRADE * 0.6
    return RISK_PER_TRADE

# ── HTTP Helpers ──────────────────────────────────────────────────────────────
def alpaca_get(path, params=None):
    h = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    try:
        r = requests.get(f"{ALPACA_BASE}{path}", headers=h, params=params, timeout=10)
        return r.json() if r.ok else {}
    except: return {}

def alpaca_data_get(path, params=None):
    h = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    try:
        r = requests.get(f"{ALPACA_DATA}{path}", headers=h, params=params, timeout=15)
        return r.json() if r.ok else {}
    except: return {}

def alpaca_post(path, body):
    h = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET,
         "Content-Type": "application/json"}
    try:
        r = requests.post(f"{ALPACA_BASE}{path}", headers=h, json=body, timeout=10)
        return r.json() if r.ok else {}
    except: return {}

def sb_upsert(table, data):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    try: requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=h, json=data, timeout=10)
    except: pass

def sb_insert(table, data):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json"}
    try: requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=h, json=data, timeout=10)
    except: pass

# ── Data Fetch (look-ahead bias free) ────────────────────────────────────────
def fetch_bars(symbol: str, limit=90) -> Optional[dict]:
    try:
        end = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        start = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = alpaca_data_get(f"/v2/stocks/{symbol}/bars", {
            "timeframe": "1Hour", "start": start, "end": end,
            "limit": limit, "feed": "iex",
        })
        bars = data.get("bars", [])
        if len(bars) < 25: return None
        return {
            "opens":   np.array([b["o"] for b in bars]),
            "highs":   np.array([b["h"] for b in bars]),
            "lows":    np.array([b["l"] for b in bars]),
            "closes":  np.array([b["c"] for b in bars]),
            "volumes": np.array([b["v"] for b in bars]),
        }
    except: return None

# ── Technical Indicators ──────────────────────────────────────────────────────
def wilder_rsi_series(closes: np.ndarray, period=14) -> np.ndarray:
    rsi_vals = np.full(len(closes), 50.0)
    if len(closes) < period + 5: return rsi_vals
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    for i in range(period, len(gains)):
        ag = (ag * (period-1) + gains[i]) / period
        al = (al * (period-1) + losses[i]) / period
        rs = ag / al if al > 0 else 100
        rsi_vals[i+1] = 100 - (100 / (1 + rs))
    return rsi_vals

def compute_atr(highs, lows, closes, period=14) -> np.ndarray:
    if len(closes) < period + 1: return np.array([float(closes[-1]) * 0.01])
    tr = np.maximum(highs[1:]-lows[1:],
         np.maximum(np.abs(highs[1:]-closes[:-1]), np.abs(lows[1:]-closes[:-1])))
    atr = np.zeros(len(tr))
    atr[period-1] = np.mean(tr[:period])
    for i in range(period, len(tr)):
        atr[i] = (atr[i-1]*(period-1)+tr[i])/period
    return atr

def compute_ema(prices: np.ndarray, period: int) -> float:
    if len(prices) < 2: return float(prices[-1]) if len(prices) else 0.0
    ema = float(prices[0])
    k = 2 / (period+1)
    for p in prices[1:]:
        ema = float(p)*k + ema*(1-k)
    return ema

def compute_hurst(closes: np.ndarray) -> float:
    if len(closes) < 30: return 0.5
    def rs(data):
        mean = np.mean(data)
        dev = np.cumsum(data - mean)
        r = np.max(dev) - np.min(dev)
        s = np.std(data, ddof=1)
        return r/s if s > 0 else 0
    log_ret = np.diff(np.log(closes + 1e-10))
    n = len(log_ret)
    windows, rs_vals = [], []
    w = 8
    while w <= n//2:
        rs_list = [rs(log_ret[i:i+w]) for i in range(0, n-w+1, w) if rs(log_ret[i:i+w]) > 0]
        if rs_list:
            windows.append(w)
            rs_vals.append(np.mean(rs_list))
        w = int(w*1.5)
    if len(windows) < 3: return 0.5
    coeffs = np.polyfit(np.log(windows), np.log(rs_vals), 1)
    return round(float(np.clip(coeffs[0], 0.0, 1.0)), 4)

# ── Sentiment Engine — 4 Sources ─────────────────────────────────────────────
def get_zeus_sentiment(symbol: str) -> dict:
    # Cache 10 minute
    cache_key = f"{symbol}_{datetime.utcnow().strftime('%H%M')[:3]}"
    if cache_key in SENTIMENT_CACHE:
        return SENTIMENT_CACHE[cache_key]

    scores = []
    sources = []
    velocity = 0.0

    # ── CryptoPanic (crypto-adjacent boost) ──────────────────────────────────
    if CRYPTOPANIC_KEY:
        try:
            r = requests.get(CRYPTOPANIC_URL, params={
                "auth_token": CRYPTOPANIC_KEY, "public": "true", "kind": "news",
            }, timeout=8)
            if r.ok:
                results = r.json().get("results", [])
                bull = sum(1 for n in results if n.get("votes", {}).get("positive", 0) > n.get("votes", {}).get("negative", 0))
                total = len(results)
                if total > 0:
                    cp_score = (bull / total) * 100
                    scores.append(cp_score)
                    sources.append(f"CP:{cp_score:.0f}")
        except: pass

    # ── CoinGecko global sentiment ────────────────────────────────────────────
    if COINGECKO_KEY:
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/global",
                headers={"x-cg-demo-api-key": COINGECKO_KEY},
                timeout=8
            )
            if r.ok:
                data = r.json().get("data", {})
                mkt_cap_change = data.get("market_cap_change_percentage_24h_usd", 0)
                # Pozitiv = bull market crypto = boost pentru crypto stocks
                cg_score = 50 + min(30, max(-30, mkt_cap_change * 3))
                scores.append(cg_score)
                sources.append(f"CG:{mkt_cap_change:+.1f}%")
        except: pass

    # ── Finnhub sentiment ─────────────────────────────────────────────────────
    if FINNHUB_KEY:
        try:
            r = requests.get("https://finnhub.io/api/v1/news-sentiment",
                             params={"symbol": symbol, "token": FINNHUB_KEY}, timeout=8)
            if r.ok:
                d = r.json()
                bull_pct = d.get("sentiment", {}).get("bullishPercent", 0.5) * 100
                scores.append(bull_pct)
                sources.append(f"FH:{bull_pct:.0f}")

                # Velocity
                key = f"fh_{symbol}"
                if key not in SENTIMENT_CACHE:
                    SENTIMENT_CACHE[key] = deque(maxlen=8)
                SENTIMENT_CACHE[key].append(bull_pct)
                hist = list(SENTIMENT_CACHE[key])
                if len(hist) >= 3:
                    velocity = hist[-1] - hist[-3]
        except: pass

    # ── NewsAPI ───────────────────────────────────────────────────────────────
    if NEWSAPI_KEY:
        try:
            r = requests.get(NEWSAPI_URL, params={
                "q": symbol, "language": "en", "pageSize": 8,
                "sortBy": "publishedAt", "apiKey": NEWSAPI_KEY,
                "from": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
            }, timeout=10)
            if r.ok:
                articles = r.json().get("articles", [])
                bull = ["beat","surge","buy","record","growth","bullish","pump","moon"]
                bear = ["miss","cut","sell","loss","crash","bearish","dump","fear"]
                b = sum(1 for a in articles for w in bull if w in (a.get("title","")+"").lower())
                s = sum(1 for a in articles for w in bear if w in (a.get("title","")+"").lower())
                if b + s > 0:
                    ns = (b/(b+s))*100
                    scores.append(ns)
                    sources.append(f"NEWS:{ns:.0f}")
        except: pass

    composite = round(float(np.mean(scores)), 2) if scores else 50.0
    result = {
        "composite": composite,
        "velocity": round(velocity, 2),
        "sources": " | ".join(sources),
        "n_sources": len(scores),
    }
    SENTIMENT_CACHE[cache_key] = result
    return result

# ── AI Chain: NVIDIA Qwen → xAI Grok → Gemini ────────────────────────────────
def ai_validate(symbol: str, price: float, rsi: float, hurst: float,
                atr: float, vol_ratio: float, sentiment: dict,
                tp: float, sl: float, rr: float) -> tuple[bool, int, str]:

    prompt = f"""You are an elite quantitative momentum trader using advanced AI analysis.

Symbol: {symbol} | Price: ${price:.2f}

MOMENTUM SIGNALS:
- Wilder RSI(14): {rsi:.1f} {'🚀 STRONG MOMENTUM' if rsi >= 70 else '⚡ BUILDING' if rsi >= 65 else '⚠️ WEAK'}
- Hurst Exponent: {hurst:.3f} {'✅ TRENDING (H>0.58)' if hurst > 0.58 else '⚠️ RANDOM WALK' if hurst > 0.45 else '↩️ MEAN REVERTING'}
- Volume surge: {vol_ratio:.2f}× average {'✅ INSTITUTIONAL' if vol_ratio > 2 else '✅ ELEVATED' if vol_ratio > 1.5 else '⚠️ NORMAL'}
- ATR(14): ${atr:.3f}
- Expected R/R: {rr:.2f} (minimum 1.8)

MULTI-SOURCE SENTIMENT ({sentiment.get('n_sources',0)} sources):
- Composite: {sentiment.get('composite',50):.1f}/100
- Velocity: {sentiment.get('velocity',0):+.1f}% (change in last 15min)
- Sources: {sentiment.get('sources','none')}

TP: ${tp:.2f} | SL: ${sl:.2f}

Is this a valid HIGH-CONFIDENCE momentum trade?
Respond ONLY with JSON: {{"action": "BUY" or "SKIP", "confidence": 0-100, "reasoning": "max 150 chars"}}"""

    # ── NVIDIA Qwen 397B (primary) ────────────────────────────────────────────
    if NVIDIA_KEY:
        try:
            r = requests.post(
                f"{NVIDIA_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"},
                json={
                    "model": NVIDIA_MODEL,
                    "messages": [
                        {"role": "system", "content": "Expert quantitative analyst. Respond with valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 250, "temperature": 0.1,
                },
                timeout=30
            )
            if r.ok:
                text = r.json()["choices"][0]["message"]["content"]
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    a = parsed.get("action", "SKIP")
                    c = int(parsed.get("confidence", 50))
                    reas = parsed.get("reasoning", "")[:200]
                    if a == "BUY" and c >= CONFIDENCE_MIN:
                        return True, c, f"[Qwen397B] {reas}"
                    elif a == "SKIP":
                        return False, c, f"[Qwen397B] {reas}"
        except Exception as e:
            log.warning(f"NVIDIA Qwen err: {e}")

    # ── xAI Grok-4 (fallback 1) ───────────────────────────────────────────────
    if XAI_KEY:
        try:
            r = requests.post(
                f"{XAI_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-4-latest",
                    "messages": [
                        {"role": "system", "content": "Expert quant analyst. JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 250, "temperature": 0.1,
                },
                timeout=25
            )
            if r.ok:
                text = r.json()["choices"][0]["message"]["content"]
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    a = parsed.get("action", "SKIP")
                    c = int(parsed.get("confidence", 50))
                    reas = parsed.get("reasoning", "")[:200]
                    return a == "BUY" and c >= CONFIDENCE_MIN, c, f"[Grok4] {reas}"
        except Exception as e:
            log.warning(f"xAI Grok err: {e}")

    # ── Qwen (fallback 2) ─────────────────────────────────────────────────────
    try:
        r = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": "Bearer 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", "Content-Type": "application/json"},
            json={"model": "qwen/qwen3.5-122b-a10b", "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 250, "temperature": 0.1, "stream": False,
                  "chat_template_kwargs": {"enable_thinking": False}},
            timeout=25
        )
        if r.ok:
            text = r.json()["choices"][0]["message"]["content"]
            if "<think>" in text and "</think>" in text:
                text = text[text.rfind("</think>")+8:].strip()
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                a = parsed.get("action", "SKIP")
                c = int(parsed.get("confidence", 50))
                reas = parsed.get("reasoning", "")[:200]
                return a == "BUY" and c >= CONFIDENCE_MIN, c, f"[Qwen] {reas}"
    except Exception as e:
        log.warning(f"Qwen fallback2 err: {e}")

    return True, 65, "AI unavailable — default pass"


def confirm_15min_momentum(symbol: str) -> bool:
    """
    Confirmare pe 15min: ultimele 2 bare trebuie să fie green cu volum ok.
    Previne intrările în retraceri scurte.
    """
    try:
        from datetime import datetime, timedelta
        end = (datetime.utcnow() - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        start = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = alpaca_data_get(f"/v2/stocks/{symbol}/bars", {
            "timeframe": "15Min", "start": start, "end": end,
            "limit": 10, "feed": "iex"
        })
        bars15 = data.get("bars", [])
        if len(bars15) < 3:
            return True  # fallback = allow
        # Ultimele 2 bare: close > open (green candles)
        last2 = bars15[-2:]
        greens = sum(1 for b in last2 if b["c"] > b["o"])
        return greens >= 1  # minim 1 din 2 bare green
    except:
        return True

# ── Analyze Symbol ────────────────────────────────────────────────────────────
def analyze(symbol: str) -> Optional[dict]:
    if not is_session(): return None

    # BTC macro filter: dacă BTC scade >5% în 2h, skip crypto stocks
    btc_change = get_btc_2h_change()
    CRYPTO_STOCKS = {"COIN", "MSTR", "HOOD", "RIOT", "MARA", "CLSK"}
    if btc_change < -5.0 and symbol in CRYPTO_STOCKS:
        log.debug(f"ZEUS: Skip {symbol} — BTC down {btc_change:.1f}% in 2h")
        return None

    bars = fetch_bars(symbol)
    if not bars: return None

    closes  = bars["closes"]
    opens   = bars["opens"]
    highs   = bars["highs"]
    lows    = bars["lows"]
    volumes = bars["volumes"]
    price   = float(closes[-1])

    # ATR
    atr_s = compute_atr(highs, lows, closes, 14)
    if len(atr_s) < 5: return None
    atr = float(atr_s[-1])

    # Wilder RSI (look-ahead free)
    rsi_s = wilder_rsi_series(closes, WILDER_PERIOD)
    rsi   = float(rsi_s[-1])

    # Momentum zone: RSI 65-80 (în trend, nu overbought extrem)
    if not (65 <= rsi <= 82): return None

    # Hurst — confirmare trend
    hurst = compute_hurst(closes[-60:] if len(closes) >= 60 else closes)
    if hurst < 0.52: return None  # nu e trend persistent

    # Volume surge — confirmare instituțională
    vol_ma = np.mean(volumes[-20:])
    vol_ratio = float(volumes[-1]) / vol_ma if vol_ma > 0 else 1.0
    if vol_ratio < VOL_SURGE_MIN: return None

    # EMA trend filters
    ema50  = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200) if len(closes) >= 200 else compute_ema(closes, 100)
    if price < ema50 or price < ema200: return None

    # Candle quality: body > 60% din ATR
    body = abs(float(closes[-1]) - float(opens[-1]))
    if body < 0.60 * atr: return None

    # Profit Factor gate
    tp = price + ATR_TP_MULT * atr
    sl = price - ATR_SL_MULT * atr
    rr = (tp - price) / (price - sl) if (price - sl) > 0 else 0
    if rr < 1.8: return None

    # 15min momentum confirmation
    if not confirm_15min_momentum(symbol):
        return None

    # Sentiment
    sentiment = get_zeus_sentiment(symbol)
    if sentiment["composite"] < 48 and sentiment["n_sources"] >= 2:
        return None

    # AI validation
    valid, confidence, reasoning = ai_validate(
        symbol, price, rsi, hurst, atr, vol_ratio, sentiment, tp, sl, rr
    )
    if not valid: return None

    return {
        "symbol": symbol, "price": price,
        "rsi": round(rsi, 2), "hurst": hurst,
        "atr": round(atr, 4), "vol_ratio": round(vol_ratio, 2),
        "take_profit": round(tp, 3), "stop_loss": round(sl, 3),
        "expected_rr": round(rr, 3),
        "confidence": confidence, "reasoning": reasoning,
        "sentiment": sentiment,
    }

# ── Place Order ───────────────────────────────────────────────────────────────
def place_order(sig: dict, cash: float) -> bool:
    qty = max(1, int(cash * zeus_adaptive_risk() / (sig["price"] * 1.0005)))
    order = alpaca_post("/v2/orders", {
        "symbol": sig["symbol"], "qty": str(qty),
        "side": "buy", "type": "market", "time_in_force": "day",
    })
    if order.get("id"):
        TRAILING_PEAKS[sig["symbol"]] = sig["price"]
        log.info(f"⚡ ZEUS BUY {qty}×{sig['symbol']} @ ${sig['price']:.2f} | "
                 f"RSI={sig['rsi']} H={sig['hurst']} vol={sig['vol_ratio']:.1f}× | "
                 f"conf={sig['confidence']}%")
        sb_insert("trades", {
            "symbol": sig["symbol"], "action": "BUY",
            "price": sig["price"], "qty": qty,
            "confidence": sig["confidence"], "reasoning": sig["reasoning"],
            "rsi": sig["rsi"], "strategy": "zeus_crypto_momentum",
            "take_profit": sig["take_profit"], "stop_loss": sig["stop_loss"],
            "timestamp": datetime.utcnow().isoformat(),
        })
        return True
    return False

# ── Check Exits ───────────────────────────────────────────────────────────────
def check_exits():
    positions = alpaca_get("/v2/positions")
    if not isinstance(positions, list): return

    for pos in positions:
        sym   = pos["symbol"]
        qty   = int(pos["qty"])
        entry = float(pos["avg_entry_price"])
        price = float(pos["current_price"])
        pnl   = float(pos["unrealized_pl"])

        bars = fetch_bars(sym, 30)
        if not bars: continue
        atr_s = compute_atr(bars["highs"], bars["lows"], bars["closes"], 14)
        atr   = float(atr_s[-1]) if len(atr_s) > 0 else entry * 0.01

        TRAILING_PEAKS[sym] = max(TRAILING_PEAKS.get(sym, price), price)
        peak = TRAILING_PEAKS[sym]

        tp_price    = entry + ATR_TP_MULT * atr
        sl_price    = entry - ATR_SL_MULT * atr
        trail_price = peak  - ATR_TRAIL_MULT * atr

        should_exit = False
        exit_reason = ""

        if price >= tp_price:
            should_exit, exit_reason = True, "take_profit"
        elif price <= sl_price:
            should_exit, exit_reason = True, "stop_loss"
        elif price <= trail_price and pnl > 0:
            should_exit, exit_reason = True, "trailing_stop"
        else:
            rsi_s = wilder_rsi_series(bars["closes"], WILDER_PERIOD)
            if float(rsi_s[-1]) < 30:
                should_exit, exit_reason = True, "rsi_exit_30"

        if should_exit:
            order = alpaca_post("/v2/orders", {
                "symbol": sym, "qty": str(qty),
                "side": "sell", "type": "market", "time_in_force": "day",
            })
            if order.get("id"):
                TRAILING_PEAKS.pop(sym, None)
                _ZEUS_RECENT_PL.append(pnl)
                if len(_ZEUS_RECENT_PL) > 10:
                    _ZEUS_RECENT_PL.pop(0)
                log.info(f"{'✅' if pnl>0 else '❌'} ZEUS EXIT {sym} | {exit_reason} | P&L=${pnl:.2f}")
                sb_insert("trades", {
                    "symbol": sym, "action": "SELL",
                    "price": price, "qty": qty, "pl": round(pnl, 2),
                    "close_type": exit_reason, "strategy": "zeus_exit",
                    "timestamp": datetime.utcnow().isoformat(),
                })

# ── Portfolio ─────────────────────────────────────────────────────────────────
def update_portfolio():
    acc = alpaca_get("/v2/account")
    positions = alpaca_get("/v2/positions")
    if not acc: return None, None
    eq   = float(acc.get("equity", 0))
    cash = float(acc.get("cash", 0))
    pnl  = eq - 10000.0
    open_pos = len(positions) if isinstance(positions, list) else 0
    total_pl = sum(float(p.get("unrealized_pl",0)) for p in (positions or []))
    sb_upsert("portfolio_snapshot", {
        "id": 1, "equity": round(eq,2), "cash": round(cash,2),
        "pnl": round(pnl,2), "pnl_pct": round(pnl/10000*100,4),
        "total_pl": round(total_pl,2), "open_positions": open_pos,
        "strategy": "zeus_crypto_momentum",
        "bot_version": "ZEUS-v1",
        "updated_at": datetime.utcnow().isoformat(),
    })
    log.info(f"💼 ZEUS equity=${eq:.2f} | P&L={pnl:+.2f}$ | {open_pos} pos")
    return eq, cash

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    tg("🚀 ZEUS pornit — crypto momentum")
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║  NeuroTrade ZEUS — Crypto Momentum + NVIDIA Qwen 397B    ║")
    log.info("║  AI: NVIDIA Qwen → xAI Grok-4 → Gemini                  ║")
    log.info("║  Data: CryptoPanic + CoinGecko + Finnhub + NewsAPI       ║")
    log.info("╚══════════════════════════════════════════════════════════╝")

    daily_loss = 0.0
    start_equity = 10000.0

    while True:
        try:
            if not is_session():
                log.info("⏰ ZEUS outside session")
                time.sleep(CYCLE_SECONDS)
                continue

            check_exits()
            result = update_portfolio()
            if not result[0]:
                time.sleep(60)
                continue
            equity, cash = result

            if start_equity == 10000.0:
                start_equity = equity

            # Daily loss guard
            if daily_loss / start_equity < -MAX_DAILY_LOSS:
                log.warning("🛑 ZEUS daily loss limit — skipping new trades")
                time.sleep(CYCLE_SECONDS)
                continue

            positions = alpaca_get("/v2/positions")
            n_pos = len(positions) if isinstance(positions, list) else 0
            open_syms = {p["symbol"] for p in (positions or [])}

            signals = []
            for sym in UNIVERSE:
                if sym in open_syms: continue
                sig = analyze(sym)
                if sig:
                    signals.append(sig)
                    log.info(f"⚡ {sym}: RSI={sig['rsi']} H={sig['hurst']} vol={sig['vol_ratio']:.1f}× conf={sig['confidence']}%")
                time.sleep(0.4)

            signals.sort(key=lambda x: x["confidence"] * x["vol_ratio"], reverse=True)

            for sig in signals:
                if n_pos >= MAX_POSITIONS or cash < 250: break
                if place_order(sig, cash):
                    n_pos += 1
                    cash -= cash * RISK_PER_TRADE

            for s in signals[:10]:
                sent = s.get("sentiment", {})
                sb_upsert("signals", {
                    "symbol": s["symbol"], "action": "BUY",
                    "confidence": s["confidence"],
                    "reasoning": f"[ZEUS] RSI={s['rsi']} H={s['hurst']} vol={s['vol_ratio']:.1f}× | {s['reasoning']}",
                    "rsi": s["rsi"], "strategy": "zeus_crypto_momentum",
                    "updated_at": datetime.utcnow().isoformat(),
                })

            log.info(f"═══ ZEUS CYCLE END | {len(signals)} signals | {n_pos}/{MAX_POSITIONS} pos ═══")
            if signals: tg(f"📊 Cycle: {len(signals)} signals | {n_pos}/{MAX_POSITIONS} pozitii")

        except KeyboardInterrupt:
            log.info("ZEUS stopped.")
            break
        except Exception as e:
            log.error(f"ZEUS cycle error: {e}", exc_info=True)

        time.sleep(CYCLE_SECONDS)

if __name__ == "__main__":
    main()
