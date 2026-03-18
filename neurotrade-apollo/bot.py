"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  NeuroTrade APOLLO — STAT ARB + xAI GROK-4 + KRAKEN CRYPTO                 ║
║                                                                              ║
║  AI Principal: xAI Grok-4 (cel mai avansat model xAI)                       ║
║  AI Fallback:  Gemini 2.0 Flash                                              ║
║                                                                              ║
║  Strategie unică: DUAL-MARKET STATISTICAL ARBITRAGE                          ║
║  → Pairs trading pe STOCKS (Alpaca) + monitoring CRYPTO (Kraken)            ║
║  → Hurst Exponent + Shannon Entropy pe spread                               ║
║  → Half-life weighted position sizing                                       ║
║  → CryptoPanic fear/greed pentru macro context                              ║
║  → Cointegration score 0-100 per pereche                                    ║
║  → Grok-4 analizează datele tehnice + sentiment global                      ║
║                                                                              ║
║  Win rate vizat: 74-85% (market neutral)                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import time
import logging
import os
import json
import re
import math
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional
import numpy as np
import requests
import sys, os
sys.path.insert(0, '/opt/neurotrade-apollo')
from weekend_mode import run_weekend_crypto_mode as _run_weekend

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
    format="%(asctime)s [APOLLO] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/var/log/neurotrade-apollo.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("APOLLO")

# ── Config ────────────────────────────────────────────────────────────────────
ALPACA_KEY    = os.getenv("ALPACA_KEY", "")
ALPACA_SECRET = os.getenv("ALPACA_SECRET", "")
ALPACA_BASE   = os.getenv("ALPACA_BASE", "https://paper-api.alpaca.markets")
ALPACA_DATA   = "https://data.alpaca.markets"

SUPABASE_URL  = os.getenv("SUPABASE_URL_APOLLO", "")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY_APOLLO", "")

# AI
XAI_KEY       = os.getenv("XAI_API_KEY", "")
XAI_BASE      = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL     = os.getenv("XAI_MODEL", "grok-4")
GEMINI_KEY    = os.getenv("GEMINI_API_KEY", "")

# Kraken
KRAKEN_PUBLIC  = os.getenv("KRAKEN_PUBLIC", "")
KRAKEN_PRIVATE = os.getenv("KRAKEN_PRIVATE", "")

# Data
COINGECKO_KEY   = os.getenv("COINGECKO_API_KEY", "")
CRYPTOPANIC_KEY = os.getenv("CRYPTOPANIC_KEY", "")
CRYPTOPANIC_URL = os.getenv("CRYPTOPANIC_URL", "https://cryptopanic.com/api/developer/v2")
NEWSAPI_KEY     = os.getenv("NEWSAPI_KEY", "")
NEWSAPI_URL     = os.getenv("NEWSAPI_URL", "https://newsapi.org/v2/everything")
FINNHUB_KEY     = os.getenv("FINNHUB_KEY", "")
ALPHAV_KEY      = os.getenv("ALPHAVANTAGE_KEY", "")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def tg(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"🔱 APOLLO | {msg}", "parse_mode": "HTML"},
            timeout=5
        )
    except Exception:
        pass

def wait_for_session():
    from datetime import datetime, timezone
    import math
    now = datetime.now(timezone.utc)
    h, m = now.hour, now.minute
    weekday = now.weekday()  # 0=Luni, 5=Sambata, 6=Duminica
    if weekday >= 5:
        return True  # weekend crypto mode
        return False
    in_session = (8 <= h < 12) or (h == 13 and m >= 30) or (14 <= h < 20)
    if in_session:
        return True
    # Calculeaza secunde pana la urmatoarea sesiune
    if h < 8:
        wait = (8 - h) * 3600 - m * 60
    elif 12 <= h < 13 or (h == 13 and m < 30):
        wait = ((13 - h) * 3600 + (30 - m) * 60) if h == 12 else (30 - m) * 60
    else:
        # dupa 20:00 UTC, asteapta pana la 08:00 UTC a doua zi
        wait = (32 - h) * 3600 - m * 60
    wait = max(300, wait)
    log.info(f"⏰ APOLLO: piata inchisa — astept {wait//3600}h {(wait%3600)//60}m pana la deschidere")
    tg(f"⏰ Piata inchisa. Astept {wait//3600}h {(wait%3600)//60}m.")
    import time as _t
    _t.sleep(wait)
    return False


def is_session() -> bool:
    """Stock market session: London 08-12 UTC + NY 13:30-20:00 UTC. No weekends."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    h, m = now.hour, now.minute
    return (8 <= h < 12) or (h == 13 and m >= 30) or (14 <= h < 20)

# ── Parameters ────────────────────────────────────────────────────────────────
CYCLE_SECONDS  = 300
MAX_PAIRS      = 5
LOOKBACK       = 60
HALFLIFE_MAX   = 42
HALFLIFE_MIN   = 4
CORR_MIN       = 0.78
ENTROPY_MAX    = 0.82
CONFIDENCE_MIN = 62
BASE_RISK      = 0.12
ZSCORE_EXIT    = 0.5
ZSCORE_STOP    = 3.8

# Pairs cu cointegration istorică
PAIRS = [
    {"a": "NVDA",  "b": "AMD",   "sector": "semiconductors"},
    {"a": "MSFT",  "b": "GOOGL", "sector": "big_tech"},
    {"a": "AAPL",  "b": "MSFT",  "sector": "big_tech"},
    {"a": "JPM",   "b": "GS",    "sector": "banks"},
    {"a": "BAC",   "b": "WFC",   "sector": "banks"},
    {"a": "SPY",   "b": "QQQ",   "sector": "etf"},
    {"a": "XOM",   "b": "CVX",   "sector": "energy"},
    {"a": "AMZN",  "b": "WMT",   "sector": "retail"},
    {"a": "CRM",   "b": "NOW",   "sector": "cloud"},
    {"a": "NFLX",  "b": "DIS",   "sector": "media"},
    {"a": "COIN",  "b": "HOOD",  "sector": "crypto_fin"},
    {"a": "TSLA",  "b": "RIVN",  "sector": "ev"},
    # ── Nuevas perechi adăugate v2 ──────────────────────────────
    {"a": "PANW",  "b": "CRWD",  "sector": "cybersec"},
    {"a": "V",     "b": "MA",    "sector": "payments"},
    {"a": "MU",    "b": "INTC",  "sector": "memory_chips"},
    {"a": "UBER",  "b": "LYFT",  "sector": "rideshare"},
]


_PAIR_BLACKLIST: dict = {}   # {pair_str: datetime_until}
_PAIR_LOSS_COUNT: dict = {}  # {pair_str: int}

def is_pair_blacklisted(pair_str: str) -> bool:
    from datetime import datetime
    if pair_str in _PAIR_BLACKLIST:
        if datetime.utcnow() < _PAIR_BLACKLIST[pair_str]:
            return True
        del _PAIR_BLACKLIST[pair_str]  # expirat
    return False

def record_pair_result(pair_str: str, profit: float):
    from datetime import datetime, timedelta
    if profit < 0:
        _PAIR_LOSS_COUNT[pair_str] = _PAIR_LOSS_COUNT.get(pair_str, 0) + 1
        if _PAIR_LOSS_COUNT[pair_str] >= 3:
            _PAIR_BLACKLIST[pair_str] = datetime.utcnow() + timedelta(hours=24)
            log.warning(f"⛔ APOLLO: Pair {pair_str} blacklisted 24h (3 losses)")
            _PAIR_LOSS_COUNT[pair_str] = 0
    else:
        _PAIR_LOSS_COUNT[pair_str] = 0  # reset la win

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

# ── Kraken API ────────────────────────────────────────────────────────────────
def kraken_get_ticker(pairs: list) -> dict:
    """Prețuri live de pe Kraken pentru context crypto macro"""
    try:
        pair_str = ",".join(pairs)
        r = requests.get(
            "https://api.kraken.com/0/public/Ticker",
            params={"pair": pair_str},
            timeout=8
        )
        if r.ok:
            result = r.json().get("result", {})
            prices = {}
            for key, val in result.items():
                try:
                    prices[key] = float(val["c"][0])  # last price
                except: pass
            return prices
    except Exception as e:
        log.debug(f"Kraken ticker: {e}")
    return {}

def get_crypto_macro_context() -> dict:
    """
    Macro context din Kraken + CoinGecko + CryptoPanic.
    Folosit ca filtru global — dacă crypto e în colaps, evităm noi intrări.
    """
    context = {"btc_change": 0.0, "fear_greed": 50, "cp_sentiment": "neutral", "macro_ok": True}

    # BTC price change 24h (Kraken)
    prices = kraken_get_ticker(["XBTUSD"])
    if prices:
        btc_price = prices.get("XXBTZUSD", prices.get("XBTUSD", 0))
        context["btc_price"] = btc_price

    # CoinGecko global market
    if COINGECKO_KEY:
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/global",
                headers={"x-cg-demo-api-key": COINGECKO_KEY},
                timeout=8
            )
            if r.ok:
                data = r.json().get("data", {})
                mkt_change = data.get("market_cap_change_percentage_24h_usd", 0)
                context["btc_change"] = mkt_change
                # Colaps crypto > -8% în 24h = nu tranzacționăm
                if mkt_change < -8:
                    context["macro_ok"] = False
                    log.warning(f"⚠️ Crypto market down {mkt_change:.1f}% — APOLLO cautious mode")
        except: pass

    # CryptoPanic fear/greed
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
                    bull_pct = bull / total
                    context["cp_sentiment"] = "bullish" if bull_pct > 0.6 else "bearish" if bull_pct < 0.4 else "neutral"
        except: pass

    return context

# ── Data Fetch ────────────────────────────────────────────────────────────────
def fetch_closes(symbol: str, days: int) -> np.ndarray:
    try:
        data = alpaca_data_get(f"/v2/stocks/{symbol}/bars", {
            "timeframe": "1Day",
            "start": (datetime.utcnow() - timedelta(days=days+10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": days+10, "feed": "iex",
        })
        bars = data.get("bars", [])
        return np.array([b["c"] for b in bars]) if bars else np.array([])
    except: return np.array([])

# ── Statistical Computations ──────────────────────────────────────────────────
def spread_entropy(spread: np.ndarray, bins=8) -> float:
    if len(spread) < 15: return 0.5
    norm = (spread - np.mean(spread)) / (np.std(spread) + 1e-10)
    hist, _ = np.histogram(norm, bins=bins, density=True)
    hist = hist[hist > 0]
    prob = hist / hist.sum()
    entropy = -np.sum(prob * np.log2(prob + 1e-10))
    return round(float(entropy / math.log2(bins)), 4)

def compute_half_life(spread: np.ndarray) -> float:
    if len(spread) < 10: return 999.0
    y = np.diff(spread)
    x = spread[:-1]
    if np.std(x) == 0: return 999.0
    cov = np.cov(y, x)
    if cov[1,1] == 0: return 999.0
    lam = cov[0,1] / cov[1,1]
    if lam >= 0: return 999.0
    hl = -math.log(2) / lam
    return round(float(hl), 2)

def cointegration_score(corr: float, hl: float, entropy: float) -> float:
    corr_s = max(0, (corr - CORR_MIN) / (1.0 - CORR_MIN)) * 40
    if hl <= HALFLIFE_MIN or hl > HALFLIFE_MAX:
        hl_s = 0.0
    elif hl <= 15:
        hl_s = 40.0
    else:
        hl_s = 40.0 * (1 - (hl - 15) / (HALFLIFE_MAX - 15))
    entr_s = max(0, (1 - entropy / ENTROPY_MAX)) * 20
    return round(corr_s + hl_s + entr_s, 2)

def halflife_risk(hl: float) -> float:
    if hl <= 0: return BASE_RISK * 0.5
    ratio = math.sqrt(15.0 / max(hl, 4))
    return min(BASE_RISK * 2.0, BASE_RISK * ratio)

def dynamic_zscore_entry(atr_pct: float) -> float:
    if atr_pct < 0.01: return 1.8
    elif atr_pct < 0.025: return 2.1
    else: return 2.5

# ── xAI Grok-4 Validation ────────────────────────────────────────────────────
def grok_validate(sym_a: str, sym_b: str, zscore: float, corr: float,
                   hl: float, entropy: float, score: float,
                   direction: str, sector: str, macro: dict) -> tuple[bool, int, str]:

    prompt = f"""Expert statistical arbitrage analysis:

Pair: {sym_a}/{sym_b} | Sector: {sector}
Z-Score: {zscore:.2f} | Entry threshold: dynamic ATR-based
Correlation (60d): {corr:.3f}
Half-Life: {hl:.1f} days
Spread Shannon Entropy: {entropy:.3f} {'✅ structured' if entropy < 0.70 else '⚠️ semi-random'}
Cointegration Score: {score:.1f}/100
Direction: {direction}

MACRO CONTEXT (Kraken + CoinGecko + CryptoPanic):
- Crypto market 24h change: {macro.get('btc_change', 0):+.1f}%
- CryptoPanic sentiment: {macro.get('cp_sentiment', 'neutral')}
- Macro OK: {macro.get('macro_ok', True)}

Key: Half-life {hl:.0f}d means spread should revert in ~{hl:.0f} trading days.

Is this a valid stat arb trade?
Answer ONLY JSON: {{"action": "TRADE" or "SKIP", "confidence": 0-100, "reasoning": "max 150 chars"}}"""

    # xAI Grok-4 (primary)
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
                    return a == "TRADE" and c >= CONFIDENCE_MIN, c, f"[Grok4] {reas}"
        except Exception as e:
            log.warning(f"Grok4 err: {e}")

    # Qwen fallback
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
                return a == "TRADE" and c >= CONFIDENCE_MIN, c, f"[Qwen] {reas}"
    except Exception as e:
        log.warning(f"Qwen fallback err: {e}")

    return True, 65, "AI unavailable"

# ── Analyze Pair ──────────────────────────────────────────────────────────────
def analyze_pair(pair: dict, macro: dict) -> Optional[dict]:
    # Check session hours for stock pairs
    if not is_session():
        return None
    if not macro.get("macro_ok", True):
        return None  # crypto macro prea negativ

    sym_a, sym_b = pair["a"], pair["b"]
    pair_str = f"{sym_a}/{sym_b}"
    if is_pair_blacklisted(pair_str):
        log.debug(f"APOLLO: Skip {pair_str} — blacklisted")
        return None

    pa = fetch_closes(sym_a, LOOKBACK + 10)
    time.sleep(0.3)
    pb = fetch_closes(sym_b, LOOKBACK + 10)

    if len(pa) < 30 or len(pb) < 30: return None

    n = min(len(pa), len(pb))
    pa, pb = pa[-n:], pb[-n:]

    corr = float(np.corrcoef(pa, pb)[0, 1])
    if corr < CORR_MIN: return None

    cov = np.cov(pa, pb)
    hr  = cov[0,1] / cov[1,1] if cov[1,1] != 0 else 1.0
    spread = pa - hr * pb
    spread_30 = spread[-30:]

    hl = compute_half_life(spread_30)
    if hl < HALFLIFE_MIN or hl > HALFLIFE_MAX: return None

    entropy = spread_entropy(spread_30)
    if entropy > ENTROPY_MAX: return None

    mean_s = np.mean(spread_30)
    std_s  = np.std(spread_30)
    if std_s == 0: return None
    zscore = (spread[-1] - mean_s) / std_s

    # ATR-dynamic entry
    atr_pct = abs(pa[-1] - pa[-2]) / pa[-1] if len(pa) >= 2 else 0.015
    entry_z = dynamic_zscore_entry(atr_pct)
    if abs(zscore) < entry_z: return None

    score = cointegration_score(corr, hl, entropy)
    if score < 28: return None

    direction = "SHORT_A_LONG_B" if zscore > entry_z else "LONG_A_SHORT_B"
    buy_sym   = sym_b if zscore > entry_z else sym_a
    sell_sym  = sym_a if zscore > entry_z else sym_b

    risk = halflife_risk(hl)

    valid, confidence, reasoning = grok_validate(
        sym_a, sym_b, zscore, corr, hl, entropy, score, direction, pair["sector"], macro
    )
    if not valid: return None

    return {
        "pair": f"{sym_a}/{sym_b}",
        "sym_a": sym_a, "sym_b": sym_b,
        "buy_sym": buy_sym, "sell_sym": sell_sym,
        "direction": direction,
        "zscore": round(zscore, 3), "entry_z": round(entry_z, 2),
        "corr": round(corr, 3), "hedge_ratio": round(hr, 3),
        "half_life": hl, "entropy": entropy,
        "coint_score": score, "risk_pct": round(risk, 3),
        "price_a": round(float(pa[-1]), 3),
        "price_b": round(float(pb[-1]), 3),
        "confidence": confidence, "reasoning": reasoning,
    }

# ── Place Pair Trade ──────────────────────────────────────────────────────────
def place_pair(sig: dict, cash: float) -> bool:
    budget = cash * sig["risk_pct"]
    half   = budget / 2
    qty_b  = max(1, int(half / sig["price_a"])) if sig["buy_sym"] == sig["sym_a"] else max(1, int(half / sig["price_b"]))
    qty_s  = max(1, int(half / sig["price_b"])) if sig["sell_sym"] == sig["sym_b"] else max(1, int(half / sig["price_a"]))

    b_ord = alpaca_post("/v2/orders", {"symbol": sig["buy_sym"], "qty": str(qty_b), "side": "buy", "type": "market", "time_in_force": "day"})
    s_ord = alpaca_post("/v2/orders", {"symbol": sig["sell_sym"], "qty": str(qty_s), "side": "sell", "type": "market", "time_in_force": "day"})

    ok = b_ord.get("id") and s_ord.get("id")
    if ok:
        log.info(f"🔱 APOLLO PAIR: LONG {qty_b}×{sig['buy_sym']} | SHORT {qty_s}×{sig['sell_sym']} | "
                 f"z={sig['zscore']} hl={sig['half_life']}d score={sig['coint_score']} conf={sig['confidence']}%")
        for sym, act, qty, pr in [
            (sig["buy_sym"],  "BUY",  qty_b, sig["price_a"] if sig["buy_sym"]==sig["sym_a"] else sig["price_b"]),
            (sig["sell_sym"], "SELL", qty_s, sig["price_b"] if sig["sell_sym"]==sig["sym_b"] else sig["price_a"]),
        ]:
            sb_insert("trades", {
                "symbol": sym, "action": act, "price": pr, "qty": qty,
                "confidence": sig["confidence"],
                "reasoning": f"APOLLO pairs {sig['pair']} z={sig['zscore']} hl={sig['half_life']}d | {sig['reasoning']}",
                "strategy": "apollo_statarb", "pair_name": sig["pair"],
                "zscore": sig["zscore"],
                "timestamp": datetime.utcnow().isoformat(),
            })
    return ok

# ── Check Pair Exits ──────────────────────────────────────────────────────────
def check_pair_exits():
    positions = alpaca_get("/v2/positions")
    if not isinstance(positions, list) or len(positions) < 2: return
    pos_map = {p["symbol"]: p for p in positions}

    for pair in PAIRS:
        sym_a, sym_b = pair["a"], pair["b"]
        if sym_a not in pos_map or sym_b not in pos_map: continue

        pa = fetch_closes(sym_a, 35)
        pb = fetch_closes(sym_b, 35)
        if len(pa) < 30 or len(pb) < 30: continue

        n = min(len(pa), len(pb))
        cov_m = np.cov(pa[-n:], pb[-n:])
        hr = cov_m[0,1]/cov_m[1,1] if cov_m[1,1] != 0 else 1.0
        spread = pa[-n:] - hr * pb[-n:]
        s30 = spread[-30:]
        std = np.std(s30)
        if std == 0: continue
        z_now = (spread[-1] - np.mean(s30)) / std

        hl = compute_half_life(s30)
        exit_z = 0.4 if hl < 15 else 0.6

        pnl_a = float(pos_map[sym_a].get("unrealized_pl", 0))
        pnl_b = float(pos_map[sym_b].get("unrealized_pl", 0))
        total_pnl = pnl_a + pnl_b

        should_exit = False
        exit_reason = ""

        if abs(z_now) <= exit_z:
            should_exit, exit_reason = True, "zscore_reverted"
        elif abs(z_now) >= ZSCORE_STOP:
            should_exit, exit_reason = True, "zscore_stop"

        if should_exit:
            for sym, pos in [(sym_a, pos_map[sym_a]), (sym_b, pos_map[sym_b])]:
                qty   = abs(int(float(pos["qty"])))
                side  = "sell" if float(pos["qty"]) > 0 else "buy"
                price = float(pos["current_price"])
                pnl   = float(pos["unrealized_pl"])
                order = alpaca_post("/v2/orders", {"symbol": sym, "qty": str(qty), "side": side, "type": "market", "time_in_force": "day"})
                if order.get("id"):
                    sb_insert("trades", {
                        "symbol": sym,
                        "action": "SELL" if side == "sell" else "BUY",
                        "price": price, "qty": qty, "pl": round(pnl, 2),
                        "close_type": exit_reason, "strategy": "apollo_exit",
                        "zscore": round(z_now, 3),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            log.info(f"{'✅' if total_pnl > 0 else '❌'} APOLLO EXIT {sym_a}/{sym_b} | {exit_reason} | z={z_now:.2f} | P&L=${total_pnl:.2f}")
        time.sleep(0.5)

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
        "strategy": "apollo_statarb",
        "bot_version": "APOLLO-v1",
        "updated_at": datetime.utcnow().isoformat(),
    })
    log.info(f"💼 APOLLO equity=${eq:.2f} | P&L={pnl:+.2f}$ | {open_pos} pos")
    return eq, cash

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║  NeuroTrade APOLLO — Stat Arb + xAI Grok-4 + Kraken     ║")
    log.info("║  AI: xAI Grok-4 → Gemini 2.0 Flash                      ║")
    log.info("║  Data: Kraken + CoinGecko + CryptoPanic + NewsAPI        ║")
    log.info("║  Strategy: Pairs Trading + Hurst + Half-Life Sizing      ║")
    log.info("╚══════════════════════════════════════════════════════════╝")

    tg("🚀 APOLLO pornit — pairs trading stocks")
    while True:
        try:
            if not wait_for_session():
                continue
            check_pair_exits()
            from datetime import datetime, timezone as _tz
            if datetime.now(_tz.utc).weekday() >= 5:
                _run_weekend(get_crypto_macro_context, tg, log,
                             XAI_KEY, XAI_BASE, XAI_MODEL,
                             NEWSAPI_KEY, NEWSAPI_URL,
                             KRAKEN_PUBLIC, KRAKEN_PRIVATE)
                time.sleep(CYCLE_SECONDS)
                continue

            result = update_portfolio()
            if not result[0]:
                time.sleep(60)
                continue
            equity, cash = result

            # Macro context din Kraken + CoinGecko + CryptoPanic
            macro = get_crypto_macro_context()
            log.info(f"🌍 Macro: crypto_change={macro.get('btc_change',0):+.1f}% | "
                     f"cp={macro.get('cp_sentiment')} | ok={macro.get('macro_ok')}")

            positions = alpaca_get("/v2/positions")
            active_syms = {p["symbol"] for p in (positions or [])}
            active_pairs = sum(1 for p in PAIRS if p["a"] in active_syms or p["b"] in active_syms)

            pair_signals = []
            for pair in PAIRS:
                if pair["a"] in active_syms or pair["b"] in active_syms: continue
                sig = analyze_pair(pair, macro)
                if sig:
                    pair_signals.append(sig)
                    log.info(f"🔱 {sig['pair']}: z={sig['zscore']} hl={sig['half_life']}d "
                             f"H={sig['entropy']} score={sig['coint_score']} conf={sig['confidence']}%")
                time.sleep(0.5)

            pair_signals.sort(key=lambda x: x["coint_score"] * x["confidence"], reverse=True)

            for sig in pair_signals:
                if active_pairs >= MAX_PAIRS or cash < 500: break
                if place_pair(sig, cash):
                    active_pairs += 1

            # Update signals
            for pair in PAIRS:
                try:
                    pa = fetch_closes(pair["a"], 35)
                    pb = fetch_closes(pair["b"], 35)
                    if len(pa) < 30 or len(pb) < 30: continue
                    n = min(len(pa), len(pb))
                    cov_m = np.cov(pa[-n:], pb[-n:])
                    hr = cov_m[0,1]/cov_m[1,1] if cov_m[1,1] != 0 else 1.0
                    spread = pa[-n:] - hr * pb[-n:]
                    s30 = spread[-30:]
                    std = np.std(s30)
                    z = (spread[-1] - np.mean(s30)) / std if std > 0 else 0
                    corr = float(np.corrcoef(pa[-n:], pb[-n:])[0,1])
                    hl = compute_half_life(s30)
                    entr = spread_entropy(s30)
                    score = cointegration_score(corr, hl, entr)
                    sb_upsert("signals", {
                        "symbol": f"{pair['a']}/{pair['b']}",
                        "action": "LONG_SPREAD" if z < -1.5 else "SHORT_SPREAD" if z > 1.5 else "NEUTRAL",
                        "confidence": min(95, int(score)),
                        "reasoning": f"z={z:.2f} hl={hl:.1f}d H={entr:.2f} score={score:.0f}/100 macro={macro.get('cp_sentiment')}",
                        "zscore": round(z, 3), "strategy": "apollo_statarb",
                        "updated_at": datetime.utcnow().isoformat(),
                    })
                    time.sleep(0.3)
                except: pass

            log.info(f"═══ APOLLO CYCLE END | {len(pair_signals)} signals | {active_pairs}/{MAX_PAIRS} pairs ═══")
            if pair_signals: tg(f"📊 Cycle end: {len(pair_signals)} signals | {active_pairs}/{MAX_PAIRS} perechi active")

        except KeyboardInterrupt:
            log.info("APOLLO stopped.")
            break
        except Exception as e:
            log.error(f"APOLLO cycle error: {e}", exc_info=True)

        time.sleep(CYCLE_SECONDS)

if __name__ == "__main__":
    main()
