"""
news_client.py — NeuroTrade V5
9 surse: NewsAPI, Yahoo, Google, Finviz, Benzinga, MarketWatch, SeekingAlpha, CNBC + CryptoPanic + xAI
"""
import requests, logging, xml.etree.ElementTree as ET, re, json
from datetime import datetime, timezone
from config import NEWSAPI_KEY, NEWSAPI_URL, COINGECKO_API_KEY, CRYPTOPANIC_KEY, CRYPTOPANIC_URL, XAI_API_KEY, XAI_BASE_URL, XAI_MODEL

log = logging.getLogger("News")

QUERY_MAP = {
    "AAPL":"Apple Inc stock","MSFT":"Microsoft stock","NVDA":"NVIDIA AI chip stock",
    "TSLA":"Tesla stock","GOOGL":"Google Alphabet stock","AMZN":"Amazon AWS stock",
    "META":"Meta Facebook stock","AMD":"AMD semiconductor stock","NFLX":"Netflix stock",
    "PLTR":"Palantir AI stock","COIN":"Coinbase crypto stock","MSTR":"MicroStrategy Bitcoin",
    "QQQ":"NASDAQ QQQ ETF","SOXL":"semiconductor ETF","TQQQ":"TQQQ leveraged ETF",
    "BTC/USDT":"Bitcoin BTC crypto","ETH/USDT":"Ethereum ETH crypto",
    "SOL/USDT":"Solana SOL crypto","BNB/USDT":"Binance BNB crypto",
    "DOGE/USDT":"Dogecoin DOGE crypto","EURUSD":"EUR USD forex","GBPUSD":"GBP USD forex",
}
COMPANY_MAP = {
    "AAPL":"Apple","MSFT":"Microsoft","NVDA":"NVIDIA","TSLA":"Tesla",
    "GOOGL":"Google","AMZN":"Amazon","META":"Meta","AMD":"AMD","NFLX":"Netflix",
}
CRYPTO_ID_MAP = {
    "BTC/USDT":"bitcoin","ETH/USDT":"ethereum","SOL/USDT":"solana",
    "BNB/USDT":"binancecoin","DOGE/USDT":"dogecoin","ADA/USDT":"cardano",
}
_newsapi_failed = False

def _newsapi(symbol, count=5):
    global _newsapi_failed
    if _newsapi_failed: return []
    try:
        r = requests.get(NEWSAPI_URL, params={"q":QUERY_MAP.get(symbol,f"{symbol} stock"),
            "language":"en","sortBy":"publishedAt","pageSize":count,"apiKey":NEWSAPI_KEY}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "error": _newsapi_failed = True; return []
            return [{"title":a["title"],"description":(a.get("description") or "")[:200],
                "source":a.get("source",{}).get("name","NewsAPI"),"weight":1.2}
                for a in data.get("articles",[]) if a.get("title") and "[Removed]" not in a["title"]][:count]
        elif r.status_code in [401,429]: _newsapi_failed = True
    except Exception as e: log.debug(f"NewsAPI {symbol}: {e}")
    return []

def _yahoo(symbol, count=4):
    try:
        r = requests.get(f"https://finance.yahoo.com/rss/headline?s={symbol}",
            headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code != 200: return []
        root = ET.fromstring(r.content)
        return [{"title":item.findtext("title","").strip(),"description":"","source":"Yahoo Finance","weight":1.1}
            for item in root.findall(".//item")[:count] if item.findtext("title","").strip()]
    except Exception as e: log.debug(f"Yahoo {symbol}: {e}")
    return []

def _google(symbol, count=3):
    try:
        q = QUERY_MAP.get(symbol, f"{symbol} stock")
        r = requests.get(f"https://news.google.com/rss/search?q={requests.utils.quote(q)}&hl=en-US&gl=US&ceid=US:en",
            headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code != 200: return []
        root = ET.fromstring(r.content)
        return [{"title":item.findtext("title","").strip(),"description":"","source":"Google News","weight":1.0}
            for item in root.findall(".//item")[:count] if item.findtext("title","").strip()]
    except Exception as e: log.debug(f"Google {symbol}: {e}")
    return []

def _benzinga(symbol, count=3):
    try:
        r = requests.get(f"https://www.benzinga.com/stock/{symbol.lower()}/feed",
            headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code != 200: return []
        root = ET.fromstring(r.content)
        sym_l = symbol.lower(); co = COMPANY_MAP.get(symbol,symbol).lower()
        result = []
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title","").strip()
            if (sym_l in title.lower() or co.split()[0] in title.lower()):
                result.append({"title":title,"description":"","source":"Benzinga","weight":1.3})
            if len(result) >= count: break
        return result
    except Exception as e: log.debug(f"Benzinga {symbol}: {e}")
    return []

def _cnbc(symbol, count=3):
    try:
        sym_l = symbol.lower(); co = COMPANY_MAP.get(symbol,symbol).lower()
        result = []
        for feed in ["https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"]:
            r = requests.get(feed, headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
            if r.status_code != 200: continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:15]:
                title = item.findtext("title","").strip()
                if sym_l in title.lower() or co.split()[0] in title.lower():
                    result.append({"title":title,"description":"","source":"CNBC","weight":1.4})
                if len(result) >= count: return result
        return result
    except Exception as e: log.debug(f"CNBC {symbol}: {e}")
    return []

def _cryptopanic(symbol, count=5):
    ticker = symbol.split("/")[0] if "/" in symbol else symbol
    try:
        r = requests.get(CRYPTOPANIC_URL+"/posts/", params={
            "auth_token":CRYPTOPANIC_KEY,"currencies":ticker,"kind":"news","public":"true"}, timeout=10)
        if r.status_code == 200:
            return [{"title":i["title"],"description":"","source":"CryptoPanic","weight":1.5}
                for i in r.json().get("results",[])[:count] if i.get("title")]
    except Exception as e: log.debug(f"CryptoPanic {symbol}: {e}")
    return []

def _xai_news(symbol, count=3):
    try:
        q = QUERY_MAP.get(symbol, f"{symbol} market")
        prompt = f"Give me {count} most recent news headlines about {q} from last 24h. JSON array with: title, summary, sentiment. Only JSON."
        r = requests.post(f"{XAI_BASE_URL}/chat/completions",
            headers={"Content-Type":"application/json","Authorization":f"Bearer {XAI_API_KEY}"},
            json={"model":XAI_MODEL,"messages":[
                {"role":"system","content":"Return only valid JSON array."},
                {"role":"user","content":prompt}
            ],"temperature":0.1,"max_tokens":500}, timeout=15)
        if r.status_code != 200: return []
        content = r.json()["choices"][0]["message"]["content"].strip()
        if "```" in content:
            for part in content.split("```"):
                if "[" in part: content = part.replace("json","").strip(); break
        articles = json.loads(content)
        return [{"title":a["title"],"description":a.get("summary","")[:200],
            "source":"xAI Grok (live)","weight":1.6}
            for a in articles[:count] if a.get("title")]
    except Exception as e: log.debug(f"xAI news {symbol}: {e}")
    return []

def get_news(symbol, market_type="stock"):
    is_crypto = market_type == "crypto" or "/" in symbol
    is_forex = market_type == "forex"

    if is_crypto:
        sources = [("CryptoPanic", lambda: _cryptopanic(symbol,5)),
                   ("xAI", lambda: _xai_news(symbol,3)),
                   ("NewsAPI", lambda: _newsapi(symbol,3)),
                   ("Google", lambda: _google(symbol,3))]
    elif is_forex:
        sources = [("xAI",          lambda: _xai_news(symbol,5)),
                   ("FXStreet",     lambda: _fxstreet(symbol,4)),
                   ("DailyFX",      lambda: _dailyfx(symbol,4)),
                   ("ForexFactory", lambda: _forexfactory(symbol,3)),
                   ("Investing",    lambda: _investing_forex(symbol,3)),
                   ("NewsAPI",      lambda: _newsapi(symbol,3)),
                   ("Google",       lambda: _google(symbol,2))]
    else:
        sources = [("xAI", lambda: _xai_news(symbol,3)),
                   ("NewsAPI", lambda: _newsapi(symbol,4)),
                   ("CNBC", lambda: _cnbc(symbol,3)),
                   ("Benzinga", lambda: _benzinga(symbol,3)),
                   ("Yahoo", lambda: _yahoo(symbol,4)),
                   ("Google", lambda: _google(symbol,2))]

    all_articles = []; sources_log = []
    for name, fn in sources:
        try:
            arts = fn()
            if arts: all_articles.extend(arts); sources_log.append(f"{len(arts)} {name}")
        except Exception as e: log.debug(f"{name} error: {e}")

    seen = set(); combined = []
    for a in all_articles:
        key = a["title"][:40].lower().strip()
        if key not in seen and len(key) > 5:
            seen.add(key); combined.append(a)

    combined.sort(key=lambda x: x.get("weight",1.0), reverse=True)
    log.info(f"News {symbol}: {len(combined)} stiri ({', '.join(sources_log) if sources_log else 'niciuna'})")
    return combined[:10]

def test_connection():
    try:
        r = requests.get("https://finance.yahoo.com/rss/headline?s=AAPL",
            headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        return r.status_code == 200
    except: return False

# ─── FOREX NEWS SOURCES ───────────────────────────────────────
from config import FOREXFACTORY_RSS, FXSTREET_RSS, DAILYFX_RSS, INVESTING_RSS, MARKETPULSE_RSS

FOREX_PAIR_MAP = {
    "EURUSD":("EUR","USD","euro dollar"),"GBPUSD":("GBP","USD","pound dollar"),
    "USDJPY":("USD","JPY","dollar yen"),"AUDUSD":("AUD","USD","australian dollar"),
    "USDCAD":("USD","CAD","dollar canadian"),"USDCHF":("USD","CHF","dollar franc"),
    "NZDUSD":("NZD","USD","new zealand dollar"),
}

def _fxstreet(symbol, count=4):
    c1,c2,kw = FOREX_PAIR_MAP.get(symbol,(symbol[:3],symbol[3:],symbol.lower()))
    try:
        r = requests.get(FXSTREET_RSS, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code != 200: return []
        root = ET.fromstring(r.content)
        result = []
        for item in root.findall(".//item")[:30]:
            title = item.findtext("title","").strip()
            if c1.lower() in title.lower() or c2.lower() in title.lower() or kw in title.lower():
                result.append({"title":title,"description":"","source":"FXStreet","weight":1.5})
            if len(result) >= count: break
        return result
    except Exception as e: log.debug(f"FXStreet {symbol}: {e}")
    return []

def _dailyfx(symbol, count=4):
    c1,c2,kw = FOREX_PAIR_MAP.get(symbol,(symbol[:3],symbol[3:],symbol.lower()))
    try:
        r = requests.get(DAILYFX_RSS, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code != 200: return []
        root = ET.fromstring(r.content)
        result = []
        for item in root.findall(".//item")[:30]:
            title = item.findtext("title","").strip()
            if c1.lower() in title.lower() or c2.lower() in title.lower():
                result.append({"title":title,"description":"","source":"DailyFX","weight":1.5})
            if len(result) >= count: break
        return result
    except Exception as e: log.debug(f"DailyFX {symbol}: {e}")
    return []

def _forexfactory(symbol, count=3):
    c1,c2,_ = FOREX_PAIR_MAP.get(symbol,(symbol[:3],symbol[3:],symbol.lower()))
    try:
        r = requests.get(FOREXFACTORY_RSS, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code != 200: return []
        root = ET.fromstring(r.content)
        result = []
        for item in root.findall(".//item")[:20]:
            title = item.findtext("title","").strip()
            if c1.lower() in title.lower() or c2.lower() in title.lower() or "forex" in title.lower():
                result.append({"title":title,"description":"","source":"ForexFactory","weight":1.4})
            if len(result) >= count: break
        return result
    except Exception as e: log.debug(f"ForexFactory {symbol}: {e}")
    return []

def _investing_forex(symbol, count=3):
    c1,c2,_ = FOREX_PAIR_MAP.get(symbol,(symbol[:3],symbol[3:],symbol.lower()))
    try:
        r = requests.get(INVESTING_RSS, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code != 200: return []
        root = ET.fromstring(r.content)
        result = []
        for item in root.findall(".//item")[:20]:
            title = item.findtext("title","").strip()
            if c1.lower() in title.lower() or c2.lower() in title.lower() or "forex" in title.lower():
                result.append({"title":title,"description":"","source":"Investing.com","weight":1.4})
            if len(result) >= count: break
        return result
    except Exception as e: log.debug(f"Investing {symbol}: {e}")
    return []
