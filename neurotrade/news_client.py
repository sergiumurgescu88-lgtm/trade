import json
"""
news_client.py — NeuroTrade Bot v2
8 surse: NewsAPI, Yahoo, Google News, Finviz, Benzinga, MarketWatch, Seeking Alpha, CNBC
"""
import requests
import logging
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timezone
from config import XAI_API_KEY, XAI_BASE_URL, XAI_MODEL, NEWSAPI_KEY, NEWSAPI_URL

log = logging.getLogger("News")

QUERY_MAP = {
    "AAPL":  "Apple Inc stock earnings revenue iPhone",
    "MSFT":  "Microsoft stock earnings cloud Azure AI",
    "NVDA":  "NVIDIA GPU AI chip stock earnings datacenter",
    "TSLA":  "Tesla stock electric vehicle earnings Elon Musk",
    "GOOGL": "Google Alphabet stock advertising AI",
    "AMZN":  "Amazon stock AWS ecommerce earnings",
    "META":  "Meta Facebook stock advertising AI Zuckerberg",
    "AMD":   "AMD semiconductor chip AI stock earnings",
}

COMPANY_MAP = {
    "AAPL":  "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA",
    "TSLA":  "Tesla", "GOOGL": "Google",   "AMZN": "Amazon",
    "META":  "Meta",  "AMD":  "AMD",
}

_newsapi_failed = False

def _get_newsapi(symbol: str, count: int = 4) -> list:
    global _newsapi_failed
    if _newsapi_failed:
        return []
    try:
        r = requests.get(NEWSAPI_URL, params={
            "q": QUERY_MAP.get(symbol, f"{symbol} stock"),
            "language": "en", "sortBy": "publishedAt",
            "pageSize": count, "apiKey": NEWSAPI_KEY
        }, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "error":
                _newsapi_failed = True
                return []
            result = []
            for a in data.get("articles", []):
                title = (a.get("title") or "").strip()
                if title and "[Removed]" not in title:
                    result.append({"title": title,
                        "description": (a.get("description") or "")[:200],
                        "source": a.get("source", {}).get("name", "NewsAPI"),
                        "published": a.get("publishedAt", ""), "weight": 1.2})
            return result
        elif r.status_code in [401, 429]:
            _newsapi_failed = True
    except Exception as e:
        log.debug(f"NewsAPI {symbol}: {e}")
    return []

def _get_yahoo_rss(symbol: str, count: int = 4) -> list:
    try:
        r = requests.get(f"https://finance.yahoo.com/rss/headline?s={symbol}",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        result = []
        for item in root.findall(".//item")[:count]:
            title = (item.findtext("title") or "").strip()
            if title:
                result.append({"title": title,
                    "description": (item.findtext("description") or "")[:200],
                    "source": "Yahoo Finance",
                    "published": item.findtext("pubDate", ""), "weight": 1.1})
        return result
    except Exception as e:
        log.debug(f"Yahoo {symbol}: {e}")
    return []

def _get_google_news(symbol: str, count: int = 3) -> list:
    try:
        query = QUERY_MAP.get(symbol, f"{symbol} stock")
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        result = []
        for item in root.findall(".//item")[:count]:
            title = (item.findtext("title") or "").strip()
            if title:
                result.append({"title": title,
                    "description": (item.findtext("description") or "")[:200],
                    "source": "Google News",
                    "published": item.findtext("pubDate", ""), "weight": 1.0})
        return result
    except Exception as e:
        log.debug(f"Google News {symbol}: {e}")
    return []

def _get_benzinga(symbol: str, count: int = 3) -> list:
    try:
        url = f"https://www.benzinga.com/stock/{symbol.lower()}/feed"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        result = []
        sym_lower = symbol.lower()
        company = COMPANY_MAP.get(symbol, symbol).lower()
        for item in root.findall(".//item")[:10]:
            title = (item.findtext("title") or "").strip()
            desc  = (item.findtext("description") or "").strip()
            combined = (title + desc).lower()
            if sym_lower in combined or company.split()[0] in combined:
                result.append({"title": title, "description": desc[:200],
                    "source": "Benzinga",
                    "published": item.findtext("pubDate", ""), "weight": 1.3})
            if len(result) >= count:
                break
        return result
    except Exception as e:
        log.debug(f"Benzinga {symbol}: {e}")
    return []

def _get_marketwatch(symbol: str, count: int = 3) -> list:
    try:
        r = requests.get("https://feeds.marketwatch.com/marketwatch/realtimeheadlines/",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        sym_lower = symbol.lower()
        company = COMPANY_MAP.get(symbol, symbol).lower()
        result = []
        for item in root.findall(".//item")[:20]:
            title = (item.findtext("title") or "").strip()
            desc  = (item.findtext("description") or "").strip()
            combined = (title + desc).lower()
            if sym_lower in combined or company.split()[0] in combined:
                result.append({"title": title, "description": desc[:200],
                    "source": "MarketWatch",
                    "published": item.findtext("pubDate", ""), "weight": 1.2})
            if len(result) >= count:
                break
        return result
    except Exception as e:
        log.debug(f"MarketWatch {symbol}: {e}")
    return []

def _get_seeking_alpha(symbol: str, count: int = 3) -> list:
    try:
        url = f"https://seekingalpha.com/api/sa/combined/{symbol}.xml"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        result = []
        for item in root.findall(".//item")[:count]:
            title = (item.findtext("title") or "").strip()
            if title:
                result.append({"title": title,
                    "description": (item.findtext("description") or "")[:200],
                    "source": "Seeking Alpha",
                    "published": item.findtext("pubDate", ""), "weight": 1.3})
        return result
    except Exception as e:
        log.debug(f"Seeking Alpha {symbol}: {e}")
    return []

def _get_cnbc(symbol: str, count: int = 3) -> list:
    try:
        # CNBC RSS general finance + filtram per simbol
        feeds = [
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147",
        ]
        sym_lower = symbol.lower()
        company = COMPANY_MAP.get(symbol, symbol).lower()
        result = []
        for feed_url in feeds:
            r = requests.get(feed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:15]:
                title = (item.findtext("title") or "").strip()
                desc  = (item.findtext("description") or "").strip()
                combined = (title + desc).lower()
                if sym_lower in combined or company.split()[0] in combined:
                    result.append({"title": title, "description": desc[:200],
                        "source": "CNBC",
                        "published": item.findtext("pubDate", ""), "weight": 1.4})
                if len(result) >= count:
                    return result
        return result
    except Exception as e:
        log.debug(f"CNBC {symbol}: {e}")
    return []

def _get_finviz(symbol: str, count: int = 4) -> list:
    try:
        url = f"https://finviz.com/quote.ashx?t={symbol}"
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finviz.com/"
        }, timeout=12)
        if r.status_code != 200:
            return []
        titles = re.findall(r'class="news-link-left"[^>]*>([^<]+)</a>', r.text)
        if not titles:
            titles = re.findall(r'<a[^>]+class="tab-link-news"[^>]*>([^<]+)</a>', r.text)
        result = []
        for title in titles[:count]:
            title = title.strip()
            if title and len(title) > 10:
                result.append({"title": title, "description": "",
                    "source": "Finviz",
                    "published": datetime.now(timezone.utc).isoformat(),
                    "weight": 1.2})
        return result
    except Exception as e:
        log.debug(f"Finviz {symbol}: {e}")
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


def get_news(symbol: str) -> list:
    all_articles = []
    sources_log  = []

    source_fns = [
        ("NewsAPI",       lambda: _get_newsapi(symbol, 4)),
        ("Yahoo",         lambda: _get_yahoo_rss(symbol, 4)),
        ("Benzinga",      lambda: _get_benzinga(symbol, 3)),
        ("Finviz",        lambda: _get_finviz(symbol, 4)),
        ("Seeking Alpha", lambda: _get_seeking_alpha(symbol, 3)),
        ("MarketWatch",   lambda: _get_marketwatch(symbol, 3)),
        ("Google News",   lambda: _get_google_news(symbol, 3)),
        ("CNBC",          lambda: _get_cnbc(symbol, 3)),
    ]

    for name, fn in source_fns:
        try:
            articles = fn()
            if articles:
                all_articles.extend(articles)
                sources_log.append(f"{len(articles)} {name}")
        except Exception as e:
            log.debug(f"Sursa {name} eroare: {e}")

    seen     = set()
    combined = []
    for a in all_articles:
        key = a["title"][:40].lower().strip()
        if key not in seen and len(key) > 5:
            seen.add(key)
            combined.append(a)

    combined.sort(key=lambda x: x.get("weight", 1.0), reverse=True)

    log.info(f"News {symbol}: {len(combined)} stiri ({', '.join(sources_log) if sources_log else 'niciuna'})")

    if not combined:
        log.warning(f"{symbol}: Nicio stire — Gemini foloseste context general")

    return combined[:10]


def test_connection() -> bool:
    try:
        r = requests.get("https://finance.yahoo.com/rss/headline?s=AAPL",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if r.status_code == 200:
            return True
    except Exception:
        pass
    try:
        r = requests.get(NEWSAPI_URL, params={
            "q": "stock market", "pageSize": 1, "apiKey": NEWSAPI_KEY
        }, timeout=8)
        if r.status_code == 200 and r.json().get("status") == "ok":
            return True
    except Exception:
        pass
    return False
