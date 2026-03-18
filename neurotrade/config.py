import os
ALPACA_API_KEY    = "PKQVHDB4MSVHAUGYPZDIM7MFWN"
ALPACA_SECRET_KEY = "CeL5phw5VBqJzSY7bphxTr2cMTtorBWhjDRNs5jwaGRg"
ALPACA_BASE_URL   = "https://paper-api.alpaca.markets/v2"
ALPACA_DATA_URL   = "https://data.alpaca.markets/v2"
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL            = "gemini-2.0-flash"
XAI_API_KEY  = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
XAI_MODEL    = "grok-3"
NEWSAPI_KEY  = "2dafb4c845c94b118e1b33c81efd988f"
NEWSAPI_URL  = "https://newsapi.org/v2/everything"
SUPABASE_URL = "https://lgrllhsfgvnngtmlwwug.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxncmxsaHNmZ3Zubmd0bWx3d3VnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU5NTM4NiwiZXhwIjoyMDg3MTcxMzg2fQ.zXnxQ9C6xuOWibkmXRcVelUKmuQNqNxFvv4d7bp2ZHw"
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = "7758960424"
FOREXFACTORY_RSS = "https://www.forexfactory.com/rss"
FXSTREET_RSS     = "https://www.fxstreet.com/rss/news"
DAILYFX_RSS      = "https://www.dailyfx.com/feeds/all"
INVESTING_RSS    = "https://www.investing.com/rss/news_301.rss"
MARKETPULSE_RSS  = "https://www.marketpulse.com/feed/"
SYMBOLS = ["AAPL","MSFT","NVDA","TSLA","GOOGL","AMZN","META","AMD","NFLX","CRM","SNOW","PLTR","UBER","SHOP","JPM","BAC","GS","V","MA","DIS","PYPL","INTC","MU","ASML","TSM"]
ETF_SYMBOLS = ["QQQ","ARKK","SOXL","TQQQ","XLK","SOXX","SMH","SPY","IWM","UPRO","SPXL","TECL","FNGU"]
FOREX_SYMBOLS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD"]
ALL_SYMBOLS   = SYMBOLS + ETF_SYMBOLS
MARKET_INDEX  = "SPY"
CYCLE_MINUTES=3
SYMBOL_DELAY_SEC     = 4
STARTING_CAPITAL     = 10000
CONFIDENCE_THRESHOLD=70
RSI_BUY_MAX=72
RSI_SELL_MIN=48
RSI_PERIOD           = 14
MACD_FAST=12; MACD_SLOW=26; MACD_SIGNAL=9; EMA_FAST=20; EMA_SLOW=50; HISTORY_BARS=60
POSITION_SIZING = {
    (48, 54): 0.07,
    (55, 64): 0.10,
    (65, 74): 0.14,
    (75, 84): 0.18,
    (85, 94): 0.22,
    (95, 100): 0.28,
}
MAX_POSITION_USD=500; MIN_POSITION_USD=70; MAX_OPEN_POSITIONS=20
STOP_LOSS_PCT=0.03; TAKE_PROFIT_PCT=0.05; TRAILING_STOP_PCT=0.025
SAFE_MODE_DROP_PCT=0.025; DAILY_LOSS_LIMIT_PCT=0.04; PORTFOLIO_RISK_CAP=0.92
XAI_API_KEY  = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
XAI_MODEL    = "grok-3"

# ═══════════════════════════════════════════════════════════════
#  KRAKEN x10 LEVERAGE + SENTIMENT
# ═══════════════════════════════════════════════════════════════
KRAKEN_API_KEY    = "wA7o9CcsFeNdG0TkdEf+cp502gBNM3WX28pV8IRWKPEMNUcsR9t3/nGE"
KRAKEN_SECRET_KEY = "t3gcZQv0pO35F1OOW0/ipvV5DC/gs7cLTKLn1hDwCgs7JZ+t4pyodqyUvFe9jwqj9K0MpZPFYZao9czLl8VjKURT"
KRAKEN_BASE_URL   = "https://api.kraken.com"

CRYPTO_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "DOGE/USDT"]
ALL_SYMBOLS = SYMBOLS + ETF_SYMBOLS + CRYPTO_SYMBOLS

LEVERAGE_ENABLED        = True
DEFAULT_LEVERAGE        = 10
MAX_LEVERAGE            = 10
CRYPTO_STOP_LOSS_PCT    = 0.015
CRYPTO_TAKE_PROFIT_PCT  = 0.04
CRYPTO_TRAILING_PCT     = 0.02
CRYPTO_MAX_POSITION_PCT = 0.03
CRYPTO_CONFIDENCE_MIN   = 75
MARGIN_CALL_LEVEL       = 180
MARGIN_CRITICAL_LEVEL   = 140
MAX_OPEN_CRYPTO_POSITIONS = 3
SENTIMENT_ENABLED       = True
SENTIMENT_MIN_CONFIDENCE = 70
SENTIMENT_MIN_SCORE     = 0.35
TELEGRAM_ALERTS_ENABLED = True

# ═══════════════════════════════════════════════════════════════
#  CRYPTO APIs (Missing - Added Now)
# ═══════════════════════════════════════════════════════════════
CRYPTOPANIC_KEY   = "59c682c8661c29f5deba8df58e40b754751b80c4"
CRYPTOPANIC_URL   = "https://cryptopanic.com/api/developer/v1"
NEWSAPI_KEY       = "905f5a50045a48e3a4a7388fd6d50ac8"
NEWSAPI_URL       = "https://newsapi.org/v2/everything"
COINGECKO_API_KEY = "CG-pZzDUZHhVRPkwvaCuHsRxwW6"
XAI_API_KEY       = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL      = "https://api.x.ai/v1"
XAI_MODEL         = "grok-2-latest"

# KRAKEN - Need YOUR real keys from kraken.com
KRAKEN_API_KEY    = "YOUR_KRAKEN_API_KEY_HERE"
KRAKEN_SECRET_KEY = "YOUR_KRAKEN_SECRET_KEY_HERE"
KRAKEN_BASE_URL   = "https://api.kraken.com"
