"""
bot.py — NeuroTrade Bot v5.0
Multi-market: Stocks + ETF (Alpaca) + Crypto (Binance paper) + Forex (Yahoo paper)
AI Chain: Gemini → xAI Grok → Qwen
News: 9 surse + CryptoPanic + xAI live
"""
import asyncio, logging, os, time
from datetime import datetime, date
import alpaca_client as alpaca
import kraken_client as kraken
import forex_client as forex
import news_client as news
import ai_client as ai
import indicators
import market_regime as regime
import position_sizer as sizer
import history
import telegram_client as telegram
import supabase_client as supabase
from config import (
    ALL_SYMBOLS, STOCK_SYMBOLS, ETF_SYMBOLS, CRYPTO_SYMBOLS, FOREX_SYMBOLS,
    CYCLE_MINUTES, CONFIDENCE_THRESHOLD, MAX_OPEN_POSITIONS, STARTING_CAPITAL,
    SYMBOL_DELAY_SEC, RSI_BUY_MAX, RSI_SELL_MIN, RSI_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL, EMA_FAST, EMA_SLOW, HISTORY_BARS,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT, TRAILING_STOP_PCT,
    SAFE_MODE_DROP_PCT, DAILY_LOSS_LIMIT_PCT, PORTFOLIO_RISK_CAP,
    MAX_POSITION_USD, MIN_POSITION_USD,
)

os.makedirs("logs", exist_ok=True)
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler("logs/neurotrade-v5.log", encoding="utf-8"),
              logging.StreamHandler()])
log = logging.getLogger("BotV5")

_daily_start_equity = 0.0
_daily_reset_date = None
_paused = [False]

def _reset_daily(equity):
    global _daily_start_equity, _daily_reset_date
    today = date.today()
    if _daily_reset_date != today:
        _daily_start_equity = equity
        _daily_reset_date = today
        log.info(f"Reset zilnic — equity: ${equity:,.2f}")

def _daily_loss_hit(equity):
    if _daily_start_equity <= 0: return False
    return (equity - _daily_start_equity) / _daily_start_equity < -DAILY_LOSS_LIMIT_PCT

def _deployed_pct(positions, equity):
    if equity <= 0: return 0.0
    return sum(float(p.get("market_value",0) or 0) for p in positions) / equity

def _get_client(market):
    if market == "crypto": return kraken
    if market == "forex": return forex
    return alpaca

def _get_market_type(symbol):
    if symbol in CRYPTO_SYMBOLS: return "crypto"
    if symbol in FOREX_SYMBOLS: return "forex"
    if symbol in ETF_SYMBOLS: return "etf"
    return "stock"

def _calc_qty(market_type, confidence, cash, price):
    if market_type == "crypto":
        pct = {(52,59):0.05,(60,69):0.08,(70,79):0.12,(80,89):0.16,(90,100):0.20}
        for (lo,hi),p in pct.items():
            if lo <= confidence <= hi:
                amount = min(cash * p, MAX_POSITION_USD)
                return round(amount / price, 6)
        return 0
    elif market_type == "forex":
        return 1.0  # 1 mini lot
    else:
        return sizer.calc_quantity(confidence, cash, price)

async def _check_risk_exits(positions, market_type="stock"):
    client = _get_client(market_type)
    closed = []; msgs = []
    for pos in positions:
        symbol = pos.get("symbol","")
        qty = float(pos.get("qty",0))
        unr_pct = float(pos.get("unrealized_plpc",0) or 0)
        unr_pl = float(pos.get("unrealized_pl",0) or 0)
        current = float(pos.get("current_price",0) or 0)
        entry = float(pos.get("avg_entry_price",0) or 0)
        if entry <= 0 or qty <= 0: continue
        close_type = None
        if unr_pct <= -STOP_LOSS_PCT: close_type = "STOP_LOSS"
        elif unr_pct >= TAKE_PROFIT_PCT: close_type = "TAKE_PROFIT"
        elif unr_pct > 0:
            peak_pct = max(unr_pct, TAKE_PROFIT_PCT * 0.5)
            if peak_pct - unr_pct >= TRAILING_STOP_PCT and unr_pct > 0.005:
                close_type = "TRAILING_STOP"
        if close_type:
            ok = client.close_position(symbol)
            if ok:
                history.add_trade(symbol, "SELL", qty, current, 0, close_type, unr_pl)
                supabase.push_trade(symbol, "SELL", qty, current, 0, close_type, unr_pl, "", market_type)
                icon = {"STOP_LOSS":"🛑","TAKE_PROFIT":"💰","TRAILING_STOP":"📌"}.get(close_type,"⚪")
                msgs.append(f"{icon} <b>{symbol}</b> [{close_type}] @ ${current:.4f} | P&L: ${unr_pl:+.2f}")
                closed.append(symbol)
            await asyncio.sleep(0.3)
    return closed, msgs

async def run_cycle(cycle):
    log.info(f"{'='*20} CICLU V5 #{cycle} {'='*20}")

    # ── Conturi ─────────────────────────────────────────────
    alpaca_acc = alpaca.get_account()
    if not alpaca_acc: log.error("Alpaca offline"); return

    eq_stocks = float(alpaca_acc.get("equity",0))
    cash_stocks = float(alpaca_acc.get("cash", alpaca_acc.get("buying_power",0)))
    crypto_acc = kraken.get_account()
    forex_acc = forex.get_account()
    eq_crypto = float(crypto_acc.get("equity",0))
    eq_forex = float(forex_acc.get("equity",0))
    total_equity = eq_stocks + eq_crypto + eq_forex

    _reset_daily(total_equity)
    if _daily_loss_hit(total_equity):
        log.warning("Circuit breaker zilnic — skip")
        telegram.send(f"⛔ <b>CIRCUIT BREAKER V5</b>\nPierdere >{DAILY_LOSS_LIMIT_PCT*100:.0f}% azi")
        return

    # ── Market regime ────────────────────────────────────────
    regime_info = regime.get_regime()
    safe_mode = regime_info.get("safe_mode", False)
    log.info(f"Equity total: ${total_equity:,.2f} | Safe: {safe_mode} | Trend: {regime_info.get('trend')}")

    if safe_mode:
        telegram.send(f"⚠️ <b>SAFE MODE V5</b>\n{regime_info['reason']}")

    # ── Risk exits toate pietele ─────────────────────────────
    all_closed = []
    for mtype, client in [("stock", alpaca), ("crypto", kraken), ("forex", forex)]:
        positions = client.get_positions()
        closed, msgs = await _check_risk_exits(positions, mtype)
        all_closed.extend(closed)
        if msgs:
            telegram.send(f"📊 <b>Risk V5 [{mtype.upper()}]:</b>\n" + "\n".join(msgs))

    if safe_mode:
        _push_snapshot(alpaca_acc, cycle, regime_info)
        return

    # ── Scan simboluri ───────────────────────────────────────
    all_markets = [
        (STOCK_SYMBOLS, "stock", alpaca),
        (ETF_SYMBOLS, "etf", alpaca),
        (CRYPTO_SYMBOLS, "crypto", kraken),
        (FOREX_SYMBOLS, "forex", forex),
    ]

    executed = 0; blocked = 0
    cycle_lines = [
        f"🔄 <b>CICLU V5 #{cycle}</b> — {datetime.now().strftime('%H:%M')}",
        f"💰 Stocks: ${eq_stocks:,.0f} | Crypto: ${eq_crypto:,.0f} | Forex: ${eq_forex:,.0f}",
        f"📡 {regime_info.get('reason','')[:55]}", ""
    ]

    for symbols, mtype, client in all_markets:
        if mtype in ["stock","etf"] and safe_mode: continue

        acc = client.get_account()
        cash = float(acc.get("cash", acc.get("buying_power",0)))
        positions = client.get_positions()
        pos_syms = {p.get("symbol") for p in positions}
        open_count = len(positions)

        # Prioritate: simboluri cu pozitii deschise (SELL) primul
        scan_order = [s for s in symbols if s in pos_syms] + [s for s in symbols if s not in pos_syms]

        for symbol in scan_order:
            if open_count >= MAX_OPEN_POSITIONS and symbol not in pos_syms: break

            try:
                price = client.get_price(symbol) if hasattr(client,"get_price") else None
                if mtype in ["stock","etf"]:
                    price = alpaca.get_price(symbol)
                elif mtype == "crypto":
                    price = kraken.get_price(symbol)
                elif mtype == "forex":
                    price = forex.get_price(symbol)
                if not price: continue

                # Indicatori tehnici
                if mtype in ["stock","etf"]:
                    closes = alpaca.get_closes(symbol, limit=HISTORY_BARS) or []
                elif mtype == "crypto":
                    closes = kraken.get_closes(symbol, limit=HISTORY_BARS) or []
                else:
                    closes = forex.get_closes(symbol, limit=HISTORY_BARS) or []

                if closes and len(closes) >= 15:
                    tech = indicators.analyze_all(closes, RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL, EMA_FAST, EMA_SLOW)
                else:
                    tech = {"rsi":None,"macd_crossover":"none","ema_trend":"neutral","tech_score":0,"tech_recommendation":"N/A"}

                # Stiri
                articles = news.get_news(symbol, mtype)
                time.sleep(1)

                # AI analiza
                has_pos = symbol in pos_syms
                signal = ai.analyze(symbol, articles, price, has_pos, tech, mtype)
                action = signal["action"]; conf = signal["confidence"]
                rsi_str = f"{tech['rsi']:.0f}" if tech.get("rsi") else "N/A"
                emoji = {"BUY":"🟢","SELL":"🔴","HOLD":"⚪"}.get(action,"⚪")
                cycle_lines.append(f"{emoji} <b>[{mtype.upper()}] {symbol}</b> ${price:.4f} | {action} {conf}% | RSI:{rsi_str}")

                # Filtre executie
                can_trade = False; reason = "HOLD"
                if action == "BUY" and not safe_mode:
                    if conf < CONFIDENCE_THRESHOLD: reason = f"Conf {conf}%<{CONFIDENCE_THRESHOLD}%"
                    elif has_pos: reason = "Pozitie deja deschisa"
                    elif open_count >= MAX_OPEN_POSITIONS: reason = "Max pozitii"
                    elif cash < MIN_POSITION_USD: reason = "Cash insuficient"
                    elif tech.get("rsi") and tech["rsi"] > RSI_BUY_MAX: reason = f"RSI {tech['rsi']:.0f}>{RSI_BUY_MAX}"
                    elif mtype in ["stock","etf"] and not alpaca.is_market_open() if hasattr(alpaca,"is_market_open") else False: reason = "Piata inchisa"
                    else: can_trade = True; reason = ""
                elif action == "SELL":
                    if conf < CONFIDENCE_THRESHOLD: reason = f"Conf {conf}%<{CONFIDENCE_THRESHOLD}%"
                    elif not has_pos: reason = "Fara pozitie"
                    else: can_trade = True; reason = ""

                supabase.save_signal(symbol=symbol, action=action, confidence=conf,
                    reason=signal.get("reasoning",""), market=mtype)

                if can_trade and action in ["BUY","SELL"]:
                    if action == "BUY":
                        qty = _calc_qty(mtype, conf, cash, price)
                        if qty <= 0:
                            await asyncio.sleep(SYMBOL_DELAY_SEC); continue
                        order = client.place_order(symbol, "buy", qty)
                        if order:
                            executed += 1; open_count += 1; cash -= qty * price
                            history.add_trade(symbol, "BUY", qty, price, conf, "SIGNAL", 0.0)
                            supabase.push_trade(symbol, "BUY", qty, price, conf, "SIGNAL", 0.0, order.get("id",""), mtype)
                            telegram.send(f"🟢 <b>[{mtype.upper()}] {symbol} BUY</b> {qty} @ ${price:.4f}\n🎯 {conf}% | {signal.get('reasoning','')[:150]}")
                    elif action == "SELL":
                        pos = next((p for p in positions if p.get("symbol")==symbol), None)
                        if pos:
                            qty = float(pos.get("qty",0))
                            unr_pl = float(pos.get("unrealized_pl",0) or 0)
                            ok = client.close_position(symbol)
                            if ok:
                                executed += 1; open_count -= 1
                                history.add_trade(symbol, "SELL", qty, price, conf, "SIGNAL", unr_pl)
                                supabase.push_trade(symbol, "SELL", qty, price, conf, "SIGNAL", unr_pl, "", mtype)
                                telegram.send(f"🔴 <b>[{mtype.upper()}] {symbol} SELL</b> @ ${price:.4f}\n💰 P&L: ${unr_pl:+.2f}")
                else:
                    if action != "HOLD" and conf >= 70:
                        blocked += 1

            except Exception as e:
                log.error(f"[{symbol}] Eroare: {e}", exc_info=True)

            await asyncio.sleep(SYMBOL_DELAY_SEC)

    # ── Rezumat ──────────────────────────────────────────────
    cycle_lines += ["", f"⚡ <b>Rezultat:</b> {executed} executate | {blocked} blocate | {len(all_closed)} risk exits"]
    telegram.send("\n".join(cycle_lines))
    _push_snapshot(alpaca_acc, cycle, regime_info)
    log.info(f"CICLU V5 #{cycle} FINISH — exec={executed} blocked={blocked}")


def _push_snapshot(account, cycle, regime_info):
    try:
        positions = alpaca.get_positions()
        prices = alpaca.get_prices_batch(ALL_SYMBOLS)
        stats = history.get_summary()
        # Equity total: Alpaca + Kraken + Forex
        eq_stocks = float(account.get("equity", 0))
        eq_kraken = float(kraken.get_account().get("equity", 0))
        eq_forex  = float(forex.get_account().get("equity", 0))
        total_eq  = eq_stocks + eq_kraken + eq_forex
        initial   = 13000
        supabase._client.save_snapshot(
            equity=total_eq,
            cash=float(account.get("cash", 0)),
            open_positions=len(positions),
            pnl=total_eq - initial,
            pnl_pct=((total_eq - initial) / initial) * 100,
            total_pl=total_eq - initial,
            cycle=cycle,
            safe_mode=regime_info.get("safe_mode", False),
            market_trend=regime_info.get("trend", "NEUTRAL"),
            total_trades=stats.get("total_trades", 0)
        )
        supabase.push_positions(positions, prices)
    except Exception as e:
        log.warning(f"Snapshot error: {e}")


async def main():
    log.info("NeuroTrade Bot V5.0 pornit")
    conn = {
        "alpaca": alpaca.test_connection(),
        "kraken": kraken.test_connection(),
        "forex": forex.test_connection(),
        "ai": ai.test_connection(),
        "news": news.test_connection(),
        "telegram": telegram.test_connection(),
        "supabase": supabase.test_connection(),
    }
    for name, ok in conn.items():
        log.info(f"  {name}: {'OK' if ok else 'EROARE'}")

    account = alpaca.get_account()
    eq = float(account.get("equity",0)) if account else 0
    crypto_acc = kraken.get_account()
    forex_acc = forex.get_account()

    telegram.send("\n".join([
        "🚀 <b>NEUROTRADE BOT V5.0 PORNIT</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{'✅' if conn['alpaca'] else '❌'} Alpaca Stocks/ETF",
        f"{'✅' if conn["kraken"] else '❌'} Kraken Crypto (paper)",
        f"{'✅' if conn['forex'] else '❌'} Forex (paper)",
        f"{'✅' if conn['ai'] else '❌'} AI (Gemini+xAI+Qwen)",
        f"{'✅' if conn['news'] else '❌'} News (9 surse)",
        f"{'✅' if conn['supabase'] else '❌'} Supabase",
        "",
        f"💰 Stocks equity: ${eq:,.2f}",
        f"🪙 Crypto cash: ${crypto_acc.get('cash',0):,.2f}",
        f"💱 Forex cash: ${forex_acc.get('cash',0):,.2f}",
        "",
        f"📋 {len(STOCK_SYMBOLS)} stocks | {len(ETF_SYMBOLS)} ETF | {len(CRYPTO_SYMBOLS)} crypto | {len(FOREX_SYMBOLS)} forex",
        f"⏱ Ciclu: {CYCLE_MINUTES} min | Conf: ≥{CONFIDENCE_THRESHOLD}% | Max: {MAX_OPEN_POSITIONS} pozitii",
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
    ]))

    # Telegram menu polling
    telegram.register_callbacks({
        "get_cycle":    lambda: cycle if 'cycle' in dir() else 0,
        "is_paused":    lambda: _paused[0],
        "get_regime":   lambda: _last_regime[0] if '_last_regime' in dir() else {},
        "get_account":  lambda: alpaca.get_account(),
        "get_positions":lambda: alpaca.get_positions(),
        "get_stats":    lambda: _stats[0] if '_stats' in dir() else {},
        "get_trades":   lambda: [],
        "pause":        lambda: _paused.__setitem__(0, True),
        "resume":       lambda: _paused.__setitem__(0, False),
    })
    # telegram.start_polling()  # MOVED TO ASYNC TASK
    # Pornește polling async în background
    import threading
    polling_thread = threading.Thread(target=telegram.start_polling, daemon=True)
    polling_thread.start()
    await asyncio.sleep(2)  # Dă timp să pornească

    if not conn["alpaca"]:
        log.error("Alpaca offline — opresc"); return

    cycle = 0
    while True:
        try:
            if _paused[0]:
                await asyncio.sleep(30); continue
            cycle += 1
            await run_cycle(cycle)
            log.info(f"Urmator ciclu in {CYCLE_MINUTES} minute...")
            await asyncio.sleep(CYCLE_MINUTES * 60)
        except KeyboardInterrupt:
            telegram.send("⛔ <b>NeuroTrade V5 oprit.</b>")
            break
        except Exception as e:
            log.error(f"Eroare critica #{cycle}: {e}", exc_info=True)
            telegram.send(f"⚠️ <b>Eroare V5 #{cycle}:</b> {str(e)[:200]}\nRepornesc 60s...")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
