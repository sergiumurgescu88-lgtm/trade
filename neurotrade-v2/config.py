import os
ALPACA_API_KEY    = "PKKUZCVZINGY6DDJTNHAKJ2XFU"
ALPACA_SECRET_KEY = "A7PVMi8pstPw5PdEeHt57G3fxHwHkVhPcu2KRXoyuG5f"
ALPACA_BASE_URL   = "https://paper-api.alpaca.markets/v2"
ALPACA_DATA_URL   = "https://data.alpaca.markets/v2"
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL            = "gemini-2.0-flash"
XAI_API_KEY  = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
XAI_MODEL    = "grok-3"
NEWSAPI_KEY  = "2dafb4c845c94b118e1b33c81efd988f"
NEWSAPI_URL  = "https://newsapi.org/v2/everything"
SUPABASE_URL = "https://qvzupovzynuqqmcmdvou.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF2enVwb3Z6eW51cXFtY21kdm91Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzIxNTMzMSwiZXhwIjoyMDg4NzkxMzMxfQ.pd9SqoI3V0Q4qLc_R64pSaF_sexqeb9MT-9vFKRETt0"
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = "7758960424"
FOREXFACTORY_RSS = "https://www.forexfactory.com/rss"
FXSTREET_RSS     = "https://www.fxstreet.com/rss/news"
DAILYFX_RSS      = "https://www.dailyfx.com/feeds/all"
INVESTING_RSS    = "https://www.investing.com/rss/news_301.rss"
MARKETPULSE_RSS  = "https://www.marketpulse.com/feed/"
STOCK_SYMBOLS = ["AAPL","MSFT","NVDA","TSLA","GOOGL","AMZN","META","AMD","NFLX","CRM","PLTR","UBER","SHOP","JPM","BAC","GS","V","MA","DIS","PYPL","INTC","MU","TSM","ASML","QQQ","SOXL","TQQQ","ARKK","SPY","SOXX","SMH","XLK","UPRO","SPXL","TECL"]
FOREX_SYMBOLS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD"]
CRYPTO_SYMBOLS = []
ALL_SYMBOLS = STOCK_SYMBOLS + CRYPTO_SYMBOLS
STARTING_CAPITAL=10000; CYCLE_MINUTES=3; SYMBOL_DELAY_SEC=3
CONFIDENCE_THRESHOLD=70; MAX_OPEN_POSITIONS=20
STOP_LOSS_PCT=0.03; TAKE_PROFIT_PCT=0.05; TRAILING_STOP_PCT=0.025
RISK_CAP_PCT=0.85; MAX_DAILY_LOSS_PCT=0.05
RSI_BUY_MAX=72; RSI_SELL_MIN=48

GEMINI_API_KEY_FALLBACK   = "AIzaSyC2HbVSn005V81vYlJxlVseL_0Ccf1uJUU"
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
ALL_SYMBOLS = STOCK_SYMBOLS + CRYPTO_SYMBOLS
LEVERAGE_ENABLED = True
DEFAULT_LEVERAGE = 10
MARGIN_CALL_LEVEL = 180
MARGIN_CRITICAL_LEVEL = 140
MAX_OPEN_CRYPTO_POSITIONS = 3
