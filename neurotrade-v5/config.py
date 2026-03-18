import os
ALPACA_API_KEY    = "PKQ3SX4CS5OY2BVDR4AHH3YI6L"
ALPACA_SECRET_KEY = "5jQPtP9jaHDbpdCRDSRgKGe9o1bXuNVnzYTa4Vd4nogN"
ALPACA_BASE_URL   = "https://paper-api.alpaca.markets/v2"
ALPACA_DATA_URL   = "https://data.alpaca.markets/v2"
KRAKEN_API_KEY    = "GyY3Ceh003tkHnVAtj7f5mbioGdsV6DtN7mNqEM7+pFiz+0QYGnwjbXv"
KRAKEN_SECRET_KEY = "VYVl/I1QdkQmrfx0m31SOLo4/V2XYYvkOP91eF2vWUGACuGPuM4m2eEeaZtkHdMNKWrk/ao9RShCn4Wi3Ogf+VAR"
KRAKEN_BASE_URL   = "https://demo-futures.kraken.com"
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL            = "gemini-2.0-flash"
XAI_API_KEY  = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
XAI_MODEL    = "grok-3"
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "qwen/qwen3.5-122b-a10b"
NEWSAPI_KEY       = "905f5a50045a48e3a4a7388fd6d50ac8"
NEWSAPI_URL       = "https://newsapi.org/v2/everything"
COINGECKO_API_KEY = "CG-pZzDUZHhVRPkwvaCuHsRxwW6"
CRYPTOPANIC_KEY   = "59c682c8661c29f5deba8df58e40b754751b80c4"
CRYPTOPANIC_URL   = "https://cryptopanic.com/api/developer/v2"
FOREXFACTORY_RSS = "https://www.forexfactory.com/rss"
FXSTREET_RSS     = "https://www.fxstreet.com/rss/news"
DAILYFX_RSS      = "https://www.dailyfx.com/feeds/all"
INVESTING_RSS    = "https://www.investing.com/rss/news_301.rss"
MARKETPULSE_RSS  = "https://www.marketpulse.com/feed/"
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = "7758960424"
SUPABASE_URL = "https://zawhuoshdefyznqmjphh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inphd2h1b3NoZGVmeXpucW1qcGhoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzMyNDU3NywiZXhwIjoyMDg4OTAwNTc3fQ.WK6J0-FIBndW1nb-XgS60bunFxwQFN2K3kzQ7E9X0g4"
STOCK_SYMBOLS = ["AAPL","MSFT","NVDA","TSLA","GOOGL","AMZN","META","AMD","NFLX","CRM","PLTR","UBER","SHOP","SNOW","JPM","BAC","GS","V","MA","DIS","PYPL","INTC","MU","TSM","ASML","ORCL","ADBE","QCOM"]
ETF_SYMBOLS    = ["QQQ","SOXL","TQQQ","ARKK","XLK","SOXX","SMH","SPY","IWM","UPRO","SPXL","TECL","FNGU"]
CRYPTO_SYMBOLS = []
FOREX_SYMBOLS  = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD"]
ALL_SYMBOLS    = STOCK_SYMBOLS + ETF_SYMBOLS
MARKET_INDEX   = "SPY"
CYCLE_MINUTES=3; SYMBOL_DELAY_SEC=2; STARTING_CAPITAL=10000
CONFIDENCE_THRESHOLD=70; RSI_BUY_MAX=65; RSI_SELL_MIN=48; RSI_PERIOD=14
MACD_FAST=12; MACD_SLOW=26; MACD_SIGNAL=9; EMA_FAST=9; EMA_SLOW=21; HISTORY_BARS=60
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
SAFE_MODE_DROP_PCT=0.02; DAILY_LOSS_LIMIT_PCT=0.04; PORTFOLIO_RISK_CAP=0.92
GEMINI_API_KEY_FALLBACK   = "AIzaSyC2HbVSn005V81vYlJxlVseL_0Ccf1uJUU"
GEMINI_API_KEY_FALLBACK2  = "AIzaSyAVh6WXZl3bZZjY89Qe2VCO9eb5hsLqSfI"

# ═══════════════════════════════════════════════════════════════
#  KRAKEN x10 LEVERAGE + SENTIMENT
# ═══════════════════════════════════════════════════════════════
# KRAKEN_API_KEY    = "wA7o9CcsFeNdG0TkdEf+cp502gBNM3WX28pV8IRWKPEMNUcsR9t3/nGE"
# KRAKEN_SECRET_KEY = "t3gcZQv0pO35F1OOW0/ipvV5DC/gs7cLTKLn1hDwCgs7JZ+t4pyodqyUvFe9jwqj9K0MpZPFYZao9czLl8VjKURT"
# KRAKEN_BASE_URL   = "https://api.kraken.com"
LEVERAGE_ENABLED = True
DEFAULT_LEVERAGE = 10
MARGIN_CALL_LEVEL = 180
MARGIN_CRITICAL_LEVEL = 140
MAX_OPEN_CRYPTO_POSITIONS = 3

# ═══════════════════════════════════════════════════════════════
#  BINANCE TESTNET (Crypto Demo Trading)
# ═══════════════════════════════════════════════════════════════
BINANCE_API_KEY    = "mJUa3UJy5oQocSDbubuXUsWK5S02YIsQ4wDx3BxYvUsnYXhpZ61pFtBfy2MCfClm"
BINANCE_SECRET_KEY = "8fXXbxW3Or9bsTcj36uIJDef4d5xmXoT50ELEg22Ne4lS6AYy3ND7GnsZMms53uD"
BINANCE_BASE_URL   = "https://testnet.binance.vision/api/v3"
BINANCE_TESTNET    = True

# Crypto symbols for demo trading
CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOGEUSDT"]

# Leverage settings for crypto demo
LEVERAGE_ENABLED = True
DEFAULT_LEVERAGE = 10
CRYPTO_STOP_LOSS_PCT = 0.015
CRYPTO_TAKE_PROFIT_PCT = 0.04
CRYPTO_TRAILING_PCT = 0.02
MAX_OPEN_CRYPTO_POSITIONS = 3
