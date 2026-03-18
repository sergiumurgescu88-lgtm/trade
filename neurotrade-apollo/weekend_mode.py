import requests, hashlib, hmac, base64, time as _t
import json as _j

def _w_price(symbol, log):
    pm = {"BTC":"XBTUSD","ETH":"ETHUSD","SOL":"SOLUSD"}
    try:
        r = requests.get("https://api.kraken.com/0/public/Ticker",
                         params={"pair": pm.get(symbol,symbol+"USD")}, timeout=8)
        d = r.json()
        return float(list(d["result"].values())[0]["c"][0]) if not d.get("error") else 0.0
    except Exception as e:
        log.warning(f"w_price [{symbol}]: {e}"); return 0.0

def _w_ohlc(symbol, log, bars=50):
    pm = {"BTC":"XBTUSD","ETH":"ETHUSD","SOL":"SOLUSD"}
    try:
        r = requests.get("https://api.kraken.com/0/public/OHLC",
                         params={"pair": pm.get(symbol,symbol+"USD"), "interval": 60}, timeout=10)
        d = r.json()
        return [float(c[4]) for c in list(d["result"].values())[0][-bars:]] if not d.get("error") else []
    except Exception as e:
        log.warning(f"w_ohlc [{symbol}]: {e}"); return []

def _w_rsi(prices, p=14):
    if len(prices) < p+1: return 50.0
    dl = [prices[i]-prices[i-1] for i in range(1,len(prices))]
    ag = sum(x for x in dl[-p:] if x>0)/p
    al = sum(-x for x in dl[-p:] if x<0)/p
    return round(100-(100/(1+ag/al)),2) if al else 100.0

def _w_grok(symbol, price, rsi, mom, ch24, news, XAI_KEY, XAI_BASE, XAI_MODEL, log):
    if not XAI_KEY:
        return {"action":"BUY","confidence":68,"reasoning":"oversold"} if rsi<35 else {"action":"HOLD","confidence":0,"reasoning":"no_key"}
    n = "\n".join("- "+h for h in news[:5]) or "No news."
    prompt = (
        "Crypto weekend scalp " + symbol + "/USD.\n"
        "Price: $" + f"{price:,.0f}" + " | RSI: " + f"{rsi:.0f}" +
        " | 1h: " + f"{mom:+.1f}" + "% | 24h: " + f"{ch24:+.1f}" + "%\n"
        "News:\n" + n + "\n"
        'Respond ONLY as JSON: {"action":"BUY" or "SELL" or "HOLD","confidence":0-100,"reasoning":"max 10 words"}'
    )
    try:
        r = requests.post(
            XAI_BASE+"/chat/completions",
            headers={"Authorization":"Bearer "+XAI_KEY,"Content-Type":"application/json"},
            json={"model":XAI_MODEL,"messages":[{"role":"user","content":prompt}],"max_tokens":60,"temperature":0.2},
            timeout=20)
        c = r.json()["choices"][0]["message"]["content"].strip()
        c = c.replace("```json","").replace("```","").strip()
        return _j.loads(c)
    except Exception as e:
        log.error("Grok weekend ["+symbol+"]: "+str(e))
        return {"action":"HOLD","confidence":0,"reasoning":"ai_error"}

def _kraken_sign(endpoint, post_data, nonce, KRAKEN_PRIVATE):
    from urllib.parse import urlencode
    sign_path = "/api/v3" + endpoint
    message   = (post_data + nonce + sign_path).encode("utf-8")
    sha256    = hashlib.sha256(message).digest()
    sig       = hmac.new(base64.b64decode(KRAKEN_PRIVATE), sha256, hashlib.sha512).digest()
    return base64.b64encode(sig).decode()

def _w_order(symbol, side, qty, KRAKEN_PUBLIC, KRAKEN_PRIVATE, log):
    from urllib.parse import urlencode
    pm   = {"BTC":"PF_XBTUSD","ETH":"PF_ETHUSD","SOL":"PF_SOLUSD"}
    pair = pm.get(symbol, "PF_"+symbol+"USD")
    try:
        nonce     = str(int(_t.time()*1000))
        params    = {"orderType":"mkt","symbol":pair,"side":side,"size":str(qty)}
        post_data = urlencode(params)
        sig       = _kraken_sign("/sendorder", post_data, nonce, KRAKEN_PRIVATE)
        r = requests.post(
            "https://demo-futures.kraken.com/derivatives/api/v3/sendorder",
            headers={"APIKey":KRAKEN_PUBLIC,"Nonce":nonce,"Authent":sig,
                     "Content-Type":"application/x-www-form-urlencoded"},
            data=post_data, timeout=10)
        ok = r.json().get("result") == "success"
        log.info("  weekend_order "+side+" "+str(qty)+" "+pair+": "+("OK" if ok else str(r.json())))
        return ok
    except Exception as e:
        log.error("Weekend order ["+symbol+"]: "+str(e)); return False

def run_weekend_crypto_mode(get_crypto_macro_context, tg, log,
                             XAI_KEY, XAI_BASE, XAI_MODEL,
                             NEWSAPI_KEY, NEWSAPI_URL,
                             KRAKEN_PUBLIC, KRAKEN_PRIVATE):
    W_SYMS = ["BTC","ETH","SOL"]
    W_RISK = 0.06
    W_CONF = 65
    log.info("APOLLO WEEKEND CRYPTO MODE START")
    tg("Weekend crypto mode — BTC/ETH/SOL Kraken")
    try:
        macro = get_crypto_macro_context()
        if not macro.get("macro_ok", True):
            log.info("Weekend skip — macro negativ ("+str(macro.get('btc_change',0))+")")
            return
        signals = []
        for sym in W_SYMS:
            try:
                closes = _w_ohlc(sym, log)
                if len(closes) < 20:
                    log.warning("  Weekend "+sym+": date insuficiente"); continue
                price = _w_price(sym, log)
                rsi   = _w_rsi(closes)
                mom   = ((closes[-1]/closes[-2])-1)*100 if len(closes)>=2 else 0.0
                ch24  = macro.get("btc_change",0) if sym=="BTC" else 0.0
                news  = []
                if NEWSAPI_KEY:
                    try:
                        nr = requests.get(NEWSAPI_URL,
                            params={"q":sym+" crypto","apiKey":NEWSAPI_KEY,
                                    "pageSize":5,"sortBy":"publishedAt","language":"en"},timeout=8)
                        news = [a["title"] for a in nr.json().get("articles",[])[:5]]
                    except: pass
                sig = _w_grok(sym, price, rsi, mom, ch24, news, XAI_KEY, XAI_BASE, XAI_MODEL, log)
                sig.update({"symbol":sym,"price":price,"rsi":rsi})
                log.info("  "+sym+": $"+f"{price:,.0f}"+" RSI="+f"{rsi:.0f}"+" 1h="+f"{mom:+.1f}"+
                         "% -> "+sig["action"]+" conf="+str(sig["confidence"])+" | "+sig.get("reasoning",""))
                if sig["action"] in ("BUY","SELL") and sig["confidence"] >= W_CONF:
                    signals.append(sig)
            except Exception as e:
                log.error("  Weekend "+sym+": "+str(e))
        placed = 0
        for sig in sorted(signals, key=lambda x: x["confidence"], reverse=True):
            if placed >= 2: break
            qty = round(10000*W_RISK/sig["price"],6) if sig["price"]>0 else 0
            if qty<=0: continue
            side = "buy" if sig["action"]=="BUY" else "sell"
            if _w_order(sig["symbol"], side, qty, KRAKEN_PUBLIC, KRAKEN_PRIVATE, log):
                placed += 1
                tg(side.upper()+" "+str(qty)+" "+sig["symbol"]+" @ $"+f"{sig['price']:,.0f}"+" conf="+str(sig["confidence"])+"%")
        log.info("WEEKEND CYCLE END | "+str(len(signals))+" signals | "+str(placed)+" placed")
    except Exception as e:
        log.error("Weekend mode error: "+str(e), exc_info=True)
