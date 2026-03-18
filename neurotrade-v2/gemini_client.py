import os
"""
qwen_client.py — Analiza sentiment cu Qwen3.5 via NVIDIA API
Drop-in replacement pentru gemini_client.py — interfata identica
"""
import json
import logging
import requests

log = logging.getLogger("Gemini")  # pastram numele ca sa nu schimbam log-urile din bot.py

NVIDIA_KEY  = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_URL  = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "qwen/qwen3.5-122b-a10b"

_DEFAULT = {
    "action": "HOLD",
    "confidence": 0,
    "sentiment": "NEUTRAL",
    "reasoning": "Eroare analiza AI.",
    "risk": "HIGH",
    "key_factors": []
}


def _call_qwen(prompt: str) -> str:
    """Apeleaza Qwen3.5 via NVIDIA si returneaza textul brut."""
    headers = {
        "Authorization": f"Bearer {NVIDIA_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": NVIDIA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.3,
        "top_p": 0.95,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False}
    }
    r = requests.post(NVIDIA_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    # Qwen cu thinking poate returna <think>...</think> - curatam
    if "<think>" in content and "</think>" in content:
        content = content[content.rfind("</think>")+8:].strip()
    return content


def _clean_json(raw: str) -> str:
    """Extrage JSON valid din raspuns."""
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start:end+1]
    return raw


def analyze(symbol: str, news: list, price: float,
            has_open_position: bool, tech: dict) -> dict:
    """Analiza completa: stiri + context tehnic → semnal trading."""
    if news:
        news_text = "\n".join([
            f"[{n['source']}] {n['title']} — {n.get('description','')[:150]}"
            for n in news[:7]
        ])
    else:
        news_text = "Nu sunt stiri disponibile."

    rsi_val = tech.get("rsi")
    macd_cross = tech.get("macd_crossover", "none")
    ema_trend = tech.get("ema_trend", "neutral")
    tech_rec = tech.get("tech_recommendation", "NEUTRAL")
    tech_score = tech.get("tech_score", 0)

    tech_text = (
        f"RSI(14): {f'{rsi_val:.1f}' if rsi_val is not None else 'N/A'}\n"
        f"MACD crossover: {macd_cross}\n"
        f"EMA trend: {ema_trend}\n"
        f"Scor tehnic agregat: {tech_score}/3 → {tech_rec}"
    ) if rsi_val else "Indicatori tehnici indisponibili."

    position_info = "DA — detinem actiuni" if has_open_position else "NU — fara pozitie"

    prompt = f"""Esti un trader profesionist cu experienta pe bursa americana.
Ai acces la stiri recente SI indicatori tehnici pentru {symbol}.
Sarcina ta: combina analiza fundamentala (stiri) cu analiza tehnica si da un semnal precis.

═══════════════════════════════
SIMBOL: {symbol}
PRET CURENT: ${price:.2f}
POZITIE DESCHISA: {position_info}
═══════════════════════════════

📰 STIRI RECENTE:
{news_text}

📊 INDICATORI TEHNICI:
{tech_text}

Raspunde EXCLUSIV cu JSON valid (```json ... ```):
{{
  "action": "BUY" sau "SELL" sau "HOLD",
  "confidence": numar intreg 0-100,
  "sentiment": "BULLISH" sau "BEARISH" sau "NEUTRAL",
  "reasoning": "explicatie clara in romana, max 3 propozitii",
  "risk": "LOW" sau "MEDIUM" sau "HIGH",
  "key_factors": ["factor1", "factor2", "factor3"]
}}

Reguli:
- BUY: sentiment BULLISH + confirmare tehnica + confidence >= 65 + NU avem pozitie
- SELL: sentiment BEARISH + confirmare tehnica + confidence >= 65 + AVEM pozitie
- HOLD: orice situatie mixta sau neconcludenta"""

    try:
        raw = _call_qwen(prompt)
        cleaned = _clean_json(raw)
        result = json.loads(cleaned)

        action = str(result.get("action", "HOLD")).upper()
        if action not in ["BUY", "SELL", "HOLD"]:
            action = "HOLD"
        confidence = max(0, min(100, int(result.get("confidence", 0))))
        sentiment = str(result.get("sentiment", "NEUTRAL")).upper()
        if sentiment not in ["BULLISH", "BEARISH", "NEUTRAL"]:
            sentiment = "NEUTRAL"
        risk = str(result.get("risk", "HIGH")).upper()
        if risk not in ["LOW", "MEDIUM", "HIGH"]:
            risk = "HIGH"
        key_factors = result.get("key_factors", [])
        if not isinstance(key_factors, list):
            key_factors = []

        return {
            "action": action,
            "confidence": confidence,
            "sentiment": sentiment,
            "reasoning": str(result.get("reasoning", ""))[:400],
            "risk": risk,
            "key_factors": key_factors[:3]
        }

    except json.JSONDecodeError as e:
        log.error(f"Qwen JSON parse error [{symbol}]: {e}")
        return {**_DEFAULT, "reasoning": "Eroare parsare JSON."}
    except Exception as e:
        log.error(f"Qwen error [{symbol}]: {e}")
        return {**_DEFAULT, "reasoning": f"Eroare: {str(e)[:100]}"}


def test_connection() -> bool:
    try:
        r = _call_qwen("Raspunde doar cu: OK")
        return "OK" in r.upper()
    except Exception as e:
        log.error(f"Qwen test failed: {e}")
        return False
