import news_client as news
import asyncio
import telegram_client as telegram, logging, time, requests
from datetime import datetime, date
import alpaca_client as alpaca
import gemini_analyst as gemini
import technical
import supabase_client as supabase
from config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY,
    STARTING_CAPITAL, CYCLE_MINUTES, SYMBOL_DELAY_SEC,
    CONFIDENCE_THRESHOLD, MAX_OPEN_POSITIONS,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT, RISK_CAP_PCT, MAX_DAILY_LOSS_PCT,
    RSI_BUY_MAX, RSI_SELL_MIN, STOCK_SYMBOLS, CRYPTO_SYMBOLS, ALL_SYMBOLS,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("Bot")

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=8)
    except: pass

def calc_qty(price, cash, confidence, is_crypto=False):
    pct = 0.05 + (confidence - CONFIDENCE_THRESHOLD) / 100 * 0.1
    pct = min(pct, 0.12)
    amount = min(cash * pct, cash * 0.15)
    qty = round(amount / price, 6) if is_crypto else int(amount / price)
    return qty if qty > 0 else 0

def check_risk_exits(positions, prices):
    exits = []
    for pos in positions:
        sym = pos.get("symbol","")
        entry = float(pos.get("avg_entry_price",0) or 0)
        qty = float(pos.get("qty",0) or 0)
        if not entry or not qty: continue
        display_sym = sym
        for cs in CRYPTO_SYMBOLS:
            if sym == cs.replace("/",""): display_sym = cs; break
        price = prices.get(display_sym) or prices.get(sym)
        if not price: continue
        change = (price - entry) / entry
        if change <= -STOP_LOSS_PCT:
            exits.append({"pos": pos, "sym": display_sym, "alpaca_sym": sym, "qty": qty, "reason": "STOP_LOSS", "price": price})
        elif change >= TAKE_PROFIT_PCT:
            exits.append({"pos": pos, "sym": display_sym, "alpaca_sym": sym, "qty": qty, "reason": "TAKE_PROFIT", "price": price})
    return exits

_daily = {"date": None, "start_equity": None, "total": 0, "total_pl": 0.0}

def update_stats(pl):
    _daily["total"] += 1
    _daily["total_pl"] += pl

async def run_cycle(cycle):
    log.info(f"{'='*20} CICLU #{cycle} {'='*20}")
    account = alpaca.get_account()
    positions = alpaca.get_positions()
    equity = float(account.get("equity",0) or 0)
    cash = float(account.get("cash",0) or 0)

    today = date.today()
    if _daily["date"] != today:
        _daily["date"] = today
        _daily["start_equity"] = equity
        _daily["total"] = 0
        _daily["total_pl"] = 0.0
        log.info(f"Reset zilnic — equity: ${equity:,.2f}")

    if _daily["start_equity"] and (equity - _daily["start_equity"]) / _daily["start_equity"] <= -MAX_DAILY_LOSS_PCT:
        log.warning("Pierdere zilnica maxima — skip")
        return

    log.info(f"Equity: ${equity:,.2f} | Cash: ${cash:,.2f} | Pozitii: {len(positions)}/{MAX_OPEN_POSITIONS}")

    prices = {}
    for sym in ALL_SYMBOLS:
        p = alpaca.get_price(sym)
        if p: prices[sym] = p
        await asyncio.sleep(0.2)
    log.info(f"Preturi: {len(prices)}/{len(ALL_SYMBOLS)}")

    for ex in check_risk_exits(positions, prices):
        sym = ex["sym"]; qty = ex["qty"]; price = ex["price"]; reason = ex["reason"]
        entry = float(next((p for p in positions if p.get("symbol")==ex["alpaca_sym"]), {}).get("avg_entry_price", price) or price)
        pl = (price - entry) * qty
        order = alpaca.place_order(sym, qty, "sell")
        if order:
            update_stats(pl)
            supabase.push_trade(sym, "SELL", qty, price, 0, reason, pl, order.get("id",""))
            tg(f"{'🟢' if pl>=0 else '🔴'} <b>{sym} SELL [{reason}]</b>\n💲 ${price:.4f} | P&L: {pl:+.2f}$")

    positions = alpaca.get_positions()
    deployed = sum(float(p.get("market_value",0) or 0) for p in positions)
    if equity > 0 and deployed/equity >= RISK_CAP_PCT:
        log.info("Risk cap atins — skip scan")
        supabase.push_portfolio(account, positions, {}, cycle, _daily)
        supabase.push_positions(positions, prices)
        return

    if len(positions) >= MAX_OPEN_POSITIONS:
        log.info("Max pozitii — skip scan")
        supabase.push_portfolio(account, positions, {}, cycle, _daily)
        supabase.push_positions(positions, prices)
        return

    held = set()
    for pos in positions:
        s = pos.get("symbol","")
        held.add(s)
        for cs in CRYPTO_SYMBOLS:
            if s == cs.replace("/",""): held.add(cs)

    buy_count = 0
    for sym in ALL_SYMBOLS:
        if len(positions) + buy_count >= MAX_OPEN_POSITIONS: break
        is_crypto = "/" in sym
        price = prices.get(sym)
        if not price: continue

        bars = alpaca.get_bars(sym, "1Hour", 50) or []
        if len(bars) < 20: bars = alpaca.get_bars(sym, "1Day", 30) or []
        tech = technical.analyze(bars, sym)
        if not isinstance(tech, dict): tech = {"rsi": 50, "macd_crossover": "none", "ema_trend": "neutral", "tech_score": 0, "signal": "NEUTRAL", "price": 0}

        alpaca_sym = sym.replace("/","") if is_crypto else sym

        if alpaca_sym in held or sym in held:
            if tech["rsi"] > RSI_SELL_MIN:
                pos = next((p for p in positions if p.get("symbol")==alpaca_sym), None)
                if pos:
                    ai = gemini.analyze(sym, price, tech, news.get_news(sym), "crypto" if is_crypto else "stock")
                    if ai["action"] == "SELL" and ai["confidence"] >= CONFIDENCE_THRESHOLD:
                        qty = float(pos.get("qty",0) or 0)
                        entry = float(pos.get("avg_entry_price",price) or price)
                        pl = (price - entry) * qty
                        order = alpaca.place_order(sym, qty, "sell")
                        if order:
                            update_stats(pl)
                            supabase.push_trade(sym, "SELL", qty, price, ai["confidence"], "SIGNAL", pl, order.get("id",""))
                            tg(f"🔴 <b>{sym} SELL</b> [AI {ai['confidence']}%]\n💲 ${price:.4f} | P&L: {pl:+.2f}$")
            await asyncio.sleep(SYMBOL_DELAY_SEC)
            continue

        if tech["rsi"] > RSI_BUY_MAX:
            await asyncio.sleep(1)
            continue

        ai = gemini.analyze(sym, price, tech, news.get_news(sym), "crypto" if is_crypto else "stock")
        supabase.push_signal(sym, ai["action"], ai["confidence"], price, tech, ai["reasoning"], ai["risk"], False, None)
        log.info(f"{'🟢' if ai['action']=='BUY' else '⚪'} {sym} ${price:.4f} | {ai['action']} {ai['confidence']}% | RSI:{tech['rsi']}")

        if ai["action"] == "BUY" and ai["confidence"] >= CONFIDENCE_THRESHOLD:
            if not is_crypto and not alpaca.is_market_open():
                log.info(f"[{sym}] Piata inchisa — skip")
                await asyncio.sleep(1)
                continue
            qty = calc_qty(price, cash, ai["confidence"], is_crypto)
            if qty <= 0:
                await asyncio.sleep(SYMBOL_DELAY_SEC)
                continue
            order = alpaca.place_order(sym, qty, "buy")
            if order:
                buy_count += 1
                cash -= qty * price
                supabase.push_trade(sym, "BUY", qty, price, ai["confidence"], "", 0.0, order.get("id",""))
                tg(f"🟢 <b>{sym} BUY</b> {qty} @ ${price:.4f}\n🎯 {ai['confidence']}% | RSI:{tech['rsi']}\n💬 {ai['reasoning'][:150]}")
        await asyncio.sleep(SYMBOL_DELAY_SEC)

    positions = alpaca.get_positions()
    supabase.push_portfolio(account, positions, {"trend":"NEUTRAL"}, cycle, _daily)
    supabase.push_positions(positions, prices)
    tg(f"🔄 <b>CICLU #{cycle}</b>\n💰 ${equity:,.2f} | 📌 {len(positions)}/{MAX_OPEN_POSITIONS} | P&L: {_daily['total_pl']:+.2f}$")

async def main():
    log.info("NeuroTrade Bot v2.0 pornit")
    account = alpaca.get_account()
    if not account:
        log.error("Alpaca offline")
        return
    supabase.test_connection()
    equity = float(account.get("equity",0) or 0)
    tg(f"🚀 <b>NEUROTRADE BOT v2.0</b>\n💰 Capital: ${equity:,.2f}\n📋 Stocks: {len(STOCK_SYMBOLS)} | Crypto: {len(CRYPTO_SYMBOLS)}\n⏱ Ciclu: {CYCLE_MINUTES} min\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    # Telegram menu polling
    telegram.register_callbacks({
        "get_cycle":     lambda: _cycle[0] if '_cycle' in dir() else 0,
        "is_paused":     lambda: False,
        "get_regime":    lambda: {"trend":"NEUTRAL","safe_mode":False,"spy_change_pct":0,"reason":"—"},
        "get_account":   lambda: alpaca.get_account(),
        "get_positions": lambda: alpaca.get_positions(),
        "get_stats":     lambda: _daily,
        "get_trades":    lambda: [],
        "pause":         lambda: None,
        "resume":        lambda: None,
    })
    telegram.start_polling()

    _cycle = [0]
    cycle = 0
    while True:
        try:
            cycle += 1
            _cycle[0] = cycle
            await run_cycle(cycle)
            log.info(f"Urmator ciclu in {CYCLE_MINUTES} minute...")
            await asyncio.sleep(CYCLE_MINUTES * 60)
        except KeyboardInterrupt:
            tg("⛔ <b>NeuroTrade v2.0 oprit.</b>")
            break
        except Exception as e:
            log.error(f"Eroare #{cycle}: {e}", exc_info=True)
            tg(f"⚠️ Eroare #{cycle}: {str(e)[:200]}\nRepornesc 60s...")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
