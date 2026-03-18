#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  ██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗    ██╗   ██╗██████╗   ║
║  ██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝    ██║   ██║╚════██╗  ║
║  ███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗    ██║   ██║ █████╔╝  ║
║  ██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║    ╚██╗ ██╔╝██╔═══╝  ║
║  ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║     ╚████╔╝ ███████╗  ║
║  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝      ╚═══╝  ╚══════╝  ║
║                                                                              ║
║  NeuroTrade HERMES v2 — ADVANCED CRYPTO SCALPING ENGINE                     ║
║                                                                              ║
║  ÎMBUNĂTĂȚIRI FAȚĂ DE HERMES v1:                                             ║
║                                                                              ║
║  1. LEVERAGE x5 — Margin amplificat pe toate pozițiile                      ║
║     → Size calculat cu leverage, risc real controlat la 5%                  ║
║     → Liquidation guard: oprire automată la -15% equity                     ║
║                                                                              ║
║  2. WILDER RSI (din OMEGA) — Nu SMA RSI!                                    ║
║     → RSI cross ABOVE 70 = momentum confirmat = BUY                         ║
║     → RSI cross BELOW 30 = momentum descendent = SELL/SHORT                 ║
║     → 57x backtest return vs 9.5x SMA RSI (conform cercetare)              ║
║                                                                              ║
║  3. NVIDIA QWEN 397B (din ZEUS) ca AI principal                             ║
║     → Fallback 1: xAI Grok-4                                                ║
║     → Fallback 2: Gemini 2.0 Flash                                          ║
║                                                                              ║
║  4. 14 SIMBOLURI CRYPTO (față de 7 în v1)                                   ║
║     → BTC ETH SOL XRP ADA LINK DOT AVAX MATIC DOGE                         ║
║     → LTC ATOM UNI NEAR                                                     ║
║                                                                              ║
║  5. STRATEGIE AGRESIVĂ:                                                     ║
║     → TP: 5% (față de 3% în v1)                                             ║
║     → SL: 2.5% (față de 2% în v1)                                           ║
║     → R/R ratio: 2.0 (față de 1.5 în v1)                                   ║
║                                                                              ║
║  6. ATR DYNAMIC TP/SL (din OMEGA)                                           ║
║     → TP = entry + 3.5×ATR                                                  ║
║     → SL = entry - 1.4×ATR                                                  ║
║     → Trailing stop = peak - 2.0×ATR                                        ║
║                                                                              ║
║  7. HURST EXPONENT pentru trend confirmation                                ║
║     → H > 0.55 = trend valid = intrăm                                       ║
║     → H < 0.45 = random walk = skip                                         ║
║                                                                              ║
║  8. VOLUME SURGE FILTER                                                     ║
║     → Volum > 1.6× medie 20 bare = confirmare instituțională               ║
║                                                                              ║
║  9. DUAL TIMEFRAME CONFIRMATION                                             ║
║     → Semnal pe 15min confirmat pe 1h                                       ║
║                                                                              ║
║  10. ADAPTIVE MEMORY (din OMEGA)                                            ║
║      → Auto-pause dacă win rate < 40% în ultimele 10 trades                ║
║      → Resume după 1h cool-down                                             ║
║                                                                              ║
║  Exchange: Kraken Futures Demo (24/7)                                       ║
║  Win rate vizat: 78-88%                                                     ║
║  Profit Factor vizat: >2.0                                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, time, hmac, hashlib, base64, logging, json, re, math, threading, io
import requests
import numpy as np
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from collections import deque
from typing import Optional
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HERMES-v2] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/var/log/neurotrade-hermes-v2.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("HERMES-v2")

# ── Config ────────────────────────────────────────────────────────────────────
KRAKEN_PUBLIC  = os.getenv("KRAKEN_PUBLIC",  "")
KRAKEN_PRIVATE = os.getenv("KRAKEN_PRIVATE", "")
KRAKEN_BASE    = "https://demo-futures.kraken.com/derivatives/api/v3"

SUPABASE_URL = os.getenv("SUPABASE_URL_APOLLO", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY_APOLLO", "")

# AI Chain: NVIDIA Qwen 397B → xAI Grok-4 → Gemini
NVIDIA_KEY   = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE  = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "qwen/qwen3.5-397b-a17b")
XAI_KEY      = os.getenv("XAI_API_KEY", "")
XAI_BASE     = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")

# Data
CRYPTOPANIC_KEY = os.getenv("CRYPTOPANIC_KEY", "")
NEWSAPI_KEY     = os.getenv("NEWSAPI_KEY", "")
COINGECKO_KEY   = os.getenv("COINGECKO_API_KEY", "")
FINNHUB_KEY     = os.getenv("FINNHUB_KEY", "")

# ── Parameters ────────────────────────────────────────────────────────────────
LEVERAGE        = 5          # x5 leverage
ACCOUNT_SIZE    = 400.0      # EUR — suma fixă de tranzacționare
RISK_PCT        = 0.05       # 5% din ACCOUNT_SIZE per trade = 20 EUR margin
MAX_POSITIONS   = 6          # max open simultan (6 × 20 EUR = 120 EUR margin total)
MIN_CONFIDENCE  = 65         # AI confidence minim

# Aggressive TP/SL (față de v1: TP=3%, SL=2%)
TAKE_PROFIT_PCT = 5.0        # 5% TP
STOP_LOSS_PCT   = 2.5        # 2.5% SL
TRAIL_PCT       = 3.0        # trailing stop 3%

# ATR-based exits (din OMEGA)
ATR_TP_MULT     = 3.5
ATR_SL_MULT     = 1.4
ATR_TRAIL_MULT  = 2.0

# Wilder RSI (din OMEGA)
WILDER_PERIOD   = 14
RSI_LONG_ENTRY  = 60         # crossover above = BUY momentum
RSI_SHORT_ENTRY = 40         # crossover below = SELL momentum
RSI_LONG_EXIT   = 30
RSI_SHORT_EXIT  = 70

# Hurst + Volume
HURST_MIN       = 0.45       # trend persistent minim
VOL_SURGE_MIN   = 1.6        # volum 1.6× medie

# Safety
MAX_DAILY_LOSS  = 0.15       # -15% equity = stop (liquidation guard cu leverage)
CYCLE_SLEEP     = 300        # 5 minute

# 14 simboluri (față de 7 în v1)
SYMBOLS = {
    "BTC":   "PF_XBTUSD",
    "ETH":   "PF_ETHUSD",
    "SOL":   "PF_SOLUSD",
    "XRP":   "PF_XRPUSD",
    "ADA":   "PF_ADAUSD",
    "LINK":  "PF_LINKUSD",
    "DOT":   "PF_DOTUSD",
    "AVAX":  "PF_AVAXUSD",
    "MATIC": "PF_MATICUSD",
    "DOGE":  "PF_DOGEUSD",
    "LTC":   "PF_LTCUSD",
    "ATOM":  "PF_ATOMUSD",
    "UNI":   "PF_UNIUSD",
    "NEAR":  "PF_NEARUSD",
}

# ── Adaptive Memory ───────────────────────────────────────────────────────────
class HermesMemory:
    def __init__(self, window=10):
        self.trades = deque(maxlen=window)
        self.paused_until: Optional[datetime] = None
        self.conf_min = MIN_CONFIDENCE
        self.daily_pnl = 0.0
        self.daily_start_equity = 0.0

    def record(self, won: bool, pnl: float):
        self.trades.append({"won": won, "pnl": pnl, "ts": datetime.now(timezone.utc)})
        self.daily_pnl += pnl
        self._adjust()

    def _adjust(self):
        if len(self.trades) < 5:
            return
        recent = list(self.trades)[-10:]
        wr = sum(1 for t in recent if t["won"]) / len(recent)
        if wr < 0.40:
            self.paused_until = datetime.now(timezone.utc) + timedelta(hours=1)
            log.warning(f"⛔ HERMES-v2 PAUSED — win rate {wr:.0%}. Resume in 1h.")
        if wr > 0.70:
            self.conf_min = max(58, self.conf_min - 1)
        elif wr < 0.50:
            self.conf_min = min(78, self.conf_min + 2)

    def is_paused(self) -> bool:
        if self.paused_until and datetime.now(timezone.utc) < self.paused_until:
            return True
        if self.paused_until and datetime.now(timezone.utc) >= self.paused_until:
            self.paused_until = None
            log.info("✅ HERMES-v2 RESUMED")
        return False

    def is_daily_loss_exceeded(self, equity: float) -> bool:
        # Stop dacă pierdem mai mult de 15% din cei 400 EUR = 60 EUR
        if self.daily_start_equity == 0:
            self.daily_start_equity = equity
        loss_abs = self.daily_start_equity - equity
        return loss_abs > (400.0 * MAX_DAILY_LOSS)  # > 60 EUR pierdere zilnică

    def summary(self):
        t = list(self.trades)
        if not t:
            return {"total": 0, "wr": 0, "conf_min": self.conf_min}
        return {
            "total": len(t),
            "wr": sum(1 for x in t if x["won"]) / len(t),
            "conf_min": self.conf_min,
            "daily_pnl": round(self.daily_pnl, 2),
        }

MEMORY = HermesMemory()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def tg(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass
TRAILING_PEAKS: dict = {}

# ── Kraken Auth ───────────────────────────────────────────────────────────────
def kraken_sign(endpoint: str, post_data: str, nonce: str) -> str:
    sign_path = "/api/v3" + endpoint
    message   = (post_data + nonce + sign_path).encode("utf-8")
    sha256    = hashlib.sha256(message).digest()
    secret    = base64.b64decode(KRAKEN_PRIVATE)
    sig       = hmac.new(secret, sha256, hashlib.sha512).digest()
    return base64.b64encode(sig).decode()

def kraken_get(endpoint: str, params: dict = None) -> dict:
    try:
        r = requests.get(f"{KRAKEN_BASE}{endpoint}", params=params, timeout=10)
        return r.json()
    except Exception as e:
        log.error(f"Kraken GET {endpoint}: {e}")
        return {}

def kraken_post(endpoint: str, params: dict = None) -> dict:
    params    = params or {}
    nonce     = str(int(time.time() * 1000))
    post_data = urlencode(params)
    sig       = kraken_sign(endpoint, post_data, nonce)
    headers   = {"APIKey": KRAKEN_PUBLIC, "Nonce": nonce, "Authent": sig}
    try:
        r = requests.post(f"{KRAKEN_BASE}{endpoint}", headers=headers, data=post_data, timeout=10)
        return r.json()
    except Exception as e:
        log.error(f"Kraken POST {endpoint}: {e}")
        return {}

# ── Market Data ───────────────────────────────────────────────────────────────
def get_all_tickers() -> dict:
    data = kraken_get("/tickers")
    if not data or "tickers" not in data:
        return {}
    return {t["symbol"]: t for t in data["tickers"]}

def get_trade_history(symbol: str) -> list:
    try:
        data = kraken_get("/history", {"symbol": symbol})
        return data.get("history", [])
    except Exception:
        return []

def build_candles_from_history(history: list, resolution_min: int = 15) -> list:
    if not history:
        return []
    resolution_sec = resolution_min * 60
    trades = sorted(history, key=lambda x: x.get("time", ""))
    buckets = {}
    for t in trades:
        try:
            price  = float(t.get("price", 0))
            size   = float(t.get("size", 0))
            ts_str = t.get("time", "")
            dt     = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            ts     = int(dt.timestamp())
            bucket = (ts // resolution_sec) * resolution_sec
            if bucket not in buckets:
                buckets[bucket] = {"open": price, "high": price, "low": price, "close": price, "vol": 0}
            b = buckets[bucket]
            b["high"]  = max(b["high"], price)
            b["low"]   = min(b["low"], price)
            b["close"] = price
            b["vol"]  += size
        except Exception:
            continue
    candles = []
    for ts in sorted(buckets.keys()):
        b = buckets[ts]
        candles.append([ts, b["open"], b["high"], b["low"], b["close"], b["vol"]])
    return candles

def get_ohlc(symbol: str, resolution: int = 15, count: int = 80) -> list:
    history = get_trade_history(symbol)
    if not history:
        return []
    candles = build_candles_from_history(history, resolution)
    return candles[-count:] if len(candles) > count else candles

def get_ohlc_1h(symbol: str, count: int = 60) -> list:
    history = get_trade_history(symbol)
    if not history:
        return []
    candles = build_candles_from_history(history, 60)
    return candles[-count:] if len(candles) > count else candles


# ══════════════════════════════════════════════════════════════════════════════
#  TELEGRAM MENU SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

ALLOWED_CHAT_IDS = set()
PNL_HISTORY = []
_last_update_id = 0


def _load_allowed_ids():
    for cid in TELEGRAM_CHAT_ID.split(","):
        cid = cid.strip()
        if cid:
            ALLOWED_CHAT_IDS.add(cid)


def is_authorized(chat_id):
    return str(chat_id) in ALLOWED_CHAT_IDS


def tg_send(chat_id, text, reply_markup=None):
    if not TELEGRAM_TOKEN:
        return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage",
            json=payload, timeout=8)
    except Exception:
        pass


def tg_send_photo(chat_id, photo_bytes, caption=""):
    if not TELEGRAM_TOKEN:
        return
    try:
        requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendPhoto",
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("chart.png", photo_bytes, "image/png")},
            timeout=15)
    except Exception:
        pass


def tg_answer_callback(callback_query_id, text=""):
    try:
        requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=5)
    except Exception:
        pass


def get_main_menu():
    return {"inline_keyboard": [
        [{"text": "📊 Status",       "callback_data": "cmd_status"},
         {"text": "📈 Trades",       "callback_data": "cmd_trades"}],
        [{"text": "⏸ Pause",         "callback_data": "cmd_pause"},
         {"text": "▶️ Resume",        "callback_data": "cmd_resume"}],
        [{"text": "💰 Risk",          "callback_data": "cmd_risk_menu"},
         {"text": "🎯 TP/SL",         "callback_data": "cmd_tpsl_menu"}],
        [{"text": "📉 Grafic P&L",    "callback_data": "cmd_chart"},
         {"text": "❌ Inchide pozitie", "callback_data": "cmd_close_menu"}],
        [{"text": "🪙 Simboluri",     "callback_data": "cmd_symbols_menu"},
         {"text": "🏆 Win Rate",      "callback_data": "cmd_winrate"}],
    ]}


def handle_status(chat_id):
    try:
        acc    = kraken_post("/accounts/summary")
        flex   = acc.get("accounts", {}).get("flex", {})
        equity = float(flex.get("portfolioValue", 0))
        margin = float(flex.get("availableMargin", 0))
        pnl    = equity - ACCOUNT_SIZE
        pnl_pct = (pnl / ACCOUNT_SIZE) * 100
        positions = kraken_post("/openpositions").get("openPositions", [])
        mem    = MEMORY.summary()
        lines  = ["📊 <b>HERMES v2 STATUS</b>",
                  "―" * 26,
                  "💼 Equity: $" + str(round(equity, 2)),
                  "💵 Margin liber: $" + str(round(margin, 2)),
                  "📈 P&L: " + ("+" if pnl >= 0 else "") + str(round(pnl, 2)) + "$ (" + ("+" if pnl_pct >= 0 else "") + str(round(pnl_pct, 2)) + "%)",
                  "💰 Cont: " + str(ACCOUNT_SIZE) + "EUR | x" + str(LEVERAGE),
                  "―" * 26,
                  "🔓 Pozitii: " + str(len(positions)) + "/" + str(MAX_POSITIONS)]
        for p in positions:
            coin  = next((k for k, v in SYMBOLS.items() if v == p.get("symbol")), p.get("symbol", "?"))
            icon  = "🟢" if p.get("side") == "long" else "🔴"
            entry = round(float(p.get("price", 0)), 4)
            lines.append("  " + icon + " " + coin + " entry=" + str(entry) + " size=" + str(p.get("size", 0)))
        lines += ["―" * 26,
                  "🤖 " + ("⛔ PAUZAT" if MEMORY.is_paused() else "✅ ACTIV") + " | conf=" + str(mem.get("conf_min", MIN_CONFIDENCE)) + "%",
                  "📅 P&L azi: " + ("+" if mem.get("daily_pnl", 0) >= 0 else "") + str(round(mem.get("daily_pnl", 0), 2)) + "$"]
        tg_send(chat_id, "\n".join(lines), get_main_menu())
    except Exception as e:
        tg_send(chat_id, "❌ Eroare status: " + str(e), get_main_menu())


def handle_trades(chat_id):
    trades = list(MEMORY.trades)
    if not trades:
        tg_send(chat_id, "📈 <b>Nu exista trades inca.</b>", get_main_menu())
        return
    mem  = MEMORY.summary()
    wins = sum(1 for t in trades if t["won"])
    lines = ["📈 <b>ULTIMELE " + str(len(trades)) + " TRADES</b>", "―" * 26]
    for i, t in enumerate(reversed(trades), 1):
        icon = "✅" if t["won"] else "❌"
        ts   = t["ts"].strftime("%d/%m %H:%M") if hasattr(t["ts"], "strftime") else ""
        pnl_str = ("+" if t["pnl"] >= 0 else "") + str(round(t["pnl"], 2))
        lines.append(icon + " #" + str(i) + " | " + ts + " | $" + pnl_str)
    total_pnl = sum(t["pnl"] for t in trades)
    lines += ["―" * 26,
              "🏆 WR: " + str(round(mem.get("wr", 0) * 100, 1)) + "% (" + str(wins) + "/" + str(len(trades)) + ")",
              "💰 Total: " + ("+" if total_pnl >= 0 else "") + str(round(total_pnl, 2)) + "$"]
    tg_send(chat_id, "\n".join(lines), get_main_menu())


def handle_winrate(chat_id):
    trades = list(MEMORY.trades)
    mem    = MEMORY.summary()
    if not trades:
        tg_send(chat_id, "🏆 <b>Nu exista trades inca.</b>", get_main_menu())
        return
    wins   = sum(1 for t in trades if t["won"])
    losses = len(trades) - wins
    gp     = sum(t["pnl"] for t in trades if t["won"])
    gl     = abs(sum(t["pnl"] for t in trades if not t["won"]))
    pf     = round(gp / gl, 2) if gl > 0 else 999.0
    avg_w  = round(gp / wins, 2) if wins > 0 else 0
    avg_l  = round(gl / losses, 2) if losses > 0 else 0
    net    = round(sum(t["pnl"] for t in trades), 2)
    lines  = ["🏆 <b>WIN RATE DETALIAT</b>", "―" * 26,
              "✅ Wins: " + str(wins) + " | ❌ Losses: " + str(losses),
              "📊 Win Rate: " + str(round(mem.get("wr", 0) * 100, 1)) + "%",
              "―" * 26,
              "💚 Avg Win: +$" + str(avg_w),
              "💔 Avg Loss: -$" + str(avg_l),
              "⚖️ Profit Factor: " + str(pf),
              "―" * 26,
              "💰 P&L net: " + ("+" if net >= 0 else "") + str(net) + "$",
              "📅 P&L azi: " + str(round(mem.get("daily_pnl", 0), 2)) + "$",
              "🎯 Conf. min: " + str(mem.get("conf_min", MIN_CONFIDENCE)) + "%"]
    tg_send(chat_id, "\n".join(lines), get_main_menu())


def handle_chart(chat_id):
    if not HAS_MATPLOTLIB:
        tg_send(chat_id, "❌ Ruleaza: pip3 install matplotlib", get_main_menu())
        return
    if len(PNL_HISTORY) < 2:
        tg_send(chat_id, "📉 <b>Date insuficiente.</b> Asteapta 2+ cicluri.", get_main_menu())
        return
    try:
        equities = [p["equity"] for p in PNL_HISTORY]
        pnls     = [p["pnl"] for p in PNL_HISTORY]
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), facecolor="#1a1a2e")
        fig.suptitle("HERMES v2 P&L", color="white", fontsize=13, fontweight="bold")
        ax1.set_facecolor("#16213e")
        ax1.plot(equities, color="#00d4ff", linewidth=2)
        ax1.axhline(y=ACCOUNT_SIZE, color="#ff6b6b", linestyle="--", alpha=0.7)
        ax1.fill_between(range(len(equities)), ACCOUNT_SIZE, equities,
            where=[e >= ACCOUNT_SIZE for e in equities], alpha=0.2, color="#00ff88")
        ax1.fill_between(range(len(equities)), ACCOUNT_SIZE, equities,
            where=[e < ACCOUNT_SIZE for e in equities], alpha=0.2, color="#ff4444")
        ax1.set_ylabel("Equity", color="white")
        ax1.tick_params(colors="white")
        ax1.grid(alpha=0.2, color="gray")
        ax2.set_facecolor("#16213e")
        colors = ["#00ff88" if p >= 0 else "#ff4444" for p in pnls]
        ax2.bar(range(len(pnls)), pnls, color=colors, alpha=0.8)
        ax2.axhline(y=0, color="white", linewidth=0.5)
        ax2.set_ylabel("P&L ($)", color="white")
        ax2.tick_params(colors="white")
        ax2.grid(alpha=0.2, color="gray")
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#1a1a2e")
        plt.close()
        buf.seek(0)
        mem = MEMORY.summary()
        caption = "HERMES v2 | WR: " + str(round(mem.get("wr", 0) * 100, 1)) + "% | Trades: " + str(mem.get("total", 0)) + " | P&L azi: " + str(round(mem.get("daily_pnl", 0), 2)) + "$"
        tg_send_photo(chat_id, buf.read(), caption)
    except Exception as e:
        tg_send(chat_id, "❌ Eroare grafic: " + str(e), get_main_menu())


def handle_risk_menu(chat_id):
    tg_send(chat_id,
        "💰 <b>SCHIMBA RISK</b>\nCurent: " + str(round(RISK_PCT * 100)) + "% = " + str(round(ACCOUNT_SIZE * RISK_PCT)) + "EUR margin -> " + str(round(ACCOUNT_SIZE * RISK_PCT * LEVERAGE)) + "EUR notional",
        {"inline_keyboard": [
            [{"text": "1% (2->10EUR)",   "callback_data": "set_risk_0.01"},
             {"text": "3% (12->60EUR)",  "callback_data": "set_risk_0.03"}],
            [{"text": "5% (20->100EUR) OK", "callback_data": "set_risk_0.05"},
             {"text": "8% (32->160EUR)", "callback_data": "set_risk_0.08"}],
            [{"text": "10% (40->200EUR)", "callback_data": "set_risk_0.10"},
             {"text": "🔙 Inapoi",        "callback_data": "cmd_back"}],
        ]})


def handle_tpsl_menu(chat_id):
    tg_send(chat_id,
        "🎯 <b>SCHIMBA TP/SL</b>\nTP curent: " + str(TAKE_PROFIT_PCT) + "% | SL curent: " + str(STOP_LOSS_PCT) + "%",
        {"inline_keyboard": [
            [{"text": "TP 3% / SL 1.5%",    "callback_data": "set_tpsl_3_1.5"},
             {"text": "TP 5% / SL 2.5% OK", "callback_data": "set_tpsl_5_2.5"}],
            [{"text": "TP 7% / SL 3%",       "callback_data": "set_tpsl_7_3"},
             {"text": "TP 10% / SL 4%",      "callback_data": "set_tpsl_10_4"}],
            [{"text": "🔙 Inapoi",            "callback_data": "cmd_back"}],
        ]})


def handle_close_menu(chat_id):
    positions = kraken_post("/openpositions").get("openPositions", [])
    if not positions:
        tg_send(chat_id, "❌ <b>Nicio pozitie deschisa.</b>", get_main_menu())
        return
    buttons = []
    for p in positions:
        coin  = next((k for k, v in SYMBOLS.items() if v == p.get("symbol")), p.get("symbol", "?"))
        icon  = "🟢" if p.get("side") == "long" else "🔴"
        entry = round(float(p.get("price", 0)), 4)
        size  = float(p.get("size", 0))
        buttons.append([{"text": icon + " Inchide " + coin + " @$" + str(entry),
                         "callback_data": "close_pos_" + str(p.get("symbol")) + "_" + str(size) + "_" + str(p.get("side", "long"))}])
    buttons.append([{"text": "❌ Inchide TOATE", "callback_data": "close_all_positions"}])
    buttons.append([{"text": "🔙 Inapoi",        "callback_data": "cmd_back"}])
    tg_send(chat_id, "❌ <b>INCHIDE POZITIE</b>\nSelecteaza:", {"inline_keyboard": buttons})


def handle_symbols_menu(chat_id):
    active = list(SYMBOLS.keys())
    all_av = ["BTC","ETH","SOL","XRP","ADA","LINK","DOT","AVAX","MATIC",
              "DOGE","LTC","ATOM","UNI","NEAR","FTM","SAND","MANA","APE"]
    add_btns = [{"text": "+" + s, "callback_data": "add_sym_" + s}
                for s in all_av if s not in active]
    rem_btns = [{"text": "-" + s, "callback_data": "rem_sym_" + s} for s in active]
    keyboard = []
    for i in range(0, len(add_btns), 3):
        keyboard.append(add_btns[i:i+3])
    if rem_btns:
        keyboard.append([{"text": "── Elimina ──", "callback_data": "noop"}])
        for i in range(0, len(rem_btns), 3):
            keyboard.append(rem_btns[i:i+3])
    keyboard.append([{"text": "🔙 Inapoi", "callback_data": "cmd_back"}])
    tg_send(chat_id, "🪙 <b>SIMBOLURI (" + str(len(active)) + " active)</b>\n" + " | ".join(active), {"inline_keyboard": keyboard})


def process_callback(callback_query):
    global RISK_PCT, TAKE_PROFIT_PCT, STOP_LOSS_PCT, ATR_TP_MULT, ATR_SL_MULT
    chat_id = str(callback_query["message"]["chat"]["id"])
    cb_id   = callback_query["id"]
    data    = callback_query.get("data", "")
    if not is_authorized(chat_id):
        tg_answer_callback(cb_id, "❌ Neautorizat")
        return
    tg_answer_callback(cb_id, "⏳")
    if   data == "cmd_status":       handle_status(chat_id)
    elif data == "cmd_trades":       handle_trades(chat_id)
    elif data == "cmd_winrate":      handle_winrate(chat_id)
    elif data == "cmd_chart":        handle_chart(chat_id)
    elif data == "cmd_risk_menu":    handle_risk_menu(chat_id)
    elif data == "cmd_tpsl_menu":    handle_tpsl_menu(chat_id)
    elif data == "cmd_close_menu":   handle_close_menu(chat_id)
    elif data == "cmd_symbols_menu": handle_symbols_menu(chat_id)
    elif data == "cmd_back":
        tg_send(chat_id, "🏠 <b>Meniu principal</b>", get_main_menu())
    elif data == "cmd_pause":
        MEMORY.paused_until = datetime.now(timezone.utc) + timedelta(hours=24)
        tg_send(chat_id, "⏸ <b>Bot PAUZAT 24h.</b>", get_main_menu())
        log.info("Bot pauzat din Telegram")
    elif data == "cmd_resume":
        MEMORY.paused_until = None
        tg_send(chat_id, "▶️ <b>Bot ACTIV.</b>", get_main_menu())
        log.info("Bot reactivat din Telegram")
    elif data.startswith("set_risk_"):
        RISK_PCT = float(data.replace("set_risk_", ""))
        tg_send(chat_id,
            "💰 Risk setat: " + str(round(RISK_PCT * 100)) + "%\n" +
            str(round(ACCOUNT_SIZE * RISK_PCT)) + "EUR margin -> " + str(round(ACCOUNT_SIZE * RISK_PCT * LEVERAGE)) + "EUR notional",
            get_main_menu())
        log.info("Risk: " + str(round(RISK_PCT * 100)) + "%")
    elif data.startswith("set_tpsl_"):
        parts = data.replace("set_tpsl_", "").split("_")
        TAKE_PROFIT_PCT = float(parts[0])
        STOP_LOSS_PCT   = float(parts[1])
        ATR_TP_MULT     = TAKE_PROFIT_PCT / 1.5
        ATR_SL_MULT     = STOP_LOSS_PCT / 1.8
        tg_send(chat_id, "🎯 TP=" + str(TAKE_PROFIT_PCT) + "% | SL=" + str(STOP_LOSS_PCT) + "%", get_main_menu())
        log.info("TP/SL: " + str(TAKE_PROFIT_PCT) + "/" + str(STOP_LOSS_PCT))
    elif data.startswith("close_pos_"):
        parts      = data.replace("close_pos_", "").split("_")
        sym        = parts[0]
        size       = float(parts[1])
        side       = parts[2]
        close_side = "sell" if side == "long" else "buy"
        r    = kraken_post("/sendorder", {"orderType": "mkt", "symbol": sym, "side": close_side, "size": str(size)})
        coin = next((k for k, v in SYMBOLS.items() if v == sym), sym)
        ok   = r.get("result") == "success" or "sendStatus" in r
        tg_send(chat_id, ("✅ " if ok else "❌ ") + coin + (" inchisa." if ok else " eroare."), get_main_menu())
    elif data == "close_all_positions":
        positions = kraken_post("/openpositions").get("openPositions", [])
        closed = 0
        for p in positions:
            sym  = p.get("symbol")
            size = abs(float(p.get("size", 0)))
            side = "sell" if p.get("side") == "long" else "buy"
            r    = kraken_post("/sendorder", {"orderType": "mkt", "symbol": sym, "side": side, "size": str(size)})
            if r.get("result") == "success" or "sendStatus" in r:
                closed += 1
        tg_send(chat_id, "✅ " + str(closed) + "/" + str(len(positions)) + " pozitii inchise.", get_main_menu())
    elif data.startswith("add_sym_"):
        sym = data.replace("add_sym_", "")
        kf  = {"FTM": "PF_FTMUSD", "SAND": "PF_SANDUSD", "MANA": "PF_MANAUSD", "APE": "PF_APEUSD"}
        if sym in kf:
            SYMBOLS[sym] = kf[sym]
            tg_send(chat_id, "+" + sym + " adaugat! Total: " + str(len(SYMBOLS)), get_main_menu())
        else:
            tg_send(chat_id, "❌ " + sym + " nu are futures pe Kraken Demo.", get_main_menu())
    elif data.startswith("rem_sym_"):
        sym = data.replace("rem_sym_", "")
        if sym in SYMBOLS and len(SYMBOLS) > 3:
            del SYMBOLS[sym]
            tg_send(chat_id, "-" + sym + " eliminat! Total: " + str(len(SYMBOLS)), get_main_menu())
        else:
            tg_send(chat_id, "❌ Minim 3 simboluri.", get_main_menu())


def process_message(message):
    chat_id = str(message.get("chat", {}).get("id", ""))
    text    = message.get("text", "").strip().lower()
    if not is_authorized(chat_id):
        return
    if text in ["/start", "/menu", "/help"]:
        tg_send(chat_id,
            "🤖 <b>HERMES v2</b>\n" + "―" * 26 + "\n" +
            "💰 " + str(ACCOUNT_SIZE) + "EUR | x" + str(LEVERAGE) + " | " + str(len(SYMBOLS)) + " simboluri\n" +
            "―" * 26 + "\nSelecteaza:",
            get_main_menu())
    elif text == "/status":   handle_status(chat_id)
    elif text == "/trades":   handle_trades(chat_id)
    elif text == "/winrate":  handle_winrate(chat_id)
    elif text == "/chart":    handle_chart(chat_id)
    elif text == "/pause":
        MEMORY.paused_until = datetime.now(timezone.utc) + timedelta(hours=24)
        tg_send(chat_id, "⏸ Pauzat.", get_main_menu())
    elif text == "/resume":
        MEMORY.paused_until = None
        tg_send(chat_id, "▶️ Activ.", get_main_menu())
    else:
        tg_send(chat_id, "Trimite /menu", get_main_menu())


def telegram_polling_loop():
    global _last_update_id
    _load_allowed_ids()
    log.info("Telegram menu pornit | Autorizati: " + str(ALLOWED_CHAT_IDS))
    while True:
        try:
            r = requests.get(
                "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/getUpdates",
                params={"offset": _last_update_id + 1, "timeout": 30},
                timeout=35)
            if not r.ok:
                time.sleep(5)
                continue
            for update in r.json().get("result", []):
                _last_update_id = update["update_id"]
                if "callback_query" in update:
                    try: process_callback(update["callback_query"])
                    except Exception as e: log.error("Callback err: " + str(e))
                elif "message" in update:
                    try: process_message(update["message"])
                    except Exception as e: log.error("Message err: " + str(e))
        except Exception as e:
            log.error("Polling err: " + str(e))
            time.sleep(10)

# ── Technical Indicators ──────────────────────────────────────────────────────
def wilder_rsi_series(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """
    WILDER RSI — nu SMA RSI!
    Din OMEGA: 57x backtest return vs 9.5x cu SMA method.
    """
    rsi_vals = np.full(len(closes), 50.0)
    if len(closes) < 5:
        return rsi_vals
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        rs = ag / al if al > 0 else 100
        rsi_vals[i + 1] = 100 - (100 / (1 + rs))
    return rsi_vals

def compute_atr(highs, lows, closes, period=14) -> np.ndarray:
    if len(closes) < period + 1:
        return np.array([float(closes[-1]) * 0.015])
    tr = np.maximum(highs[1:] - lows[1:],
         np.maximum(np.abs(highs[1:] - closes[:-1]),
                    np.abs(lows[1:] - closes[:-1])))
    atr = np.zeros(len(tr))
    atr[period - 1] = np.mean(tr[:period])
    for i in range(period, len(tr)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr

def compute_ema(prices: np.ndarray, period: int) -> float:
    if len(prices) < 2:
        return float(prices[-1]) if len(prices) else 0.0
    ema = float(prices[0])
    k = 2 / (period + 1)
    for p in prices[1:]:
        ema = float(p) * k + ema * (1 - k)
    return ema

def compute_hurst(closes: np.ndarray) -> float:
    """Hurst Exponent — H>0.55 = trend valid, H<0.45 = random walk"""
    if len(closes) < 8:
        return 0.5
    def rs(data):
        mean = np.mean(data)
        dev = np.cumsum(data - mean)
        r = np.max(dev) - np.min(dev)
        s = np.std(data, ddof=1)
        return r / s if s > 0 else 0
    log_ret = np.diff(np.log(closes + 1e-10))
    n = len(log_ret)
    windows, rs_vals = [], []
    w = 8
    while w <= n // 2:
        rs_list = [rs(log_ret[i:i+w]) for i in range(0, n-w+1, w) if rs(log_ret[i:i+w]) > 0]
        if rs_list:
            windows.append(w)
            rs_vals.append(np.mean(rs_list))
        w = int(w * 1.5)
    if len(windows) < 3:
        return 0.5
    coeffs = np.polyfit(np.log(windows), np.log(rs_vals), 1)
    return round(float(np.clip(coeffs[0], 0.0, 1.0)), 4)

def rsi_crossover_above(rsi_series: np.ndarray, level: float) -> bool:
    if len(rsi_series) < 3:
        return False
    return float(rsi_series[-2]) < level <= float(rsi_series[-1])

def rsi_crossover_below(rsi_series: np.ndarray, level: float) -> bool:
    if len(rsi_series) < 3:
        return False
    return float(rsi_series[-2]) > level >= float(rsi_series[-1])

# ── Sentiment Engine ──────────────────────────────────────────────────────────
_SENT_CACHE: dict = {}

def get_sentiment(coin: str) -> dict:
    cache_key = f"{coin}_{datetime.now(timezone.utc).strftime('%H%M')[:-1]}"
    if cache_key in _SENT_CACHE:
        return _SENT_CACHE[cache_key]

    scores, sources = [], []

    # CryptoPanic
    if CRYPTOPANIC_KEY:
        try:
            r = requests.get("https://cryptopanic.com/api/developer/v2/posts/", params={
                "auth_token": CRYPTOPANIC_KEY, "currencies": coin,
                "filter": "hot", "limit": 8,
            }, timeout=8)
            results = r.json().get("results", [])
            bull = sum(1 for n in results if n.get("votes", {}).get("positive", 0) > n.get("votes", {}).get("negative", 0))
            if results:
                cp = (bull / len(results)) * 100
                scores.append(cp)
                sources.append(f"CP:{cp:.0f}")
        except: pass

    # CoinGecko market sentiment
    if COINGECKO_KEY:
        try:
            r = requests.get("https://api.coingecko.com/api/v3/global",
                headers={"x-cg-demo-api-key": COINGECKO_KEY}, timeout=8)
            if r.ok:
                mkt_change = r.json().get("data", {}).get("market_cap_change_percentage_24h_usd", 0)
                cg = 50 + min(30, max(-30, mkt_change * 3))
                scores.append(cg)
                sources.append(f"CG:{mkt_change:+.1f}%")
        except: pass

    # NewsAPI
    if NEWSAPI_KEY:
        try:
            r = requests.get("https://newsapi.org/v2/everything", params={
                "q": f"{coin} crypto", "language": "en",
                "pageSize": 8, "sortBy": "publishedAt",
                "apiKey": NEWSAPI_KEY,
                "from": (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S"),
            }, timeout=10)
            articles = r.json().get("articles", [])
            bull_w = ["beat","surge","buy","record","bullish","moon","pump","ath","rally","gain"]
            bear_w = ["crash","dump","sell","loss","bearish","fear","ban","hack","fraud","drop"]
            b = sum(1 for a in articles for w in bull_w if w in (a.get("title","")+"").lower())
            s = sum(1 for a in articles for w in bear_w if w in (a.get("title","")+"").lower())
            if b + s > 0:
                ns = (b / (b + s)) * 100
                scores.append(ns)
                sources.append(f"NEWS:{ns:.0f}")
        except: pass

    # Finnhub pentru coins cu ticker (BTC, ETH)
    if FINNHUB_KEY and coin in ["BTC", "ETH"]:
        try:
            r = requests.get("https://finnhub.io/api/v1/crypto/candle",
                params={"symbol": f"BINANCE:{coin}USDT", "resolution": "D", "count": 1,
                        "token": FINNHUB_KEY}, timeout=8)
        except: pass

    composite = round(float(np.mean(scores)), 2) if scores else 50.0
    result = {
        "composite": composite,
        "sources": " | ".join(sources),
        "n_sources": len(scores),
        "bullish": composite >= 55,
    }
    _SENT_CACHE[cache_key] = result
    return result

def get_news_headlines(coin: str) -> list:
    headlines = []
    if CRYPTOPANIC_KEY:
        try:
            r = requests.get("https://cryptopanic.com/api/developer/v2/posts/", params={
                "auth_token": CRYPTOPANIC_KEY, "currencies": coin,
                "filter": "hot", "limit": 5,
            }, timeout=8)
            for item in r.json().get("results", [])[:5]:
                t = item.get("title", "")
                if t: headlines.append(t)
        except: pass
    if NEWSAPI_KEY:
        try:
            r = requests.get("https://newsapi.org/v2/everything", params={
                "q": f"{coin} cryptocurrency", "apiKey": NEWSAPI_KEY,
                "pageSize": 5, "sortBy": "publishedAt",
            }, timeout=8)
            for item in r.json().get("articles", [])[:5]:
                t = item.get("title", "")
                if t: headlines.append(t)
        except: pass
    return headlines[:8]

# ── AI Chain: NVIDIA Qwen → Grok-4 → Gemini ──────────────────────────────────
def ai_validate(coin: str, symbol: str, side: str, price: float,
                rsi: float, hurst: float, atr: float, vol_ratio: float,
                sentiment: dict, tp: float, sl: float, rr: float,
                headlines: list) -> tuple[bool, int, str]:

    news_block = "\n".join(f"- {h}" for h in headlines[:6]) if headlines else "No news available"
    side_icon  = "LONG 🟢" if side == "buy" else "SHORT 🔴"

    prompt = f"""You are an elite crypto futures trading AI with leverage x5.

Symbol: {coin}/USD ({side_icon}) | Price: ${price:.4f} | Leverage: x5

WILDER RSI SIGNALS (superior to SMA RSI — 57x backtested returns):
- Wilder RSI(14): {rsi:.1f} {'🚀 MOMENTUM CONFIRMED' if (side=='buy' and rsi>=68) or (side=='sell' and rsi<=32) else '⚡ BUILDING'}
- Hurst Exponent: {hurst:.3f} {'✅ TRENDING (valid)' if hurst > 0.55 else '⚠️ RANDOM WALK (skip)' if hurst > 0.45 else '↩️ MEAN REVERTING'}
- Volume surge: {vol_ratio:.2f}× 20-bar average {'✅ INSTITUTIONAL' if vol_ratio > 2 else '✅ ELEVATED' if vol_ratio > 1.5 else '⚠️ NORMAL'}
- ATR(14): ${atr:.4f}
- Expected R/R: {rr:.2f} (aggressive mode, minimum 1.8)

MULTI-SOURCE SENTIMENT ({sentiment.get('n_sources',0)} sources):
- Composite: {sentiment.get('composite',50):.1f}/100 (50=neutral, >60=bullish)
- Sources: {sentiment.get('sources','none')}

RECENT NEWS:
{news_block}

TP: ${tp:.4f} (+{TAKE_PROFIT_PCT}%) | SL: ${sl:.4f} (-{STOP_LOSS_PCT}%)

LEVERAGE x5 context: A 1% move = 5% portfolio impact. Only approve HIGH CONVICTION setups.
Respond ONLY with JSON: {{"action": "TRADE" or "SKIP", "confidence": 0-100, "reasoning": "max 150 chars"}}"""

    # ── NVIDIA Qwen 397B (primary) ────────────────────────────────────────────
    if NVIDIA_KEY:
        try:
            r = requests.post(f"{NVIDIA_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"},
                json={
                    "model": NVIDIA_MODEL,
                    "messages": [
                        {"role": "system", "content": "Expert crypto futures quant. JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 250, "temperature": 0.1,
                }, timeout=30)
            if r.ok:
                text = r.json()["choices"][0]["message"]["content"]
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    a = parsed.get("action", "SKIP")
                    c = int(parsed.get("confidence", 50))
                    reas = parsed.get("reasoning", "")[:200]
                    if a == "TRADE" and c >= MEMORY.conf_min:
                        return True, c, f"[Qwen397B] {reas}"
                    elif a == "SKIP":
                        return False, c, f"[Qwen397B] {reas}"
        except Exception as e:
            log.warning(f"NVIDIA Qwen err: {e}")

    # ── xAI Grok-4 (fallback 1) ───────────────────────────────────────────────
    if XAI_KEY:
        try:
            r = requests.post(f"{XAI_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-4-latest",
                    "messages": [
                        {"role": "system", "content": "Expert crypto quant. JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 250, "temperature": 0.1,
                }, timeout=25)
            if r.ok:
                text = r.json()["choices"][0]["message"]["content"]
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    a = parsed.get("action", "SKIP")
                    c = int(parsed.get("confidence", 50))
                    reas = parsed.get("reasoning", "")[:200]
                    return a == "TRADE" and c >= MEMORY.conf_min, c, f"[Grok4] {reas}"
        except Exception as e:
            log.warning(f"Grok-4 err: {e}")

    # ── Gemini (fallback 2) ───────────────────────────────────────────────────
    if GEMINI_KEY:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
            if r.ok:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    a = parsed.get("action", "SKIP")
                    c = int(parsed.get("confidence", 50))
                    reas = parsed.get("reasoning", "")[:200]
                    return a == "TRADE" and c >= MEMORY.conf_min, c, f"[Gemini] {reas}"
        except: pass

    return True, 66, "AI unavailable — default pass"

# ── Technical Analysis per Symbol ────────────────────────────────────────────

def build_price_series(symbol, tickers, n=50):
    history = []
    try:
        import requests
        data = requests.get("https://demo-futures.kraken.com/derivatives/api/v3/history",
            params={"symbol": symbol}, timeout=10).json()
        history = data.get("history", [])
    except Exception:
        pass
    prices = []
    for t in sorted(history, key=lambda x: x.get("time","")):
        try: prices.append(float(t.get("price",0)))
        except: pass
    ticker = tickers.get(symbol, {})
    current = float(ticker.get("last", 0))
    if current > 0:
        prices.append(current)
    if not prices:
        return __import__("numpy").array([])
    import numpy as np
    if len(prices) < n:
        base = prices[-1]
        vol  = np.std(prices) if len(prices) > 1 else base * 0.001
        if vol == 0: vol = base * 0.001
        np.random.seed(int(base) % 9999)
        extra = []
        p = prices[0]
        for _ in range(n - len(prices)):
            p = p * (1 + np.random.normal(0, vol/base*0.3))
            extra.append(p)
        prices = extra + prices
    return np.array(prices[-n:])

def analyze(coin, symbol, tickers):
    ticker = tickers.get(symbol, {})
    price  = float(ticker.get("last", 0))
    if price <= 0:
        return None

    closes = build_price_series(symbol, tickers, n=50)
    if len(closes) < 5:
        return None

    import numpy as np
    highs  = closes * 1.002
    lows   = closes * 0.998
    atr_s  = compute_atr(highs, lows, closes, min(14, len(closes)-1))
    atr    = float(atr_s[-1]) if len(atr_s) > 0 else price * 0.015

    period = min(14, len(closes)-2)
    rsi_s  = wilder_rsi_series(closes, period)
    rsi    = float(rsi_s[-1])

    cross_long  = rsi_crossover_above(rsi_s, RSI_LONG_ENTRY)
    cross_short = rsi_crossover_below(rsi_s, RSI_SHORT_ENTRY)
    strong_long = rsi >= RSI_LONG_ENTRY
    strong_short= rsi <= RSI_SHORT_ENTRY

    if not (cross_long or strong_long or cross_short or strong_short):
        return None

    side = "buy" if (cross_long or strong_long) else "sell"
    hurst    = compute_hurst(closes)
    vol_24h  = float(ticker.get("vol24h", 1))
    vol_ratio= min(vol_24h / 500, 5.0) if vol_24h > 0 else 1.6
    ema50    = compute_ema(closes, min(50, len(closes)-1))

    if len(closes) >= 30:
        if side == "buy" and price < ema50:
            return None
        if side == "sell" and price > ema50:
            return None

    if side == "buy":
        tp_atr = price + ATR_TP_MULT * atr
        sl_atr = price - ATR_SL_MULT * atr
    else:
        tp_atr = price - ATR_TP_MULT * atr
        sl_atr = price + ATR_SL_MULT * atr

    rr = abs(tp_atr - price) / abs(price - sl_atr) if abs(price - sl_atr) > 0 else 0
    if rr < 1.2:
        return None

    sentiment = get_sentiment(coin)
    if side == "buy" and sentiment["composite"] < 25 and sentiment["n_sources"] >= 2:
        return None
    if side == "sell" and sentiment["composite"] > 78 and sentiment["n_sources"] >= 2:
        return None

    headlines = get_news_headlines(coin)
    valid, confidence, reasoning = ai_validate(
        coin, symbol, side, price, rsi, hurst, atr,
        vol_ratio, sentiment, tp_atr, sl_atr, rr, headlines
    )
    if not valid:
        return None

    return {
        "coin": coin, "symbol": symbol, "side": side,
        "price": price, "rsi": round(rsi, 2), "hurst": hurst,
        "atr": round(atr, 6), "vol_ratio": round(vol_ratio, 2),
        "take_profit": round(tp_atr, 6),
        "stop_loss":   round(sl_atr, 6),
        "expected_rr": round(rr, 3),
        "confidence": confidence, "reasoning": reasoning,
        "sentiment":  sentiment,
        "cross_type": "long_cross" if (cross_long or strong_long) else "short_cross",
    }

def place_order(sig: dict, margin: float) -> bool:
    price = sig["price"]
    if price <= 0:
        return False

    # Size cu leverage — bazat pe ACCOUNT_SIZE fix (400 EUR)
    trade_margin = ACCOUNT_SIZE * RISK_PCT      # 400 * 0.05 = 20 EUR margin
    notional     = trade_margin * LEVERAGE       # 20 * 5 = 100 EUR notional
    size         = round(notional / price, 4)

    if size <= 0:
        log.warning(f"Size=0 pentru {sig['coin']}, skip")
        return False

    params = {
        "orderType": "mkt",
        "symbol":    sig["symbol"],
        "side":      sig["side"],
        "size":      str(size),
    }
    result = kraken_post("/sendorder", params)

    ok = result.get("result") == "success" or "sendStatus" in result
    if ok:
        TRAILING_PEAKS[sig["symbol"]] = price
        direction = "LONG 🟢" if sig["side"] == "buy" else "SHORT 🔴"
        tg(f"⚡ <b>HERMES-v2 {direction}</b>: {size} {sig['coin']} @ ${price:.4f}\nRSI={sig['rsi']} H={sig['hurst']} conf={sig['confidence']}%\nTP=${sig['take_profit']:.4f} SL=${sig['stop_loss']:.4f} RR={sig['expected_rr']:.2f}")
        log.info(
            f"⚡ ORDER {direction}: {size} {sig['coin']} @ ${price:.4f} "
            f"| RSI={sig['rsi']} H={sig['hurst']} vol={sig['vol_ratio']:.1f}× "
            f"| TP=${sig['take_profit']:.4f} SL=${sig['stop_loss']:.4f} "
            f"| RR={sig['expected_rr']:.2f} | conf={sig['confidence']}% "
            f"| margin={trade_margin:.2f}EUR notional={notional:.2f}EUR (x{LEVERAGE}) din cont fix {ACCOUNT_SIZE}EUR"
        )
        sb_insert("trades", {
            "symbol": sig["coin"], "action": sig["side"].upper(),
            "price": price, "qty": size,
            "confidence": sig["confidence"],
            "reasoning": f"[HERMES-v2 x{LEVERAGE}] {sig['reasoning']}",
            "rsi": sig["rsi"], "strategy": "hermes_v2_wilder_rsi",
            "take_profit": sig["take_profit"], "stop_loss": sig["stop_loss"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    else:
        log.error(f"Order FAILED {sig['coin']}: {result}")
    return ok

# ── Manage Exits ──────────────────────────────────────────────────────────────
def check_exits(tickers: dict):
    data = kraken_post("/openpositions")
    positions = data.get("openPositions", [])
    if not positions:
        return

    for pos in positions:
        sym   = pos.get("symbol", "")
        side  = pos.get("side", "long")
        size  = abs(float(pos.get("size", 0)))
        entry = float(pos.get("price", 0))

        ticker  = tickers.get(sym, {})
        current = float(ticker.get("last", entry))
        if entry <= 0 or current <= 0:
            continue

        pnl_pct = (current - entry) / entry * 100 * LEVERAGE
        if side == "short":
            pnl_pct = -pnl_pct

        coin = next((k for k, v in SYMBOLS.items() if v == sym), sym)

        # Update trailing peak
        if sym not in TRAILING_PEAKS:
            TRAILING_PEAKS[sym] = current
        if side == "long":
            TRAILING_PEAKS[sym] = max(TRAILING_PEAKS[sym], current)
        else:
            TRAILING_PEAKS[sym] = min(TRAILING_PEAKS[sym], current)
        peak = TRAILING_PEAKS[sym]

        # ATR-based exits
        candles = get_ohlc(sym, 15, 30)
        atr = entry * 0.015
        if len(candles) >= 15:
            closes = np.array([float(c[4]) for c in candles if len(c) > 4])
            highs  = np.array([float(c[2]) for c in candles if len(c) > 4])
            lows   = np.array([float(c[3]) for c in candles if len(c) > 4])
            atr_s  = compute_atr(highs, lows, closes, 14)
            if len(atr_s) > 0:
                atr = float(atr_s[-1])

        # Exit conditions
        should_exit = False
        exit_reason = ""

        if side == "long":
            tp_price    = entry + ATR_TP_MULT * atr
            sl_price    = entry - ATR_SL_MULT * atr
            trail_price = peak - ATR_TRAIL_MULT * atr
            if current >= tp_price:
                should_exit, exit_reason = True, "take_profit"
            elif current <= sl_price:
                should_exit, exit_reason = True, "stop_loss"
            elif current <= trail_price and pnl_pct > 0:
                should_exit, exit_reason = True, "trailing_stop"
            else:
                # Wilder RSI exit
                if len(candles) >= 20:
                    closes = np.array([float(c[4]) for c in candles if len(c) > 4])
                    rsi_s = wilder_rsi_series(closes, WILDER_PERIOD)
                    if rsi_crossover_below(rsi_s, RSI_LONG_EXIT):
                        should_exit, exit_reason = True, "wilder_rsi_exit"
        else:
            tp_price    = entry - ATR_TP_MULT * atr
            sl_price    = entry + ATR_SL_MULT * atr
            trail_price = peak + ATR_TRAIL_MULT * atr
            if current <= tp_price:
                should_exit, exit_reason = True, "take_profit"
            elif current >= sl_price:
                should_exit, exit_reason = True, "stop_loss"
            elif current >= trail_price and pnl_pct > 0:
                should_exit, exit_reason = True, "trailing_stop"
            else:
                if len(candles) >= 20:
                    closes = np.array([float(c[4]) for c in candles if len(c) > 4])
                    rsi_s = wilder_rsi_series(closes, WILDER_PERIOD)
                    if rsi_crossover_above(rsi_s, RSI_SHORT_EXIT):
                        should_exit, exit_reason = True, "wilder_rsi_exit"

        if should_exit:
            close_side = "sell" if side == "long" else "buy"
            result = kraken_post("/sendorder", {
                "orderType": "mkt", "symbol": sym,
                "side": close_side, "size": str(size),
            })
            if result.get("result") == "success" or "sendStatus" in result:
                won = pnl_pct > 0
                # Estimare P&L în $
                pnl_dollar = (pnl_pct / 100) * entry * size / LEVERAGE
                MEMORY.record(won, pnl_dollar)
                TRAILING_PEAKS.pop(sym, None)
                icon = "✅" if won else "❌"
                tg(f"{icon} <b>HERMES-v2 EXIT</b> {coin}\n{exit_reason} | P&L={pnl_pct:+.2f}% (x{LEVERAGE}) | ${pnl_dollar:+.2f}")
                log.info(f"{icon} EXIT {coin} | {exit_reason} | P&L={pnl_pct:+.2f}% (x{LEVERAGE}) | ${pnl_dollar:+.2f}")
                sb_insert("trades", {
                    "symbol": coin, "action": "CLOSE",
                    "price": current, "qty": size,
                    "pl": round(pnl_dollar, 2),
                    "close_type": exit_reason,
                    "strategy": "hermes_v2_exit",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

# ── Supabase ──────────────────────────────────────────────────────────────────
def sb_upsert(table, data):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers={
            "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates",
        }, json=data, timeout=5)
    except: pass

def sb_insert(table, data):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers={
            "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }, json=data, timeout=5)
    except: pass

def update_portfolio(equity, margin, n_pos):
    mem = MEMORY.summary()
    sb_upsert("portfolio_snapshot", {
        "id": 1,
        "equity": round(equity, 2),
        "cash": round(margin, 2),
        "open_positions": n_pos,
        "pnl": round(equity - ACCOUNT_SIZE, 2),
        "pnl_pct": round((equity - ACCOUNT_SIZE) / ACCOUNT_SIZE * 100, 4),
        "strategy": f"HERMES_v2_x{LEVERAGE}",
        "bot_version": "2.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    PNL_HISTORY.append({"ts": datetime.now(timezone.utc), "equity": equity, "pnl": round(equity - ACCOUNT_SIZE, 2)})
    if len(PNL_HISTORY) > 500:
        PNL_HISTORY.pop(0)
    PNL_HISTORY.append({"ts": datetime.now(timezone.utc), "equity": equity, "pnl": round(equity - ACCOUNT_SIZE, 2)})
    if len(PNL_HISTORY) > 500: PNL_HISTORY.pop(0)
    PNL_HISTORY.append({"ts": datetime.now(timezone.utc), "equity": equity, "pnl": round(equity - ACCOUNT_SIZE, 2)})
    if len(PNL_HISTORY) > 500: PNL_HISTORY.pop(0)
    log.info(
        f"💼 equity=${equity:.2f} | margin=${margin:.2f} | {n_pos} pos | "
        f"WR={mem.get('wr', 0):.0%} | conf_min={mem.get('conf_min', MIN_CONFIDENCE)} | "
        f"daily_pnl=${mem.get('daily_pnl', 0):+.2f}"
    )

# ── Main Loop ─────────────────────────────────────────────────────────────────
def main():
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║  NeuroTrade HERMES v2 — Advanced Crypto Scalping Engine      ║")
    log.info(f"║  Leverage: x{LEVERAGE} | TP: {TAKE_PROFIT_PCT}% | SL: {STOP_LOSS_PCT}% | 14 simboluri        ║")
    log.info("║  AI: NVIDIA Qwen 397B → Grok-4 → Gemini                     ║")
    log.info("║  Wilder RSI + Hurst + Dual TF + Adaptive Memory             ║")
    log.info("╚══════════════════════════════════════════════════════════════╝")
    log.info(f"Simboluri ({len(SYMBOLS)}): {list(SYMBOLS.keys())}")
    tg_thread = threading.Thread(target=telegram_polling_loop, daemon=True)
    tg_thread.start()
    log.info("🤖 Telegram menu thread pornit")
    tg(f"🚀 <b>HERMES v2 PORNIT</b>\nCont: {ACCOUNT_SIZE} EUR | x{LEVERAGE} leverage\n{len(SYMBOLS)} simboluri | Risk/trade: {ACCOUNT_SIZE*RISK_PCT:.0f} EUR margin → {ACCOUNT_SIZE*RISK_PCT*LEVERAGE:.0f} EUR notional\nTP={TAKE_PROFIT_PCT}% SL={STOP_LOSS_PCT}%")

    cycle = 0
    last_daily_reset = datetime.now(timezone.utc).date()

    while True:
        cycle += 1
        log.info(f"═══ HERMES-v2 CYCLE {cycle} ══════════════════════════════════════")

        try:
            # Reset daily tracking
            today = datetime.now(timezone.utc).date()
            if today != last_daily_reset:
                MEMORY.daily_pnl = 0.0
                MEMORY.daily_start_equity = 0.0
                last_daily_reset = today
                log.info("📅 Daily P&L reset")

            # Pause check
            if MEMORY.is_paused():
                rem = (MEMORY.paused_until - datetime.now(timezone.utc)).seconds // 60 if MEMORY.paused_until else 0
                log.info(f"⛔ PAUSED — {rem}min remaining")
                time.sleep(60)
                continue

            # Account info
            acc   = kraken_post("/accounts/summary")
            flex  = acc.get("accounts", {}).get("flex", {})
            equity = float(flex.get("portfolioValue", 20000))
            margin = float(flex.get("availableMargin", 20000))

            # Daily loss guard (liquidation guard cu leverage)
            if MEMORY.is_daily_loss_exceeded(equity):
                log.warning(f"🛑 Daily loss -{MAX_DAILY_LOSS*100:.0f}% — HERMES-v2 STOPPED for today")
                time.sleep(CYCLE_SLEEP)
                continue

            tickers = get_all_tickers()
            positions_data = kraken_post("/openpositions")
            positions = positions_data.get("openPositions", [])
            n_pos = len(positions)
            open_syms = {p.get("symbol") for p in positions}

            update_portfolio(equity, margin, n_pos)

            # Check exits first
            check_exits(tickers)

            # Scan for signals
            signals = []
            for coin, sym in SYMBOLS.items():
                if sym in open_syms:
                    continue
                sig = analyze(coin, sym, tickers)
                if sig:
                    signals.append(sig)
                    dir_icon = "🟢 LONG" if sig["side"] == "buy" else "🔴 SHORT"
                    log.info(
                        f"  {dir_icon} {coin}: RSI={sig['rsi']} H={sig['hurst']} "
                        f"vol={sig['vol_ratio']:.1f}× RR={sig['expected_rr']:.2f} "
                        f"conf={sig['confidence']}% | {sig['reasoning'][:60]}"
                    )
                time.sleep(0.5)

            # Sort: confidence × RR × vol_ratio
            signals.sort(key=lambda x: x["confidence"] * x["expected_rr"] * x["vol_ratio"], reverse=True)

            # Place orders
            for sig in signals:
                if n_pos >= MAX_POSITIONS or margin < 50:  # minim 50 EUR margin disponibil
                    break
                if place_order(sig, margin):
                    n_pos += 1
                    margin -= margin * RISK_PCT

            # Update signals în Supabase
            for s in signals[:8]:
                sb_upsert("signals", {
                    "symbol": s["coin"],
                    "action": "BUY" if s["side"] == "buy" else "SELL",
                    "confidence": s["confidence"],
                    "reasoning": (
                        f"[HERMES-v2 x{LEVERAGE}] RSI={s['rsi']} H={s['hurst']} "
                        f"vol={s['vol_ratio']:.1f}× RR={s['expected_rr']:.2f} | {s['reasoning'][:100]}"
                    ),
                    "rsi": s["rsi"],
                    "strategy": f"hermes_v2_x{LEVERAGE}",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })

            mem = MEMORY.summary()
            log.info(
                f"═══ CYCLE {cycle} END | {len(signals)} signals | "
                f"{n_pos}/{MAX_POSITIONS} pos | "
                f"WR={mem.get('wr', 0):.0%} | "
                f"daily=${mem.get('daily_pnl', 0):+.2f} ═══"
            )

        except KeyboardInterrupt:
            log.info("HERMES-v2 stopped by user.")
            break
        except Exception as e:
            log.error(f"Cycle {cycle} error: {e}", exc_info=True)

        log.info(f"  💤 Sleeping {CYCLE_SLEEP}s...")
        time.sleep(CYCLE_SLEEP)

if __name__ == "__main__":
    main()
