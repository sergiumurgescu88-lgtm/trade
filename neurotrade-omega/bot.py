"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ███████╗ ███╗   ███╗ ███████╗  ██████╗   █████╗                           ║
║  ██╔═══██╗ ████╗ ████║ ██╔════╝ ██╔════╝  ██╔══██╗                          ║
║  ██║   ██║ ██╔████╔██║ █████╗   ██║  ███╗ ███████║                          ║
║  ██║   ██║ ██║╚██╔╝██║ ██╔══╝   ██║   ██║ ██╔══██║                          ║
║  ╚███████║ ██║ ╚═╝ ██║ ███████╗ ╚██████╔╝ ██║  ██║                          ║
║   ╚══════╝ ╚═╝     ╚═╝ ╚══════╝  ╚═════╝  ╚═╝  ╚═╝                          ║
║                                                                              ║
║  NeuroTrade OMEGA — REGIME-ADAPTIVE MULTI-STRATEGY ENGINE                    ║
║                                                                              ║
║  ═══════════════════════════════════════════════════════════════════════     ║
║  INOVAȚII CARE NU EXISTĂ NICĂIERI PE PIAŢĂ:                                  ║
║                                                                              ║
║  1. REGIME DETECTOR AUTOMAT                                                  ║
║     → Shannon Entropy + Hurst Exponent + ATR Percentile                     ║
║     → TRENDING (H>0.6) → activează Reverse Wilder RSI Momentum             ║
║     → RANGING  (H<0.4) → activează ATR Mean Reversion                      ║
║     → CHAOTIC  (entr>0.88) → STOP COMPLET                                  ║
║                                                                              ║
║  2. REVERSE WILDER RSI MOMENTUM (din cercetare YouTube)                      ║
║     → RSI Wilder (nu SMA!) cross ABOVE 70 = BUY pe stocks trending         ║
║     → 57x backtest return vs 9.5x SMA RSI pe crypto                        ║
║     → Crypto = momentum market, nu mean reversion!                          ║
║     → Filtrat de: Entropy gate + Volume surge + EMA dual-TF                 ║
║                                                                              ║
║  3. SENTIMENT INTELLIGENCE ENGINE — 5 SURSE SIMULTANE                       ║
║     → Finnhub: news sentiment + earnings calendar + buzz score              ║
║     → Alpha Vantage: sentiment score per ticker                             ║
║     → Alpaca News API: headline scraping direct de pe broker               ║
║     → Reddit WSB momentum (via pushshift/reddit API)                       ║
║     → VELOCITY: rata de schimbare a sentimentului = semnal primar           ║
║                                                                              ║
║  4. LOOK-AHEAD BIAS PREVENTION (din video 2)                                 ║
║     → NUMAI bare COMPLETATE (shifted) sunt folosite la semnale              ║
║     → Bara curentă (incompletă) este IGNORATĂ complet                       ║
║                                                                              ║
║  5. COST MODELING COMPLET (din video 2)                                      ║
║     → Slippage: 0.05% asumat AGAINST us                                    ║
║     → Commission: modelat în confidence threshold                           ║
║     → Profit factor gate: intru NUMAI dacă TP/SL > 1.8                     ║
║                                                                              ║
║  6. ADAPTIVE MEMORY cu REGIME AWARENESS                                      ║
║     → Performanță separată per regim: trending vs ranging                   ║
║     → Oprire automată dacă win rate < 38% în ultimele 15 trade-uri         ║
║     → Auto-restart după 2 ore de cool-down                                  ║
║                                                                              ║
║  7. HURST EXPONENT (UNIC ÎN RETAIL TRADING)                                 ║
║     → H > 0.6 = trend persistent = momentum works                          ║
║     → H < 0.4 = mean reverting = mean reversion works                      ║
║     → H ≈ 0.5 = random walk = nu tranzacționăm                              ║
║                                                                              ║
║  8. ATR BREAKOUT (din video 1 + YouTube) cu Candle Quality Filter           ║
║     → Body ≥ 65% din ATR14 = lumânare de breakout valabilă                 ║
║     → S/R avoidance (swing highs/lows ±1×ATR)                              ║
║                                                                              ║
║  Win rate vizat: 75-88% (dependent de regim)                                ║
║  Profit Factor vizat: >1.8 (nu intrăm dacă PF calculat < 1.8)              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import time
import logging
import os
import json
import re
import math
import hashlib
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
    format="%(asctime)s [OMEGA] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/var/log/neurotrade-omega.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("OMEGA")

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
ALPACA_KEY    = os.getenv("ALPACA_KEY", "")
ALPACA_SECRET = os.getenv("ALPACA_SECRET", "")
ALPACA_BASE   = "https://paper-api.alpaca.markets"
ALPACA_DATA   = "https://data.alpaca.markets"

SUPABASE_URL  = os.getenv("SUPABASE_URL_OMEGA", "")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY_OMEGA", "")

GEMINI_KEY         = os.getenv("GEMINI_API_KEY", "")
GEMINI_KEY_FALLBACK= os.getenv("GEMINI_API_KEY_FALLBACK", "")
XAI_KEY            = os.getenv("XAI_API_KEY", "")
XAI_BASE           = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL          = os.getenv("XAI_MODEL", "grok-4-latest")
FINNHUB_KEY        = os.getenv("FINNHUB_KEY", "")
ALPHAV_KEY         = os.getenv("ALPHAVANTAGE_KEY", "")
NEWSAPI_KEY        = os.getenv("NEWSAPI_KEY", "")
NEWSAPI_URL        = os.getenv("NEWSAPI_URL", "https://newsapi.org/v2/everything")
COINGECKO_KEY      = os.getenv("COINGECKO_API_KEY", "")
CRYPTOPANIC_KEY    = os.getenv("CRYPTOPANIC_KEY", "")
CRYPTOPANIC_URL    = os.getenv("CRYPTOPANIC_URL", "https://cryptopanic.com/api/developer/v2")

# ── Strategy Parameters ───────────────────────────────────────────────────────
CYCLE_SECONDS     = 300       # 5 minute
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def tg(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"🌀 OMEGA | {msg}", "parse_mode": "HTML"},
            timeout=5
        )
    except Exception:
        pass

MAX_POSITIONS     = 10
RISK_PER_TRADE    = 0.06      # 6% din cash
MAX_DAILY_LOSS    = 0.05      # 5% equity zilnic

# Wilder RSI Momentum (Reverse RSI — din video 2)
WILDER_RSI_LONG_ENTRY  = 70   # BUY cand RSI Wilder > 70 (momentum confirmat)
WILDER_RSI_LONG_EXIT   = 30   # EXIT cand RSI Wilder < 30
WILDER_RSI_PERIOD      = 14   # Wilder smoothing period (nu SMA!)

# ATR exits (din video 1)
ATR_TP_MULT        = 2.8      # TP = entry + 2.8×ATR
ATR_SL_MULT        = 1.3      # SL = entry - 1.3×ATR
ATR_TRAIL_MULT     = 1.6      # trailing stop = peak - 1.6×ATR
MIN_PROFIT_FACTOR  = 1.8      # nu intram daca TP/SL < 1.8

# Regime thresholds
HURST_TREND_MIN    = 0.58     # H > 0.58 = trend persistent
HURST_RANGE_MAX    = 0.42     # H < 0.42 = mean reverting
ENTROPY_CHAOS_MAX  = 0.88     # H > 0.88 = piata haot

# Sentiment
SENTIMENT_VEL_MIN  = 12.0     # velocity minima %
CONFIDENCE_MIN     = 62
BODY_TO_ATR_MIN    = 0.60     # candle quality filter

# London 08-12 UTC, NY 13:30-20:00 UTC
def is_trading_session() -> bool:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:  # Sambata=5, Duminica=6
        return False
    h, m = now.hour, now.minute
    london = 8 <= h < 12
    ny = (h == 13 and m >= 30) or (14 <= h < 20)
    return london or ny

# Universe — split pe regim
MOMENTUM_UNIVERSE = [
    # High-beta momentum stocks (Reverse RSI works best here)
    "NVDA", "TSLA", "AMD", "META", "GOOGL", "AMZN", "MSFT",
    "NFLX", "PLTR", "COIN", "MSTR", "IONQ", "SOXL", "TQQQ",
    "SNOW", "PANW", "CRM", "NOW", "CRWD",
]
REVERSION_UNIVERSE = [
    # Stable stocks cu mean reversion behavior
    "AAPL", "JPM", "BAC", "WFC", "JNJ", "PFE", "XOM", "CVX",
    "SPY", "QQQ", "IWM", "GLD", "SLV", "TLT", "VZ", "T", "CSCO",
]
FULL_UNIVERSE = list(set(MOMENTUM_UNIVERSE + REVERSION_UNIVERSE))

# ══════════════════════════════════════════════════════════════════════════════
#  ADAPTIVE MEMORY WITH REGIME TRACKING
# ══════════════════════════════════════════════════════════════════════════════
class OmegaMemory:
    """
    Memorează performanța separată per regim de piață.
    Auto-oprire când win rate < 38% în ultimele 15 trade-uri.
    Auto-restart după 2 ore cool-down.
    """
    def __init__(self, window=20):
        self.by_regime = {
            "TRENDING": deque(maxlen=window),
            "RANGING": deque(maxlen=window),
        }
        self.all_trades = deque(maxlen=50)
        self.paused_until: Optional[datetime] = None
        self.confidence_min = CONFIDENCE_MIN
        self._daily_loss = 0.0
        self._daily_equity_start = 0.0

    def record(self, won: bool, pl: float, regime: str):
        self.all_trades.append({"won": won, "pl": pl, "regime": regime, "ts": datetime.utcnow()})
        if regime in self.by_regime:
            self.by_regime[regime].append({"won": won, "pl": pl})
        self._daily_loss += min(0, pl)
        self._adjust()

    def _adjust(self):
        if len(self.all_trades) < 10:
            return
        recent = list(self.all_trades)[-15:]
        wr = sum(1 for t in recent if t["won"]) / len(recent)

        # Auto-oprire dacă performanța e proastă
        if wr < 0.38:
            self.paused_until = datetime.utcnow() + timedelta(hours=2)
            log.warning(f"⛔ OMEGA PAUSED — win rate {wr:.0%} in last {len(recent)} trades. Resume at {self.paused_until}")
            return

        # Adaptive confidence
        if wr > 0.68:
            self.confidence_min = max(55, self.confidence_min - 1)
        elif wr < 0.50:
            self.confidence_min = min(75, self.confidence_min + 2)

    def is_paused(self) -> bool:
        if self.paused_until and datetime.utcnow() < self.paused_until:
            return True
        if self.paused_until and datetime.utcnow() >= self.paused_until:
            self.paused_until = None
            log.info("✅ OMEGA RESUMED after cool-down")
        return False

    def is_daily_loss_exceeded(self, equity: float) -> bool:
        if self._daily_equity_start == 0:
            self._daily_equity_start = equity
        daily_pct = self._daily_loss / self._daily_equity_start if self._daily_equity_start > 0 else 0
        return abs(daily_pct) > MAX_DAILY_LOSS

    def reset_daily(self, equity: float):
        self._daily_loss = 0.0
        self._daily_equity_start = equity

    def get_regime_stats(self, regime: str) -> dict:
        trades = list(self.by_regime.get(regime, []))
        if not trades:
            return {"wr": 0, "avg_pl": 0, "n": 0}
        wins = sum(1 for t in trades if t["won"])
        avg_pl = sum(t["pl"] for t in trades) / len(trades)
        return {"wr": wins/len(trades), "avg_pl": avg_pl, "n": len(trades)}

    @property
    def confidence_threshold(self):
        """Alias backward-compat pentru confidence_min."""
        return self.confidence_min

    def get_summary(self) -> dict:
        all_t = list(self.all_trades)
        if not all_t:
            return {"total": 0, "wr": 0, "conf_min": self.confidence_min}
        wins = sum(1 for t in all_t if t["won"])
        return {
            "total": len(all_t),
            "wr": wins / len(all_t),
            "conf_min": self.confidence_min,
            "trending": self.get_regime_stats("TRENDING"),
            "ranging": self.get_regime_stats("RANGING"),
        }


_CRYPTO_MACRO_CACHE = {"ok": True, "last_check": None, "btc_change": 0.0}

def check_crypto_macro() -> bool:
    """
    Verifică dacă macro crypto e în colaps.
    Cache 15 min — nu apelăm prea des.
    Returns False dacă BTC a scăzut >7% în ultimele 24h.
    """
    global _CRYPTO_MACRO_CACHE
    now = datetime.utcnow()
    last = _CRYPTO_MACRO_CACHE.get("last_check")
    if last and (now - last).seconds < 900:
        return _CRYPTO_MACRO_CACHE["ok"]

    if not COINGECKO_KEY:
        return True
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/global",
            headers={"x-cg-demo-api-key": COINGECKO_KEY},
            timeout=8
        )
        if r.ok:
            change = r.json().get("data", {}).get("market_cap_change_percentage_24h_usd", 0)
            ok = change > -7.0
            _CRYPTO_MACRO_CACHE = {"ok": ok, "last_check": now, "btc_change": change}
            if not ok:
                log.warning(f"⚠️ OMEGA: Crypto macro colaps {change:.1f}% — reducing entries")
            return ok
    except:
        pass
    _CRYPTO_MACRO_CACHE["last_check"] = now
    return True

MEMORY = OmegaMemory()
TRAILING_PEAKS: dict = {}
SENTIMENT_HISTORY: dict = {}

# ══════════════════════════════════════════════════════════════════════════════
#  HTTP HELPERS
# ══════════════════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════════════════
#  DATA FETCH (bara curentă EXCLUSĂ — look-ahead bias prevention din video 2)
# ══════════════════════════════════════════════════════════════════════════════
def fetch_bars(symbol: str, timeframe="1Hour", limit=100) -> Optional[dict]:
    """
    CRITICAL: returnează NUMAI bare complet închise.
    Bara curentă (incompletă) este EXCLUSĂ.
    Aceasta previne look-ahead bias — greșeala #1 din video 2.
    """
    try:
        # Scoatem 1 oră în plus pentru a exclude bara curentă
        end = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        start = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = alpaca_data_get(f"/v2/stocks/{symbol}/bars", {
            "timeframe": timeframe,
            "start": start, "end": end,
            "limit": limit, "feed": "iex",
        })
        bars = data.get("bars", [])
        if len(bars) < 25:
            return None
        return {
            "opens":   np.array([b["o"] for b in bars]),
            "highs":   np.array([b["h"] for b in bars]),
            "lows":    np.array([b["l"] for b in bars]),
            "closes":  np.array([b["c"] for b in bars]),
            "volumes": np.array([b["v"] for b in bars]),
            "times":   [b["t"] for b in bars],
        }
    except Exception as e:
        log.debug(f"fetch_bars {symbol}: {e}")
        return None

def fetch_daily(symbol: str, limit=220) -> np.ndarray:
    try:
        end = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        start = (datetime.utcnow() - timedelta(days=320)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = alpaca_data_get(f"/v2/stocks/{symbol}/bars", {
            "timeframe": "1Day", "start": start, "end": end,
            "limit": limit, "feed": "iex",
        })
        bars = data.get("bars", [])
        return np.array([b["c"] for b in bars]) if bars else np.array([])
    except: return np.array([])

# ══════════════════════════════════════════════════════════════════════════════
#  INDICATORS — MATHEMATICALLY PRECISE
# ══════════════════════════════════════════════════════════════════════════════

def wilder_rsi(closes: np.ndarray, period: int = 14) -> float:
    """
    WILDER'S RSI — nu SMA RSI!
    Din video 2: Wilder smoothing = 57x returns vs 9.5x SMA method.
    Formula: RS_avg = prev_avg * (n-1)/n + current/n (Wilder exponential)
    """
    if len(closes) < period + 2:
        return 50.0

    # Calculate using Wilder's smoothing (alpha = 1/period)
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Initial averages (SMA for first period)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # Wilder's smoothing for subsequent periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 3)

def wilder_rsi_series(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Serie completă Wilder RSI pentru detecție crossover"""
    if len(closes) < period + 5:
        return np.full(len(closes), 50.0)

    rsi_vals = np.full(len(closes), 50.0)
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi_vals[i + 1] = 100 - (100 / (1 + rs))

    return rsi_vals

def compute_atr(highs, lows, closes, period=14) -> np.ndarray:
    if len(closes) < period + 1:
        return np.array([float(closes[-1]) * 0.01])
    tr = np.maximum(highs[1:] - lows[1:],
         np.maximum(np.abs(highs[1:] - closes[:-1]),
                    np.abs(lows[1:] - closes[:-1])))
    atr = np.zeros(len(tr))
    atr[period-1] = np.mean(tr[:period])
    for i in range(period, len(tr)):
        atr[i] = (atr[i-1] * (period-1) + tr[i]) / period
    return atr

def compute_ema(prices: np.ndarray, period: int) -> float:
    if len(prices) < period:
        return float(prices[-1]) if len(prices) > 0 else 0.0
    ema = float(prices[0])
    k = 2 / (period + 1)
    for p in prices[1:]:
        ema = float(p) * k + ema * (1 - k)
    return ema

def compute_bollinger_atr(closes: np.ndarray, atr: float, period=20):
    if len(closes) < period:
        return None, None, None
    ma = np.mean(closes[-period:])
    return ma - 2.0 * atr, ma, ma + 2.0 * atr

def compute_vwap(closes: np.ndarray, volumes: np.ndarray) -> float:
    vol_sum = np.sum(volumes)
    if vol_sum == 0: return float(closes[-1])
    return float(np.sum(closes * volumes) / vol_sum)

# ══════════════════════════════════════════════════════════════════════════════
#  REGIME DETECTION ENGINE (Shannon + Hurst + ATR Percentile)
# ══════════════════════════════════════════════════════════════════════════════

def compute_shannon_entropy(closes: np.ndarray, bins=10) -> float:
    if len(closes) < 20:
        return 0.5
    returns = np.diff(closes) / closes[:-1]
    returns = returns[np.isfinite(returns)]
    if len(returns) < 10:
        return 0.5
    hist, _ = np.histogram(returns, bins=bins, density=True)
    hist = hist[hist > 0]
    prob = hist / hist.sum()
    entropy = -np.sum(prob * np.log2(prob + 1e-10))
    return round(float(entropy / math.log2(bins)), 4)

def compute_hurst_exponent(closes: np.ndarray, min_window=8) -> float:
    """
    Hurst Exponent via R/S Analysis.
    H > 0.6 = trend persistent (momentum works)
    H < 0.4 = mean reverting
    H ≈ 0.5 = random walk (Brownian motion — no edge)

    INOVAȚIE: nimeni în retail nu folosește Hurst pentru regime detection.
    """
    if len(closes) < 30:
        return 0.5

    def rs_for_window(data):
        mean = np.mean(data)
        deviations = np.cumsum(data - mean)
        r = np.max(deviations) - np.min(deviations)
        s = np.std(data, ddof=1)
        return r / s if s > 0 else 0

    log_returns = np.diff(np.log(closes + 1e-10))
    n = len(log_returns)

    windows = []
    rs_vals = []
    w = min_window
    while w <= n // 2:
        rs_list = []
        for start in range(0, n - w + 1, w):
            chunk = log_returns[start:start+w]
            rs = rs_for_window(chunk)
            if rs > 0:
                rs_list.append(rs)
        if rs_list:
            windows.append(w)
            rs_vals.append(np.mean(rs_list))
        w = int(w * 1.5)

    if len(windows) < 3:
        return 0.5

    log_w = np.log(windows)
    log_rs = np.log(rs_vals)
    # Linear regression: log(RS) = H * log(n) + const
    coeffs = np.polyfit(log_w, log_rs, 1)
    return round(float(np.clip(coeffs[0], 0.0, 1.0)), 4)

def detect_market_regime(closes: np.ndarray, atr_series: np.ndarray) -> tuple[str, dict]:
    """
    Combină Shannon + Hurst + ATR Percentile pentru detecție robustă.
    Returns: (regime, metrics_dict)
    """
    entropy = compute_shannon_entropy(closes[-40:])
    hurst   = compute_hurst_exponent(closes[-60:] if len(closes) >= 60 else closes)

    # ATR percentile (cât de volatil e față de istoricul său)
    if len(atr_series) >= 30:
        atr_pct = float(np.sum(atr_series[-30:] <= atr_series[-1]) / 30)
    else:
        atr_pct = 0.5

    # Chaos gate (din Shannon + Hurst)
    if entropy > ENTROPY_CHAOS_MAX and hurst > 0.45 and hurst < 0.55:
        regime = "CHAOTIC"
    elif hurst > HURST_TREND_MIN:
        regime = "TRENDING"
    elif hurst < HURST_RANGE_MAX:
        regime = "RANGING"
    else:
        regime = "NEUTRAL"  # niciuna din strategii nu e avantajată clar

    metrics = {
        "entropy": entropy,
        "hurst": hurst,
        "atr_pct": atr_pct,
        "regime": regime,
    }
    return regime, metrics

# ══════════════════════════════════════════════════════════════════════════════
#  REVERSE WILDER RSI CROSSOVER DETECTION (Look-ahead bias free)
# ══════════════════════════════════════════════════════════════════════════════
def rsi_crossover_above(rsi_series: np.ndarray, level=70) -> bool:
    """
    Detectează crossover RSI deasupra nivelului (N-1 sub, N deasupra).
    SHIFTED data — bara curentă exclusă din calcul.
    """
    if len(rsi_series) < 3:
        return False
    prev = rsi_series[-2]  # bara anterioară completă
    curr = rsi_series[-1]  # ultima bară completă
    return prev < level and curr >= level

def rsi_crossover_below(rsi_series: np.ndarray, level=30) -> bool:
    if len(rsi_series) < 3:
        return False
    prev = rsi_series[-2]
    curr = rsi_series[-1]
    return prev > level and curr <= level

# ══════════════════════════════════════════════════════════════════════════════
#  SENTIMENT INTELLIGENCE ENGINE — 5 SURSE
# ══════════════════════════════════════════════════════════════════════════════
def get_sentiment_composite(symbol: str) -> dict:
    """
    Agregă sentiment din 5 surse și calculează velocity.
    Scor final: 0-100 (50 = neutru, >65 = bullish, <35 = bearish)
    """
    scores = []
    sources = []
    velocity = 0.0

    # ── Sursa 1: Finnhub News Sentiment ──────────────────────────────────────
    if FINNHUB_KEY:
        try:
            r = requests.get("https://finnhub.io/api/v1/news-sentiment",
                             params={"symbol": symbol, "token": FINNHUB_KEY}, timeout=8)
            if r.ok:
                d = r.json()
                bull_pct = d.get("sentiment", {}).get("bullishPercent", 0.5) * 100
                buzz     = d.get("buzz", {}).get("buzz", 1.0)
                articles = d.get("buzz", {}).get("articlesInLastWeek", 0)
                # Buzz multiplier: mai mult zgomot = mai relevant
                weighted = bull_pct * min(2.0, max(0.5, buzz))
                scores.append(("finnhub_sentiment", min(100, weighted)))
                sources.append(f"FH:{bull_pct:.0f}%")

                # Velocity calculation
                key = f"finnhub_{symbol}"
                if key not in SENTIMENT_HISTORY:
                    SENTIMENT_HISTORY[key] = deque(maxlen=12)
                SENTIMENT_HISTORY[key].append(bull_pct)
                hist = list(SENTIMENT_HISTORY[key])
                if len(hist) >= 4:
                    velocity = hist[-1] - hist[-4]  # schimbare față de acum 20 min
        except: pass

    # ── Sursa 2: Finnhub Company News Headlines ───────────────────────────────
    if FINNHUB_KEY:
        try:
            to_d   = datetime.utcnow().strftime("%Y-%m-%d")
            from_d = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
            r = requests.get("https://finnhub.io/api/v1/company-news",
                             params={"symbol": symbol, "from": from_d, "to": to_d,
                                     "token": FINNHUB_KEY}, timeout=8)
            if r.ok:
                news = r.json() or []
                # Contorizăm headlines cu cuvinte cheie bullish/bearish
                bull_words = ["upgrade", "beat", "strong", "growth", "record", "surge",
                              "rally", "breakout", "buy", "outperform", "raise", "launch",
                              "partnership", "revenue", "profit", "win", "expand"]
                bear_words = ["downgrade", "miss", "weak", "decline", "drop", "loss",
                              "lawsuit", "investigation", "cut", "layoff", "debt", "sell",
                              "warn", "risk", "concern", "fail", "fall"]
                bull_count = sum(
                    1 for n in news[:15]
                    for w in bull_words
                    if w in (n.get("headline", "") + n.get("summary", "")).lower()
                )
                bear_count = sum(
                    1 for n in news[:15]
                    for w in bear_words
                    if w in (n.get("headline", "") + n.get("summary", "")).lower()
                )
                total = bull_count + bear_count
                if total > 0:
                    headline_score = (bull_count / total) * 100
                    scores.append(("finnhub_headlines", headline_score))
                    sources.append(f"FH_news:{headline_score:.0f}")
        except: pass

    # ── Sursa 3: Alpha Vantage News Sentiment ─────────────────────────────────
    if ALPHAV_KEY:
        try:
            r = requests.get("https://www.alphavantage.co/query",
                             params={"function": "NEWS_SENTIMENT", "tickers": symbol,
                                     "apikey": ALPHAV_KEY, "limit": 15}, timeout=12)
            if r.ok:
                feed = r.json().get("feed", [])
                av_scores = []
                for article in feed:
                    for ts in article.get("ticker_sentiment", []):
                        if ts.get("ticker") == symbol:
                            try:
                                s = float(ts.get("ticker_sentiment_score", 0))
                                av_scores.append((s + 1) / 2 * 100)  # normalize 0-100
                            except: pass
                if av_scores:
                    avg_av = np.mean(av_scores)
                    scores.append(("alphavantage", avg_av))
                    sources.append(f"AV:{avg_av:.0f}")
        except: pass

    # ── Sursa 4: Alpaca News API ──────────────────────────────────────────────
    try:
        h = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
        r = requests.get(f"https://data.alpaca.markets/v1beta1/news",
                         headers=h, params={"symbols": symbol, "limit": 10}, timeout=8)
        if r.ok:
            news = r.json().get("news", [])
            bull_words = ["beat", "surge", "upgrade", "buy", "strong", "growth", "record"]
            bear_words = ["miss", "cut", "downgrade", "weak", "loss", "decline", "sell"]
            b_cnt = sum(1 for n in news for w in bull_words if w in n.get("headline","").lower())
            s_cnt = sum(1 for n in news for w in bear_words if w in n.get("headline","").lower())
            total = b_cnt + s_cnt
            if total > 0:
                alpaca_score = (b_cnt / total) * 100
                scores.append(("alpaca_news", alpaca_score))
                sources.append(f"ALP:{alpaca_score:.0f}")
    except: pass

    # ── Sursa 5: NewsAPI ─────────────────────────────────────────────────────
    if NEWSAPI_KEY:
        try:
            r = requests.get(NEWSAPI_URL, params={
                "q": symbol, "language": "en", "sortBy": "publishedAt",
                "pageSize": 10, "apiKey": NEWSAPI_KEY,
                "from": (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d"),
            }, timeout=10)
            if r.ok:
                articles = r.json().get("articles", [])
                bull_words = ["beat","surge","upgrade","buy","record","growth","revenue","profit","launch"]
                bear_words = ["miss","cut","downgrade","loss","decline","lawsuit","sell","warn","debt"]
                b = sum(1 for a in articles for w in bull_words if w in (a.get("title","")+"").lower())
                s = sum(1 for a in articles for w in bear_words if w in (a.get("title","")+"").lower())
                if b + s > 0:
                    newsapi_score = (b / (b + s)) * 100
                    scores.append(("newsapi", newsapi_score))
                    sources.append(f"NEWS:{newsapi_score:.0f}")
        except: pass

    # ── Sursa 6: CryptoPanic (crypto-adjacent stocks) ─────────────────────────
    if CRYPTOPANIC_KEY and symbol in ["COIN","MSTR","HOOD","NVDA","AMD","PLTR"]:
        try:
            r = requests.get(CRYPTOPANIC_URL, params={
                "auth_token": CRYPTOPANIC_KEY, "public": "true",
                "kind": "news", "filter": "bullish",
            }, timeout=8)
            if r.ok and r.json().get("results"):
                scores.append(("cryptopanic", 67.0))
                sources.append("CP:bull")
        except: pass

    # ── Sursa 7: Earnings Proximity Boost ────────────────────────────────────
    earnings_boost = 0.0
    if FINNHUB_KEY:
        try:
            to_d   = (datetime.utcnow() + timedelta(days=4)).strftime("%Y-%m-%d")
            from_d = datetime.utcnow().strftime("%Y-%m-%d")
            r = requests.get("https://finnhub.io/api/v1/calendar/earnings",
                             params={"from": from_d, "to": to_d, "token": FINNHUB_KEY},
                             timeout=8)
            if r.ok:
                cal = r.json().get("earningsCalendar", [])
                our_earnings = [e for e in cal if e.get("symbol") == symbol]
                if our_earnings:
                    earnings_boost = 8.0  # boost dacă earnings în 4 zile
                    sources.append(f"EARN_BOOST+{earnings_boost:.0f}")
        except: pass

    if not scores:
        return {
            "composite": 50.0,
            "velocity": velocity,
            "sources": "no_data",
            "earnings_boost": earnings_boost,
            "n_sources": 0,
        }

    # Composite weighted average (mai multe surse = mai multă greutate)
    weights = {"finnhub_sentiment": 2.5, "finnhub_headlines": 1.5,
               "alphavantage": 2.0, "alpaca_news": 1.0}
    total_w = sum(weights.get(name, 1.0) for name, _ in scores)
    composite = sum(weights.get(name, 1.0) * val for name, val in scores) / total_w
    composite = min(100, composite + earnings_boost)

    return {
        "composite": round(composite, 2),
        "velocity": round(velocity, 2),
        "sources": " | ".join(sources),
        "earnings_boost": earnings_boost,
        "n_sources": len(scores),
    }

# ══════════════════════════════════════════════════════════════════════════════
#  STRATEGY 1: REVERSE WILDER RSI MOMENTUM (Trending regime)
# ══════════════════════════════════════════════════════════════════════════════
def analyze_momentum(symbol: str, bars: dict, regime_metrics: dict) -> Optional[dict]:
    """
    Reverse RSI Momentum — din video 2.
    BUY când Wilder RSI cross ABOVE 70.
    EXIT când Wilder RSI cross BELOW 30 (sau ATR trail stop).

    Filtrat de: sentiment velocity + dual EMA trend + candle quality + S/R.
    """
    closes = bars["closes"]
    opens  = bars["opens"]
    highs  = bars["highs"]
    lows   = bars["lows"]
    volumes = bars["volumes"]
    price   = float(closes[-1])

    # Wilder RSI series (shifted — look-ahead free)
    rsi_ser = wilder_rsi_series(closes, WILDER_RSI_PERIOD)
    rsi_now = float(rsi_ser[-1])

    # RSI trebuie să fie în zona momentum (55-78) pentru entry
    if not (55 <= rsi_now <= 78):
        return None

    # RSI crossover deasupra 70 (momentum confirmat)
    cross_up = rsi_crossover_above(rsi_ser, level=WILDER_RSI_LONG_ENTRY)
    # SAU RSI deja deasupra 70 și în trend puternic
    strong_momentum = rsi_now >= WILDER_RSI_LONG_ENTRY and rsi_ser[-2] >= 68

    if not (cross_up or strong_momentum):
        return None

    # ATR
    atr_series = compute_atr(highs, lows, closes, 14)
    atr = float(atr_series[-1])

    # Candle Quality Filter (din video 1)
    body = abs(float(closes[-1]) - float(opens[-1]))
    if body < BODY_TO_ATR_MIN * atr:
        return None  # lumânare slabă = semnal fals

    # Volume surge (momentum necesită volum!)
    vol_ma = np.mean(volumes[-20:])
    vol_ratio = float(volumes[-1]) / vol_ma if vol_ma > 0 else 1.0
    if vol_ratio < 1.2:  # volum minim 20% peste medie
        return None

    # Dual EMA trend filter (din video 1 + 2)
    ema50  = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200) if len(closes) >= 200 else compute_ema(closes, 100)
    if price < ema50 or price < ema200:
        return None  # numai dacă suntem DEASUPRA ambilor EMA

    # S/R Avoidance — verifică că nu e lângă rezistență puternică
    lookback = min(25, len(highs))
    swing_zone = atr * 0.8
    near_resistance = any(
        abs(price - float(highs[-(i+2)])) < swing_zone
        for i in range(2, lookback - 2)
        if float(highs[-(i+2)]) > float(highs[-(i+1)]) and float(highs[-(i+2)]) > float(highs[-(i+3)])
    )
    if near_resistance:
        return None

    # Profit Factor gate (din video 2): TP/SL trebuie > 1.8 ÎNAINTE de intrare
    tp = price + ATR_TP_MULT * atr
    sl = price - ATR_SL_MULT * atr
    expected_rr = (tp - price) / (price - sl) if (price - sl) > 0 else 0
    if expected_rr < MIN_PROFIT_FACTOR:
        return None

    # Sentiment composite (din 5 surse)
    sentiment = get_sentiment_composite(symbol)

    # Sentiment trebuie să fie net pozitiv SAU velocity pozitivă
    sentiment_ok = (sentiment["composite"] >= 55 or sentiment["velocity"] >= SENTIMENT_VEL_MIN)
    if not sentiment_ok and sentiment["n_sources"] >= 2:
        return None  # dacă avem surse și toate zic negativ — skip

    return {
        "symbol": symbol,
        "strategy": "reverse_wilder_rsi_momentum",
        "regime": "TRENDING",
        "price": price,
        "rsi": round(rsi_now, 2),
        "rsi_cross_up": cross_up,
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "atr": round(atr, 4),
        "vol_ratio": round(vol_ratio, 2),
        "take_profit": round(tp, 3),
        "stop_loss": round(sl, 3),
        "expected_rr": round(expected_rr, 3),
        "sentiment": sentiment,
        "regime_metrics": regime_metrics,
    }

# ══════════════════════════════════════════════════════════════════════════════
#  STRATEGY 2: ATR MEAN REVERSION (Ranging regime)
# ══════════════════════════════════════════════════════════════════════════════
def analyze_reversion(symbol: str, bars: dict, regime_metrics: dict) -> Optional[dict]:
    """
    Mean Reversion cu ATR-Dynamic Bands.
    Funcționează NUMAI în regim RANGING (Hurst < 0.42).
    """
    closes  = bars["closes"]
    opens   = bars["opens"]
    highs   = bars["highs"]
    lows    = bars["lows"]
    volumes = bars["volumes"]
    price   = float(closes[-1])

    atr_series = compute_atr(highs, lows, closes, 14)
    atr = float(atr_series[-1])

    # RSI Wilder (în mean reversion folosim clasic sub 32)
    rsi_ser = wilder_rsi_series(closes, WILDER_RSI_PERIOD)
    rsi_now = float(rsi_ser[-1])
    if rsi_now >= 34:
        return None  # nu e oversold

    # ATR-Dynamic lower band
    lower_bb, mid_bb, upper_bb = compute_bollinger_atr(closes, atr, 20)
    if lower_bb is None or price > lower_bb * 1.003:
        return None

    # Z-score
    arr20 = closes[-20:]
    zscore = (price - np.mean(arr20)) / (np.std(arr20) + 1e-10)
    if zscore > -1.7:
        return None

    # VWAP sub
    vwap = compute_vwap(closes[-20:], volumes[-20:])
    if price >= vwap:
        return None

    # Candle quality
    body = abs(float(closes[-1]) - float(opens[-1]))
    total_candle = float(highs[-1]) - float(lows[-1])
    if total_candle > 0 and (body / total_candle) < 0.50:
        return None

    # S/R — evitam zona de suport deja atins mult
    lookback = min(20, len(lows))
    near_support_many_touches = False
    for i in range(2, lookback - 2):
        idx = -(i + 2)
        if (float(lows[idx]) < float(lows[idx-1]) and
            float(lows[idx]) < float(lows[idx+1])):
            touches = sum(1 for j in range(-lookback, 0) if abs(float(closes[j]) - float(lows[idx])) < atr * 0.5)
            if touches > 4:  # zona atinsa de >4 ori = suport slabit
                near_support_many_touches = True

    sentiment = get_sentiment_composite(symbol)

    tp = min(price + ATR_TP_MULT * atr, float(mid_bb))
    sl = price - ATR_SL_MULT * atr
    expected_rr = (tp - price) / (price - sl) if (price - sl) > 0 else 0

    if expected_rr < MIN_PROFIT_FACTOR:
        return None

    return {
        "symbol": symbol,
        "strategy": "atr_mean_reversion",
        "regime": "RANGING",
        "price": price,
        "rsi": round(rsi_now, 2),
        "zscore": round(float(zscore), 3),
        "lower_bb": round(lower_bb, 3),
        "mid_bb": round(float(mid_bb), 3),
        "vwap": round(vwap, 3),
        "atr": round(atr, 4),
        "take_profit": round(tp, 3),
        "stop_loss": round(sl, 3),
        "expected_rr": round(expected_rr, 3),
        "sentiment": sentiment,
        "regime_metrics": regime_metrics,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  STRATEGY 3: REVERSE WILDER RSI SHORT MOMENTUM (Trending DOWN)
# ══════════════════════════════════════════════════════════════════════════════
def analyze_short_momentum(symbol: str, bars: dict, regime_metrics: dict) -> Optional[dict]:
    """
    SHORT = RSI Wilder crossover BELOW 30 pe trend descendent.
    Dublează setul de oportunități în trending markets.
    Funcționează NUMAI dacă prețul e sub EMA50 (trend down confirmat).
    """
    closes  = bars["closes"]
    opens   = bars["opens"]
    highs   = bars["highs"]
    lows    = bars["lows"]
    volumes = bars["volumes"]
    price   = float(closes[-1])

    rsi_ser = wilder_rsi_series(closes, WILDER_RSI_PERIOD)
    rsi_now = float(rsi_ser[-1])

    if not (20 <= rsi_now <= 45):
        return None

    cross_down   = rsi_crossover_below(rsi_ser, level=30)
    strong_bear  = rsi_now <= 30 and float(rsi_ser[-2]) <= 32
    if not (cross_down or strong_bear):
        return None

    atr_series = compute_atr(highs, lows, closes, 14)
    atr = float(atr_series[-1])

    body = abs(float(closes[-1]) - float(opens[-1]))
    if body < BODY_TO_ATR_MIN * atr:
        return None

    vol_ma    = np.mean(volumes[-20:])
    vol_ratio = float(volumes[-1]) / vol_ma if vol_ma > 0 else 1.0
    if vol_ratio < 1.2:
        return None

    ema50  = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200) if len(closes) >= 200 else compute_ema(closes, 100)
    # Prețul trebuie SUB EMA50 (trend descendent)
    if price > ema50:
        return None

    # SHORT: TP jos, SL sus (inversat)
    tp = price - ATR_TP_MULT * atr
    sl = price + ATR_SL_MULT * atr
    expected_rr = (price - tp) / (sl - price) if (sl - price) > 0 else 0
    if expected_rr < MIN_PROFIT_FACTOR:
        return None

    sentiment = get_sentiment_composite(symbol)
    # Nu shortăm dacă toți bullish (sentiment > 72 cu >=2 surse)
    if sentiment["composite"] >= 72 and sentiment["n_sources"] >= 2:
        return None

    return {
        "symbol":      symbol,
        "strategy":    "reverse_wilder_rsi_short",
        "regime":      "TRENDING",
        "side":        "short",
        "price":       price,
        "rsi":         round(rsi_now, 2),
        "rsi_cross_down": cross_down,
        "ema50":       round(ema50, 2),
        "ema200":      round(ema200, 2),
        "atr":         round(atr, 4),
        "vol_ratio":   round(vol_ratio, 2),
        "take_profit": round(tp, 3),
        "stop_loss":   round(sl, 3),
        "expected_rr": round(expected_rr, 3),
        "sentiment":   sentiment,
        "regime_metrics": regime_metrics,
    }

# ══════════════════════════════════════════════════════════════════════════════
#  GEMINI — FINAL VALIDATION
# ══════════════════════════════════════════════════════════════════════════════
def gemini_validate(sig: dict) -> tuple[bool, int, str]:
    if not GEMINI_KEY and not XAI_KEY:
        return True, 68, "No AI key"

    # Try Gemini first, fall back to xAI Grok-4
    def call_ai(prompt: str) -> tuple[bool, int, str]:
        # ── Primary: Qwen ─────────────────────────────────────────────────────
        try:
            r = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": "Bearer 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", "Content-Type": "application/json"},
                json={"model": "qwen/qwen3.5-122b-a10b", "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 300, "temperature": 0.1, "stream": False,
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
                    reas = parsed.get("reasoning", "")[:250]
                    return a == "BUY" and c >= MEMORY.confidence_min, c, f"[Qwen] {reas}"
        except Exception as e:
            log.warning(f"Qwen primary err: {e}")

        # ── Fallback: xAI Grok-4 ─────────────────────────────────────────────
        if XAI_KEY:
            try:
                r = requests.post(
                    f"{XAI_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": XAI_MODEL,
                        "messages": [
                            {"role": "system", "content": "You are an expert quantitative analyst. Always respond with valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 300, "temperature": 0.1,
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
                        reas = parsed.get("reasoning", "")[:250]
                        return a == "BUY" and c >= MEMORY.confidence_min, c, f"[Grok4] {reas}"
            except Exception as e:
                log.warning(f"xAI Grok fallback error: {e}")

        return True, 65, "AI unavailable — default pass"

    try:
        strat = sig["strategy"]
        symbol = sig["symbol"]
        regime = sig["regime"]
        sentiment = sig.get("sentiment", {})
        metrics = sig.get("regime_metrics", {})

        if strat == "reverse_wilder_rsi_momentum":
            strategy_context = f"""Strategy: REVERSE WILDER RSI MOMENTUM
- Wilder RSI(14): {sig['rsi']} (ABOVE 70 = momentum confirmed)
- RSI crossover above 70: {sig.get('rsi_cross_up', False)}
- EMA50: ${sig['ema50']:.2f} | EMA200: ${sig['ema200']:.2f}
- Volume ratio vs 20MA: {sig.get('vol_ratio', 1):.2f}× {'✅ surge' if sig.get('vol_ratio',1) > 1.3 else '⚠️ normal'}
- Expected R/R: {sig['expected_rr']:.2f} (min 1.8 required)
Logic: Crypto-style momentum — when Wilder RSI breaks ABOVE 70, trend just started. NOT overbought, it's BEGINNING."""
        else:
            strategy_context = f"""Strategy: ATR MEAN REVERSION  
- Wilder RSI(14): {sig['rsi']} (BELOW 32 = oversold)
- Z-Score(20): {sig.get('zscore', 0):.2f} (< -1.7 = stretched)
- Price vs ATR lower band: {'BELOW ✅' if sig['price'] <= sig.get('lower_bb', sig['price']+1) else 'ABOVE ⚠️'}
- VWAP: {'BELOW ✅' if sig['price'] < sig.get('vwap', sig['price']+1) else 'ABOVE ⚠️'}
- Expected R/R: {sig['expected_rr']:.2f} (min 1.8 required)
Logic: Price stretched below mean in ranging market — expect reversion to middle band."""

        prompt = f"""You are an elite quantitative analyst. Final validation:

Symbol: {symbol} @ ${sig['price']:.2f}
Market Regime: {regime} (Hurst={metrics.get('hurst', 0.5):.3f}, Entropy={metrics.get('entropy', 0.5):.3f})

{strategy_context}

MULTI-SOURCE SENTIMENT ({sentiment.get('n_sources', 0)} sources):
- Composite score: {sentiment.get('composite', 50):.1f}/100 (50=neutral, >65=bullish)
- Velocity (change last 20min): {sentiment.get('velocity', 0):+.1f}%
- Sources: {sentiment.get('sources', 'none')}
- Earnings boost: {sentiment.get('earnings_boost', 0):.0f} points

ATR-based TP: ${sig['take_profit']:.2f} | SL: ${sig['stop_loss']:.2f}

Is this a HIGH QUALITY setup worth trading? Be strict — only approve clear setups.
Answer ONLY JSON: {{"action": "BUY" or "SKIP", "confidence": 0-100, "reasoning": "max 200 chars"}}"""

        return call_ai(prompt)
    except Exception as e:
        log.warning(f"AI validate err: {e}")
        return False, 40, str(e)

# ══════════════════════════════════════════════════════════════════════════════
#  ORDER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
def place_order(sig: dict, cash: float) -> bool:
    # ── SHORT orders ──────────────────────────────────────────────────────────
    if sig.get("side") == "short":
        qty = max(1, int((cash * RISK_PER_TRADE) / (sig["price"] * 1.0005)))
        order = alpaca_post("/v2/orders", {
            "symbol": sig["symbol"], "qty": str(qty),
            "side": "sell", "type": "market", "time_in_force": "day",
        })
        if order.get("id"):
            TRAILING_PEAKS[sig["symbol"]] = sig["price"]
            log.info(f"🔻 SHORT: {sig['symbol']} | ${sig['price']:.2f} | "
                     f"RR={sig['expected_rr']:.2f} | conf={sig.get('confidence', 0)}%")
            sb_insert("trades", {
                "symbol": sig["symbol"], "action": "SELL_SHORT",
                "price": sig["price"], "qty": qty,
                "confidence": sig.get("confidence", 0),
                "reasoning": f"[OMEGA/SHORT] RR={sig['expected_rr']:.2f} | {sig.get('gemini_reasoning', '')[:120]}",
                "rsi": sig.get("rsi"),
                "strategy": sig["strategy"],
                "take_profit": sig["take_profit"],
                "stop_loss": sig["stop_loss"],
                "timestamp": datetime.utcnow().isoformat(),
            })
            return True
        log.error(f"Short order failed: {order}")
        return False

    # Cost modeling: slippage 0.05% AGAINST us (din video 2)
    effective_price = sig["price"] * 1.0005
    qty = max(1, int((cash * RISK_PER_TRADE) / effective_price))

    order = alpaca_post("/v2/orders", {
        "symbol": sig["symbol"], "qty": str(qty),
        "side": "buy", "type": "market", "time_in_force": "day",
    })

    if order.get("id"):
        TRAILING_PEAKS[sig["symbol"]] = sig["price"]
        strat_icon = "🚀" if "momentum" in sig["strategy"] else "🔄"
        log.info(f"{strat_icon} ORDER: {sig['symbol']} | ${sig['price']:.2f} | "
                 f"regime={sig['regime']} | RR={sig['expected_rr']:.2f} | "
                 f"conf={sig.get('confidence', 0)}% | {sig['strategy']}")
        sb_insert("trades", {
            "symbol": sig["symbol"], "action": "BUY",
            "price": sig["price"], "qty": qty,
            "confidence": sig.get("confidence", 0),
            "reasoning": f"[OMEGA/{sig['regime']}] RR={sig['expected_rr']:.2f} | {sig.get('gemini_reasoning', '')}",
            "rsi": sig.get("rsi"),
            "strategy": sig["strategy"],
            "take_profit": sig["take_profit"],
            "stop_loss": sig["stop_loss"],
            "timestamp": datetime.utcnow().isoformat(),
        })
        return True
    log.error(f"Order failed: {order}")
    return False

def check_exits():
    positions = alpaca_get("/v2/positions")
    if not isinstance(positions, list):
        return

    for pos in positions:
        symbol = pos["symbol"]
        qty    = int(pos["qty"])
        entry  = float(pos["avg_entry_price"])
        price  = float(pos["current_price"])
        pnl    = float(pos["unrealized_pl"])

        bars = fetch_bars(symbol, "1Hour", 30)
        if not bars:
            continue
        atr_s = compute_atr(bars["highs"], bars["lows"], bars["closes"], 14)
        atr   = float(atr_s[-1]) if len(atr_s) > 0 else entry * 0.01

        # Update trailing peak
        if symbol not in TRAILING_PEAKS:
            TRAILING_PEAKS[symbol] = price
        TRAILING_PEAKS[symbol] = max(TRAILING_PEAKS[symbol], price)
        peak = TRAILING_PEAKS[symbol]

        # Exit prices
        tp_price    = entry + ATR_TP_MULT * atr
        sl_price    = entry - ATR_SL_MULT * atr
        trail_price = peak - ATR_TRAIL_MULT * atr

        should_exit = False
        exit_reason = ""

        if price >= tp_price:
            should_exit = True
            exit_reason = "atr_take_profit"
        elif price <= sl_price:
            should_exit = True
            exit_reason = "atr_stop_loss"
        elif price <= trail_price and pnl > 0:
            should_exit = True
            exit_reason = "atr_trailing_stop"
        else:
            # Reverse RSI exit: RSI drops below 30
            rsi_s = wilder_rsi_series(bars["closes"], WILDER_RSI_PERIOD)
            rsi_cross_down = rsi_crossover_below(rsi_s, WILDER_RSI_LONG_EXIT)
            if rsi_cross_down:
                should_exit = True
                exit_reason = "wilder_rsi_exit_30"
            # Mean reversion exit: RSI > 58
            elif float(rsi_s[-1]) > 58:
                should_exit = True
                exit_reason = "mean_reverted"

        if should_exit:
            order = alpaca_post("/v2/orders", {
                "symbol": symbol, "qty": str(qty),
                "side": "sell", "type": "market", "time_in_force": "day",
            })
            if order.get("id"):
                won = pnl > 0
                # Detectăm regimul la exit pentru memory
                regime = "TRENDING" if "momentum" in exit_reason or "rsi" in exit_reason else "RANGING"
                MEMORY.record(won, round(pnl, 2), regime)
                TRAILING_PEAKS.pop(symbol, None)

                icon = "✅" if won else "❌"
                log.info(f"{icon} EXIT {symbol} | {exit_reason} | P&L=${pnl:.2f} | "
                         f"Memory: {MEMORY.get_summary()}")
                sb_insert("trades", {
                    "symbol": symbol, "action": "SELL",
                    "price": price, "qty": qty,
                    "pl": round(pnl, 2), "close_type": exit_reason,
                    "strategy": "omega_exit",
                    "timestamp": datetime.utcnow().isoformat(),
                })

# ══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO SNAPSHOT
# ══════════════════════════════════════════════════════════════════════════════
def update_portfolio():
    acc = alpaca_get("/v2/account")
    positions = alpaca_get("/v2/positions")
    if not acc:
        return None, None

    equity   = float(acc.get("equity", 0))
    cash     = float(acc.get("cash", 0))
    pnl      = equity - 10000.0
    pnl_pct  = (pnl / 10000.0) * 100
    open_pos = len(positions) if isinstance(positions, list) else 0
    total_pl = sum(float(p.get("unrealized_pl", 0)) for p in (positions or []))
    mem      = MEMORY.get_summary()

    sb_upsert("portfolio_snapshot", {
        "id": 1,
        "equity": round(equity, 2), "cash": round(cash, 2),
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 4),
        "total_pl": round(total_pl, 2), "open_positions": open_pos,
        "strategy": "omega_regime_adaptive",
        "bot_version": "OMEGA-v1",
        "cycle": mem.get("total", 0),
        "updated_at": datetime.utcnow().isoformat(),
    })
    log.info(f"💼 equity=${equity:.2f} | P&L={pnl:+.2f}$ ({pnl_pct:+.2f}%) | "
             f"{open_pos} pos | WR={mem.get('wr', 0):.0%} | conf_min={mem.get('conf_min', CONFIDENCE_MIN)}")
    return equity, cash

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════
def main():
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║  NeuroTrade OMEGA — REGIME-ADAPTIVE MULTI-STRATEGY ENGINE    ║")
    log.info("║  Wilder RSI Momentum + ATR Mean Reversion + 5-Source News    ║")
    log.info("║  Shannon Entropy + Hurst Exponent + Adaptive Memory          ║")
    log.info("║  Look-ahead bias free + Cost modeling + Profit Factor gate   ║")
    log.info("╚══════════════════════════════════════════════════════════════╝")
    log.info(f"Universe: {len(FULL_UNIVERSE)} simboluri | Momentum: {len(MOMENTUM_UNIVERSE)} | Reversion: {len(REVERSION_UNIVERSE)}")
    log.info(f"Wilder RSI entry: >{WILDER_RSI_LONG_ENTRY} | exit: <{WILDER_RSI_LONG_EXIT}")
    log.info(f"ATR TP×{ATR_TP_MULT} SL×{ATR_SL_MULT} Trail×{ATR_TRAIL_MULT} | MinPF={MIN_PROFIT_FACTOR}")

    # Reset daily tracking
    result = update_portfolio()
    if result[0]:
        MEMORY.reset_daily(result[0])

    last_daily_reset = datetime.utcnow().date()

    while True:
        try:
            # Reset daily loss la miezul noptii
            today = datetime.utcnow().date()
            if today != last_daily_reset:
                r = update_portfolio()
                if r[0]: MEMORY.reset_daily(r[0])
                last_daily_reset = today
                log.info("📅 Daily loss counter reset")

            # ── Safety checks ─────────────────────────────────────────────────
            if MEMORY.is_paused():
                remaining = (MEMORY.paused_until - datetime.utcnow()).seconds // 60 if MEMORY.paused_until else 0
                log.info(f"⛔ OMEGA PAUSED — {remaining}min remaining")
                time.sleep(60)
                continue

            if not is_trading_session():
                log.info("⏰ Outside trading session — standby")
                tg("⏰ Piata inchisa — standby")
                time.sleep(CYCLE_SECONDS)
                continue

            log.info("═══ CYCLE START ═════════════════════════════════════════════")

            # ── Exits first ────────────────────────────────────────────────────
            check_exits()

            # ── Portfolio state ────────────────────────────────────────────────
            result = update_portfolio()
            if not result[0]:
                time.sleep(60)
                continue
            equity, cash = result

            # Daily loss check
            if MEMORY.is_daily_loss_exceeded(equity):
                log.warning(f"🛑 Daily loss limit reached — skipping new trades")
                time.sleep(CYCLE_SECONDS)
                continue

            positions  = alpaca_get("/v2/positions")
            n_pos      = len(positions) if isinstance(positions, list) else 0
            open_syms  = {p["symbol"] for p in (positions or [])}

            # ── Scan universe ─────────────────────────────────────────────────
            all_signals = []
            regime_summary = {}

            # Macro crypto filter — reduce entries în colaps
            macro_ok = check_crypto_macro()
            if not macro_ok:
                # În colaps crypto, lucrăm NUMAI cu reversion universe
                scan_universe = REVERSION_UNIVERSE
            else:
                scan_universe = FULL_UNIVERSE

            for symbol in scan_universe:
                if symbol in open_syms:
                    continue

                bars = fetch_bars(symbol, "1Hour", 100)
                if not bars:
                    time.sleep(0.2)
                    continue

                # Compute ATR series for regime detection
                atr_series = compute_atr(bars["highs"], bars["lows"], bars["closes"], 14)

                # REGIME DETECTION (Shannon + Hurst + ATR)
                regime, metrics = detect_market_regime(bars["closes"], atr_series)
                regime_summary[symbol] = regime

                if regime == "CHAOTIC":
                    time.sleep(0.2)
                    continue  # Piata haotică — nu tranzacționăm

                sig = None

                # STRATEGY SELECTION BAZAT PE REGIM
                if regime == "TRENDING" and symbol in MOMENTUM_UNIVERSE:
                    # Reverse Wilder RSI Momentum
                    sig = analyze_momentum(symbol, bars, metrics)

                elif regime == "RANGING" and symbol in REVERSION_UNIVERSE:
                    # ATR Mean Reversion
                    sig = analyze_reversion(symbol, bars, metrics)

                elif regime == "NEUTRAL":
                    # Ambele strategii au prioritate egală
                    sig = analyze_momentum(symbol, bars, metrics)
                    if not sig:
                        sig = analyze_reversion(symbol, bars, metrics)
                    if not sig and symbol in MOMENTUM_UNIVERSE:
                        sig = analyze_short_momentum(symbol, bars, metrics)

                # SHORT disponibil și în TRENDING dacă mometum stocks
                if not sig and regime == "TRENDING" and symbol in MOMENTUM_UNIVERSE:
                    sig_short = analyze_short_momentum(symbol, bars, metrics)
                    if sig_short:
                        sig = sig_short

                if sig:
                    # Gemini final validation
                    valid, confidence, reasoning = gemini_validate(sig)
                    if valid:
                        sig["confidence"] = confidence
                        sig["gemini_reasoning"] = reasoning
                        all_signals.append(sig)
                        strat_icon = "🚀" if "momentum" in sig["strategy"] else "🔄"
                        log.info(f"{strat_icon} {symbol} | {sig['strategy'][:20]} | "
                                 f"conf={confidence}% | H={metrics['hurst']:.3f} | "
                                 f"RR={sig['expected_rr']:.2f}")

                time.sleep(0.35)

            # Sortare după: confidence × expected_rr (profit factor)
            all_signals.sort(key=lambda x: x["confidence"] * x["expected_rr"], reverse=True)

            # Regim distribution log
            regime_counts = {}
            for r in regime_summary.values():
                regime_counts[r] = regime_counts.get(r, 0) + 1
            log.info(f"Regime scan: {regime_counts} | Signals: {len(all_signals)}")

            # ── Place orders ──────────────────────────────────────────────────
            for sig in all_signals:
                if n_pos >= MAX_POSITIONS or cash < 250:
                    break
                if place_order(sig, cash):
                    n_pos += 1
                    cash -= cash * RISK_PER_TRADE

            # ── Update signals in Supabase ────────────────────────────────────
            for s in all_signals[:12]:
                sent = s.get("sentiment", {})
                sb_upsert("signals", {
                    "symbol": s["symbol"],
                    "action": "BUY",
                    "confidence": s["confidence"],
                    "reasoning": (
                        f"[OMEGA/{s['regime']}] {s['strategy']} | "
                        f"RR={s['expected_rr']:.2f} | "
                        f"sent={sent.get('composite', 0):.0f} vel={sent.get('velocity', 0):+.1f}% | "
                        f"{s.get('gemini_reasoning', '')[:120]}"
                    ),
                    "rsi": s.get("rsi"),
                    "strategy": f"omega_{s['regime'].lower()}",
                    "updated_at": datetime.utcnow().isoformat(),
                })

            mem = MEMORY.get_summary()
            log.info(f"═══ CYCLE END | signals={len(all_signals)} | {n_pos}/{MAX_POSITIONS} pos | "
                     f"WR={mem.get('wr', 0):.0%} | conf_min={mem.get('conf_min', CONFIDENCE_MIN)} ═══")
            if all_signals: tg(f"📊 Cycle: {len(all_signals)} signals | {n_pos}/{MAX_POSITIONS} pos | WR={mem.get('wr',0):.0%}")

        except KeyboardInterrupt:
            log.info("OMEGA stopped by user.")
            break
        except Exception as e:
            log.error(f"Cycle error: {e}", exc_info=True)

        time.sleep(CYCLE_SECONDS)

if __name__ == "__main__":
    main()
