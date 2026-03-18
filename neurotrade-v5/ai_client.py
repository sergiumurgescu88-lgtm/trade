"""
ai_client.py — NeuroTrade V5
AI Chain: Gemini 2.0 Flash → xAI Grok → Qwen NVIDIA
"""
import json
import logging
import time
import requests

log = logging.getLogger("AI")

from config import (
    GEMINI_API_KEY, GEMINI_API_KEY_FALLBACK, GEMINI_MODEL,
GEMINI_API_KEY_FALLBACK2,
    XAI_API_KEY, XAI_BASE_URL, XAI_MODEL,
    NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_MODEL,
)

try:
    from google import genai
    _USE_NEW_SDK = True
except ImportError:
    import google.generativeai as genai_old
    _USE_NEW_SDK = False

_DEFAULT = {
    "action": "HOLD", "confidence": 0,
    "sentiment": "NEUTRAL", "reasoning": "Eroare analiza AI.",
    "risk": "HIGH", "key_factors": []
}

def _call_gemini(prompt):
    keys = [k for k in [GEMINI_API_KEY, GEMINI_API_KEY_FALLBACK, GEMINI_API_KEY_FALLBACK2] if k]
    for i, key in enumerate(keys):
        try:
            if _USE_NEW_SDK:
                client = genai.Client(api_key=key)
                r = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
                return r.text.strip()
            else:
                genai_old.configure(api_key=key)
                return genai_old.GenerativeModel(GEMINI_MODEL).generate_content(prompt).text.strip()
        except Exception as e:
            if "429" in str(e).lower() and i < len(keys)-1:
                time.sleep(2); continue
            raise
    raise Exception("Gemini rate limit")

def _call_xai(prompt):
    r = requests.post(f"{XAI_BASE_URL}/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {XAI_API_KEY}"},
        json={"model": XAI_MODEL, "messages": [
            {"role": "system", "content": "You are a professional trader. Respond only with valid JSON."},
            {"role": "user", "content": prompt}
        ], "temperature": 0.1, "max_tokens": 600}, timeout=20)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"xAI error: {r.status_code}")

def _call_qwen(prompt):
    r = requests.post(f"{NVIDIA_BASE_URL}/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {NVIDIA_API_KEY}"},
        json={"model": NVIDIA_MODEL, "messages": [
            {"role": "system", "content": "You are a professional trader. Respond only with valid JSON."},
            {"role": "user", "content": prompt}
        ], "temperature": 0.1, "max_tokens": 600}, timeout=25)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Qwen error: {r.status_code}")

def _call_ai_chain(prompt):
    for name, fn in [("Qwen", _call_qwen), ("xAI", _call_xai), ("Gemini", _call_gemini)]:
        try:
            result = fn(prompt)
            log.debug(f"AI raspuns de la {name}")
            return result
        except Exception as e:
            log.warning(f"{name} failed: {e}")
    raise Exception("Toate AI-urile au esuat")

def _clean_json(raw):
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"): part = part[4:].strip()
            if part.startswith("{"): return part
    return raw

def analyze(symbol, news, price, has_position, tech, market_type="stock"):
    news_text = "\n".join([
        f"[{n['source']}] {n['title']} — {n.get('description','')[:120]}"
        for n in news[:7]
    ]) if news else "No news available."

    rsi_val = tech.get("rsi")
    tech_text = (
        f"RSI(14): {f'{rsi_val:.1f}' if rsi_val else 'N/A'}\n"
        f"MACD: {tech.get('macd_crossover','none')}\n"
        f"EMA: {tech.get('ema_trend','neutral')}\n"
        f"Score: {tech.get('tech_score',0)}/4 → {tech.get('tech_recommendation','N/A')}"
    ) if rsi_val else "Indicatori tehnici indisponibili."

    market_ctx = {"stock":"US Stock","etf":"US ETF","crypto":"Crypto 24/7","forex":"Forex"}.get(market_type,"Market")
    pos_info = "YES — detinem" if has_position else "NO — fara pozitie"

    prompt = f"""Esti un trader agresiv profesionist pe {market_ctx}.
SIMBOL: {symbol} | PRET: ${price:.4f} | POZITIE: {pos_info}

STIRI RECENTE:
{news_text}

INDICATORI TEHNICI:
{tech_text}

Raspunde EXCLUSIV cu JSON valid:
{{
  "action": "BUY" sau "SELL" sau "HOLD",
  "confidence": numar 0-100,
  "sentiment": "BULLISH" sau "BEARISH" sau "NEUTRAL",
  "reasoning": "explicatie in romana max 3 propozitii",
  "risk": "LOW" sau "MEDIUM" sau "HIGH",
  "key_factors": ["factor1", "factor2", "factor3"]
}}
Reguli: BUY daca sentiment BULLISH + conf>=52 + fara pozitie. SELL daca BEARISH + conf>=52 + avem pozitie. Fii agresiv - mai multe trades = mai mult profit."""

    try:
        result = json.loads(_clean_json(_call_ai_chain(prompt)))
        action = str(result.get("action","HOLD")).upper()
        if action not in ["BUY","SELL","HOLD"]: action = "HOLD"
        confidence = max(0, min(100, int(result.get("confidence",0))))
        sentiment = str(result.get("sentiment","NEUTRAL")).upper()
        if sentiment not in ["BULLISH","BEARISH","NEUTRAL"]: sentiment = "NEUTRAL"
        risk = str(result.get("risk","HIGH")).upper()
        if risk not in ["LOW","MEDIUM","HIGH"]: risk = "HIGH"
        kf = result.get("key_factors",[])
        return {"action":action,"confidence":confidence,"sentiment":sentiment,
                "reasoning":str(result.get("reasoning",""))[:400],"risk":risk,
                "key_factors":kf[:3] if isinstance(kf,list) else []}
    except Exception as e:
        log.error(f"AI error [{symbol}]: {e}")
        return {**_DEFAULT, "reasoning": str(e)[:100]}

def test_connection():
    try:
        return "OK" in _call_gemini("Respond with: OK").upper()
    except Exception:
        try:
            return "OK" in _call_xai("Respond with: OK").upper()
        except Exception:
            return False
