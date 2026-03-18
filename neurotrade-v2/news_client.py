import feedparser, requests, logging
log = logging.getLogger("News")

def get_news(symbol: str, count: int = 6) -> list:
    news = []

    # Yahoo Finance RSS
    try:
        feed = feedparser.parse(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US")
        for e in feed.entries[:4]:
            title = e.get("title", "")
            summary = e.get("summary", "")[:150]
            if title:
                news.append({"source": "Yahoo", "title": title, "description": summary})
    except Exception as e:
        log.debug(f"Yahoo news {symbol}: {e}")

    # Google News RSS
    try:
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en")
        for e in feed.entries[:3]:
            title = e.get("title", "")
            summary = e.get("summary", "")[:150]
            if title:
                news.append({"source": "Google", "title": title, "description": summary})
    except Exception as e:
        log.debug(f"Google news {symbol}: {e}")

    # xAI Grok fallback
    if len(news) < 3:
        try:
            from config import XAI_API_KEY, XAI_BASE_URL, XAI_MODEL
            r = requests.post(f"{XAI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {XAI_API_KEY}"},
                json={"model": XAI_MODEL, "messages": [{"role": "user",
                    "content": f"Latest 3 news headlines for {symbol} stock today. Plain numbered list only."}],
                    "max_tokens": 200},
                timeout=10)
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"]
                for line in txt.strip().split("\n")[:3]:
                    line = line.strip().lstrip("123456789. ")
                    if line:
                        news.append({"source": "xAI", "title": line, "description": ""})
        except Exception as e:
            log.debug(f"xAI news {symbol}: {e}")

    return news[:count]
