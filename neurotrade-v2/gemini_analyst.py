import json, logging, os, requests, time
log = logging.getLogger("Gemini")

# Citim din .env (incarcat de run.sh via set -a)
NVIDIA_KEY   = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_URL   = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1") + "/chat/completions"
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "qwen/qwen3.5-122b-a10b")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
XAI_KEY      = os.getenv("XAI_API_KEY", "")
XAI_URL      = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1") + "/chat/completions"
XAI_MODEL    = os.getenv("XAI_MODEL", "grok-3-latest")

_DEFAULT = {
    "action": "HOLD", "confidence": 0, "sentiment": "NEUTRAL",
    "reasoning": "Eroare analiza AI.", "risk": "HIGH", "key_factors": []
}

def _call_nvidia(prompt):
    if not NVIDIA_KEY:
        raise Exception("No NVIDIA key")
    r = requests.post(NVIDIA_URL,
        headers={"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"},
        json={"model": NVIDIA_MODEL, "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 512, "temperature": 0.3, "stream": False,
              "chat_template_kwargs": {"enable_thinking": False}},
        timeout=25)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    if "<think>" in content and "</think>" in content:
        content = content[content.rfind("</think>")+8:].strip()
    return content

def _call_gemini(prompt):
    if not GEMINI_KEY:
        raise Exception("No Gemini key")
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.3, "maxOutputTokens": 512}},
        timeout=20)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

def _call_xai(prompt):
    if not XAI_KEY:
        raise Exception("No xAI key")
    r = requests.post(XAI_URL,
        headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
        json={"model": XAI_MODEL, "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 512, "temperature": 0.3},
        timeout=20)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def _clean_json(raw):
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                raw = part
                break
    s, e = raw.find("{"), raw.rfind("}")
    return raw[s:e+1] if s != -1 and e > s else raw

def _parse(raw):
    result = json.loads(_clean_json(raw))
    action = str(result.get("action", "HOLD")).upper()
    if action not in ["BUY", "SELL", "HOLD"]:
        action = "HOLD"
    return {
        "action": action,
        "confidence": max(0, min(100, int(result.get("confidence", 0)))),
        "sentiment": str(result.get("sentiment", "NEUTRAL")).upper(),
        "reasoning": str(result.get("reasoning", ""))[:400],
        "risk": str(result.get("risk", "HIGH")).upper(),
        "key_factors": result.get("key_factors", [])[:3] if isinstance(result.get("key_factors"), list) else []
    }

def analyze(symbol: str, price: float, tech: dict, news: list, asset_type: str = "stock") -> dict:
    if not isinstance(tech, dict):
        tech = {"rsi": 50, "macd_crossover": "none", "ema_trend": "neutral", "tech_score": 0}
    if not isinstance(news, list):
        news = []

    news_text = "\n".join([
        f"[{n['source']}] {n['title']}"
        for n in news[:5] if isinstance(n, dict) and n.get('title')
    ]) or "Nu sunt stiri."

    prompt = f"""Trading signal {symbol} @ ${price:.2f}
RSI={tech.get('rsi',50)} MACD={tech.get('macd_crossover','none')} EMA={tech.get('ema_trend','neutral')} Score={tech.get('tech_score',0)}
STIRI: {news_text}
JSON ONLY: {{"action":"BUY/SELL/HOLD","confidence":0-100,"sentiment":"BULLISH/BEARISH/NEUTRAL","reasoning":"2 propozitii","risk":"LOW/MEDIUM/HIGH","key_factors":["f1","f2"]}}"""

    # Incercam in ordine: NVIDIA → xAI → Gemini
    callers = []
    if NVIDIA_KEY:
        callers.append(("NVIDIA", _call_nvidia))
    if XAI_KEY:
        callers.append(("xAI", _call_xai))
    if GEMINI_KEY:
        callers.append(("Gemini", _call_gemini))

    for name, caller in callers:
        try:
            raw = caller(prompt)
            result = _parse(raw)
            log.debug(f"AI [{name}] {symbol}: {result['action']} {result['confidence']}%")
            return result
        except Exception as e:
            log.warning(f"AI {name} failed [{symbol}]: {e}")
            time.sleep(1)

    return {**_DEFAULT, "reasoning": "Toate modelele AI au esuat."}

def test_connection():
    try:
        if NVIDIA_KEY:
            return "OK" in _call_nvidia("Reply with: OK").upper()
        if GEMINI_KEY:
            return "OK" in _call_gemini("Reply with: OK").upper()
    except:
        pass
    return False
