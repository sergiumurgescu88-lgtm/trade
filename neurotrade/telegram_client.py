import requests
import logging
import threading
import time
import subprocess
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger("Telegram")
_bot_callbacks = {}

def register_callbacks(callbacks: dict):
    global _bot_callbacks
    _bot_callbacks = callbacks

def send(message: str, parse_mode: str = "HTML", reply_markup: dict = None, chat_id: str = None) -> bool:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id or TELEGRAM_CHAT_ID, "text": message,
                   "parse_mode": parse_mode, "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except Exception as e:
        log.error(f"Telegram send error: {e}")
        return False

def edit_message(chat_id, message_id, text, parse_mode="HTML", reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text,
                   "parse_mode": parse_mode, "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        log.error(f"Telegram edit error: {e}")

def answer_callback(callback_query_id, text=""):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
        requests.post(url, json={"callback_query_id": callback_query_id, "text": text}, timeout=5)
    except Exception:
        pass

def test_connection() -> bool:
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe", timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def kb_main_menu():
    return {"inline_keyboard": [
        [{"text": "📊 Status Bot", "callback_data": "cmd_status"},
         {"text": "💰 Portfolio", "callback_data": "cmd_portfolio"}],
        [{"text": "📈 Pozitii", "callback_data": "cmd_positions"},
         {"text": "🤖 Semnale AI", "callback_data": "cmd_signals"}],
        [{"text": "📋 Tranzactii", "callback_data": "cmd_trades"},
         {"text": "🌍 Piata", "callback_data": "cmd_regime"}],
        [{"text": "⚙️ Setari", "callback_data": "cmd_settings"},
         {"text": "📉 Statistici", "callback_data": "cmd_stats"}],
        [{"text": "⏸ Pauza Bot", "callback_data": "cmd_pause"},
         {"text": "🔴 Opreste Bot", "callback_data": "cmd_stop_confirm"}],
        [{"text": "🔄 Restart Bot", "callback_data": "cmd_restart_confirm"},
         {"text": "📋 Logs Live", "callback_data": "cmd_logs"}],
    ]}

def kb_back():
    return {"inline_keyboard": [[{"text": "◀️ Meniu Principal", "callback_data": "cmd_menu"}]]}

def kb_back_refresh(refresh_cmd):
    return {"inline_keyboard": [[
        {"text": "🔄 Refresh", "callback_data": refresh_cmd},
        {"text": "◀️ Meniu", "callback_data": "cmd_menu"},
    ]]}

def kb_restart_confirm():
    return {"inline_keyboard": [[
        {"text": "✅ Da, restart", "callback_data": "cmd_restart_yes"},
        {"text": "❌ Anuleaza", "callback_data": "cmd_menu"},
    ]]}

def kb_stop_confirm():

    return {"inline_keyboard": [[
        {"text": "✅ Da, opreste", "callback_data": "cmd_stop_yes"},
        {"text": "❌ Anuleaza", "callback_data": "cmd_menu"},
    ]]}

def kb_pause_resume(is_paused: bool):
    if is_paused:
        return {"inline_keyboard": [
            [{"text": "▶️ Reia Bot", "callback_data": "cmd_resume"}],
            [{"text": "◀️ Meniu", "callback_data": "cmd_menu"}],
        ]}
    return {"inline_keyboard": [
        [{"text": "⏸ Pauza Bot", "callback_data": "cmd_pause"}],
        [{"text": "◀️ Meniu", "callback_data": "cmd_menu"}],
    ]}

def _fmt_status() -> str:
    cb = _bot_callbacks
    cycle   = cb.get("get_cycle", lambda: 0)()
    paused  = cb.get("is_paused", lambda: False)()
    regime  = cb.get("get_regime", lambda: {})() or {}
    account = cb.get("get_account", lambda: None)()
    eq   = float(account.get("equity", 0)) if account else 0
    cash = float(account.get("cash", 0)) if account else 0
    pnl  = eq - 100000
    pnl_icon = "📈" if pnl >= 0 else "📉"
    safe  = regime.get("safe_mode", False)
    trend = regime.get("trend", "NEUTRAL")
    spy   = regime.get("spy_change_pct", 0)
    return "\n".join([
        "⚡ <b>NEUROTRADE v1 — STATUS</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{'⏸' if paused else '🟢'} <b>Stare:</b> {'PAUZA' if paused else 'ACTIV'}",
        f"🔄 <b>Ciclu:</b> #{cycle}",
        f"🕐 <b>Ora:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        "",
        f"💰 <b>Equity:</b> ${eq:,.2f}",
        f"💵 <b>Cash:</b> ${cash:,.2f}",
        f"{pnl_icon} <b>P&L Total:</b> ${pnl:+,.2f}",
        "",
        f"🌍 <b>Piata:</b> {trend}",
        f"📊 <b>SPY:</b> {spy:+.2f}%",
        f"{'⚠️ SAFE MODE ACTIV' if safe else '✅ Trading normal'}",
    ])

def _fmt_portfolio() -> str:
    cb = _bot_callbacks
    account   = cb.get("get_account", lambda: None)()
    stats     = cb.get("get_stats", lambda: {})() or {}
    positions = cb.get("get_positions", lambda: [])()
    if not account:
        return "❌ Nu pot accesa contul Alpaca."
    eq   = float(account.get("equity", 0))
    cash = float(account.get("cash", 0))
    bp   = float(account.get("buying_power", 0))
    pnl  = eq - 100000
    pnl_pct = (pnl / 100000) * 100
    total_trades = stats.get("total", 0)
    wins = stats.get("buys", 0)
    win_rate     = (wins / total_trades * 100) if total_trades > 0 else 0
    total_pl     = stats.get("total_pl", 0)
    cash_pct = (cash / eq * 100) if eq > 0 else 0
    filled   = int(cash_pct / 100 * 10)
    cash_bar = "█" * filled + "░" * (10 - filled)
    pnl_icon = "🟢" if pnl >= 0 else "🔴"
    return "\n".join([
        "💰 <b>PORTFOLIO</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>Equity:</b>       ${eq:>12,.2f}",
        f"💵 <b>Cash:</b>         ${cash:>12,.2f}",
        f"⚡ <b>Buying Power:</b> ${bp:>12,.2f}",
        "",
        f"💹 <b>Cash disponibil:</b>",
        f"  [{cash_bar}] {cash_pct:.1f}%",
        "",
        f"{pnl_icon} <b>P&L vs Capital Initial:</b>",
        f"  ${pnl:+,.2f} ({pnl_pct:+.2f}%)",
        "",
        f"📋 <b>Tranzactii totale:</b> {total_trades}",
        f"🎯 <b>Win Rate:</b>          {win_rate:.1f}%",
        f"💰 <b>Profit realizat:</b>   ${total_pl:+,.2f}",
        f"📌 <b>Pozitii deschise:</b>  {len(positions)} / 5",
    ])

def _fmt_positions() -> str:
    positions = _bot_callbacks.get("get_positions", lambda: [])()
    if not positions:
        return "📈 <b>POZITII DESCHISE</b>\n━━━━━━━━━━━━━━━━━━━━\n📭 <i>Nu ai pozitii deschise momentan.</i>"
    lines = ["📈 <b>POZITII DESCHISE</b>", "━━━━━━━━━━━━━━━━━━━━"]
    for p in positions:
        sym    = p.get("symbol", "?")
        qty    = float(p.get("qty", 0))
        entry  = float(p.get("avg_entry_price", 0))
        price  = float(p.get("current_price", 0))
        mv     = float(p.get("market_value", 0))
        pl     = float(p.get("unrealized_pl", 0))
        pl_pct = float(p.get("unrealized_plpc", 0)) * 100
        pl_icon = "🟢" if pl >= 0 else "🔴"
        lines += ["", f"<b>{sym}</b> — {qty:.0f} actiuni",
            f"  💲 Pret curent: ${price:.2f}",
            f"  📥 Entry:       ${entry:.2f}",
            f"  💼 Valoare:     ${mv:,.2f}",
            f"  {pl_icon} P&L:        ${pl:+.2f} ({pl_pct:+.2f}%)"]
    lines += ["", "━━━━━━━━━━━━━━━━━━━━", f"📌 Total: {len(positions)} pozitii"]
    return "\n".join(lines)

def _fmt_trades() -> str:
    trades = _bot_callbacks.get("get_trades", lambda: [])()
    if not trades:
        return "📋 <b>TRANZACTII</b>\n━━━━━━━━━━━━━━━━━━━━\n📭 <i>Nu exista tranzactii inca.</i>"
    recent   = trades[-10:][::-1]
    total_pl = sum(float(t.get("pl", 0)) for t in trades)
    lines    = [f"📋 <b>TRANZACTII (ultimele {len(recent)})</b>", "━━━━━━━━━━━━━━━━━━━━"]
    ct_icons = {"SIGNAL": "📡", "STOP_LOSS": "🛑", "TAKE_PROFIT": "💰", "TRAILING_STOP": "📌"}
    for t in recent:
        sym    = t.get("symbol", "?")
        action = t.get("action", "?")
        qty    = t.get("qty", 0)
        price  = float(t.get("price", 0))
        pl     = float(t.get("pl", 0))
        ctype  = t.get("close_type", "SIGNAL")
        ts     = str(t.get("timestamp", ""))[:16].replace("T", " ")
        a_icon = "🟢" if action == "BUY" else "🔴"
        pl_str = f"  P&L: ${pl:+.2f}" if action == "SELL" else ""
        lines.append(f"{a_icon} <b>{sym}</b> {action} {qty}x @${price:.2f} {ct_icons.get(ctype,'📡')}{pl_str}\n   <i>{ts}</i>")
    lines += ["━━━━━━━━━━━━━━━━━━━━",
              f"💰 <b>P&L Total: ${total_pl:+,.2f}</b>",
              f"📊 <b>Total: {len(trades)} tranzactii</b>"]
    return "\n".join(lines)

def _fmt_regime() -> str:
    regime = _bot_callbacks.get("get_regime", lambda: {})() or {}
    trend  = regime.get("trend", "NEUTRAL")
    safe   = regime.get("safe_mode", False)
    reason = regime.get("reason", "—")
    spy    = regime.get("spy_change_pct", 0)
    trend_icons = {"BULL": "🐂 BULL", "BEAR": "🐻 BEAR", "NEUTRAL": "➡️ NEUTRAL", "VOLATILE": "⚡ VOLATIL"}
    return "\n".join([
        "🌍 <b>MARKET REGIME</b>", "━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>Trend:</b> {trend_icons.get(trend, trend)}",
        f"{'📈' if spy >= 0 else '📉'} <b>SPY azi:</b> {spy:+.2f}%", "",
        f"{'⚠️ <b>SAFE MODE ACTIV</b>' if safe else '✅ <b>Trading normal</b>'}",
        "", f"💬 <b>Motiv:</b>", f"<i>{reason}</i>",
        "", f"🕐 {datetime.now().strftime('%H:%M:%S')}",
    ])

def _fmt_stats() -> str:
    cb      = _bot_callbacks
    stats   = cb.get("get_stats", lambda: {})() or {}
    account = cb.get("get_account", lambda: None)()
    cycle   = cb.get("get_cycle", lambda: 0)()
    total   = stats.get("total", 0)
    wins = stats.get("buys", 0)
    losses  = stats.get("sells", 0)
    total_pl = stats.get("total_pl", 0)
    best    = stats.get("best_trade", 0.0)
    worst   = stats.get("worst_trade", 0.0)
    win_rate = (wins / total * 100) if total > 0 else 0
    eq  = float(account.get("equity", 100000)) if account else 100000
    roi = ((eq - 100000) / 100000) * 100
    filled  = int(win_rate / 100 * 10)
    win_bar = "🟢" * filled + "⬜" * (10 - filled)
    return "\n".join([
        "📉 <b>STATISTICI COMPLETE</b>", "━━━━━━━━━━━━━━━━━━━━",
        f"🔄 <b>Cicluri rulate:</b>    {cycle}",
        f"📊 <b>Tranzactii totale:</b> {total}", "",
        f"🎯 <b>Win Rate:</b>",
        f"  {win_bar} {win_rate:.1f}%",
        f"  ✅ Wins: {wins}  |  ❌ Losses: {losses}", "",
        f"💰 <b>Performanta:</b>",
        f"  P&L realizat: ${total_pl:+,.2f}",
        f"  ROI total:    {roi:+.2f}%",
        f"  Equity:       ${eq:,.2f}", "",
        f"🏆 <b>Best trade:</b>  ${best:+.2f}",
        f"💀 <b>Worst trade:</b> ${worst:+.2f}",
    ])

def _fmt_settings() -> str:
    try:
        from config import (SYMBOLS, CYCLE_MINUTES, CONFIDENCE_THRESHOLD,
            MAX_OPEN_POSITIONS, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
            TRAILING_STOP_PCT, RSI_BUY_MAX, RSI_SELL_MIN)
        return "\n".join([
            "⚙️ <b>SETARI BOT</b>", "━━━━━━━━━━━━━━━━━━━━",
            f"📋 <b>Simboluri:</b>", f"  {', '.join(SYMBOLS)}", "",
            f"⏱ <b>Ciclu:</b>           {CYCLE_MINUTES} minute",
            f"🎯 <b>Confidence min:</b>  {CONFIDENCE_THRESHOLD}%",
            f"📌 <b>Max pozitii:</b>     {MAX_OPEN_POSITIONS}", "",
            "🛡 <b>Risk Management:</b>",
            f"  🔴 Stop Loss:     -{STOP_LOSS_PCT*100:.0f}%",
            f"  💰 Take Profit:   +{TAKE_PROFIT_PCT*100:.0f}%",
            f"  📌 Trailing Stop: -{TRAILING_STOP_PCT*100:.0f}% din peak", "",
            f"  RSI Buy max:  {RSI_BUY_MAX}",
            f"  RSI Sell min: {RSI_SELL_MIN}",
        ])
    except Exception as e:
        return f"⚙️ <b>SETARI BOT</b>\n❌ Eroare: {e}"

def _fmt_logs() -> str:
    try:
        result = subprocess.run(
            ["tail", "-20", "/opt/neurotrade/logs/neurotrade.log"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")[-20:]
        log_text = "\n".join(lines)
        return f"📋 <b>LOGS LIVE (ultimele 20 linii)</b>\n━━━━━━━━━━━━━━━━━━━━\n<pre>{log_text}</pre>"
    except Exception as e:
        return f"❌ Eroare la citire logs: {e}"

_stop_requested = False

def is_stop_requested() -> bool:
    return _stop_requested

def _handle_command(text: str, chat_id: str):
    cmd = text.strip().lower().split()[0] if text else ""
    if cmd in ["/start", "/menu", "/help"]:
        send("⚡ <b>NEUROTRADE v1</b> — Control Center\n━━━━━━━━━━━━━━━━━━━━\nSelecteaza o optiune:", reply_markup=kb_main_menu(), chat_id=chat_id)
    elif cmd == "/status":
        send(_fmt_status(), reply_markup=kb_back_refresh("cmd_status"), chat_id=chat_id)
    elif cmd == "/portfolio":
        send(_fmt_portfolio(), reply_markup=kb_back_refresh("cmd_portfolio"), chat_id=chat_id)
    elif cmd == "/pozitii":
        send(_fmt_positions(), reply_markup=kb_back_refresh("cmd_positions"), chat_id=chat_id)
    elif cmd == "/tranzactii":
        send(_fmt_trades(), reply_markup=kb_back_refresh("cmd_trades"), chat_id=chat_id)
    elif cmd == "/piata":
        send(_fmt_regime(), reply_markup=kb_back_refresh("cmd_regime"), chat_id=chat_id)
    elif cmd == "/statistici":
        send(_fmt_stats(), reply_markup=kb_back_refresh("cmd_stats"), chat_id=chat_id)
    elif cmd == "/restart":
        send("🔄 <b>Restart in curs...</b>", chat_id=chat_id)
        subprocess.Popen(["systemctl", "restart", "neurotrade"])
    elif cmd == "/logs":
        send(_fmt_logs(), reply_markup=kb_back_refresh("cmd_logs"), chat_id=chat_id)
    elif cmd == "/setari":
        send(_fmt_settings(), reply_markup=kb_back(), chat_id=chat_id)
    else:
        send("❓ Comanda necunoscuta. Foloseste /menu", reply_markup=kb_main_menu(), chat_id=chat_id)

def _handle_callback(cq: dict):
    global _stop_requested
    cq_id   = cq.get("id")
    data    = cq.get("data", "")
    chat_id = str(cq["message"]["chat"]["id"])
    msg_id  = cq["message"]["message_id"]
    answer_callback(cq_id)
    handlers = {
        "cmd_menu":      lambda: ("⚡ <b>NEUROTRADE v1</b> — Control Center\n━━━━━━━━━━━━━━━━━━━━\nSelecteaza o optiune:", kb_main_menu()),
        "cmd_status":    lambda: (_fmt_status(),    kb_back_refresh("cmd_status")),
        "cmd_portfolio": lambda: (_fmt_portfolio(), kb_back_refresh("cmd_portfolio")),
        "cmd_positions": lambda: (_fmt_positions(), kb_back_refresh("cmd_positions")),
        "cmd_signals":   lambda: (_fmt_status(),    kb_back_refresh("cmd_signals")),
        "cmd_trades":    lambda: (_fmt_trades(),    kb_back_refresh("cmd_trades")),
        "cmd_regime":    lambda: (_fmt_regime(),    kb_back_refresh("cmd_regime")),
        "cmd_stats":     lambda: (_fmt_stats(),     kb_back_refresh("cmd_stats")),
        "cmd_settings":  lambda: (_fmt_settings(),  kb_back()),
    }
    if data in handlers:
        text, markup = handlers[data]()
        edit_message(chat_id, msg_id, text, reply_markup=markup)
    elif data == "cmd_pause":
        pause_fn = _bot_callbacks.get("pause")
        if pause_fn:
            pause_fn()
        edit_message(chat_id, msg_id, "⏸ <b>Bot pus in pauza.</b>", reply_markup=kb_pause_resume(True))
    elif data == "cmd_resume":
        resume_fn = _bot_callbacks.get("resume")
        if resume_fn:
            resume_fn()
        edit_message(chat_id, msg_id, "▶️ <b>Bot reluat.</b>", reply_markup=kb_pause_resume(False))
    elif data == "cmd_logs":
        edit_message(chat_id, msg_id, _fmt_logs(), reply_markup=kb_back_refresh("cmd_logs"))
    elif data == "cmd_restart_confirm":
        edit_message(chat_id, msg_id, "🔄 <b>Esti sigur ca vrei sa restartezi botul?</b>", reply_markup=kb_restart_confirm())
    elif data == "cmd_restart_yes":
        edit_message(chat_id, msg_id, "🔄 <b>Bot repornit prin systemd...</b>")
        subprocess.Popen(["systemctl", "restart", "neurotrade"])
    elif data == "cmd_stop_confirm":
        edit_message(chat_id, msg_id, "🔴 <b>Esti sigur ca vrei sa opresti botul?</b>", reply_markup=kb_stop_confirm())
    elif data == "cmd_stop_yes":
        _stop_requested = True
        edit_message(chat_id, msg_id, "🔴 <b>Bot oprit din Telegram.</b>")

_last_update_id = 0
_polling_active = False

def _poll_loop():
    global _last_update_id, _polling_active
    log.info("Telegram polling pornit.")
    while _polling_active:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            r = requests.get(url, params={
                "offset": _last_update_id + 1,
                "timeout": 20,
                "allowed_updates": ["message", "callback_query"]
            }, timeout=25)
            if r.status_code != 200:
                time.sleep(5)
                continue
            for update in r.json().get("result", []):
                _last_update_id = update["update_id"]
                if "message" in update:
                    msg = update["message"]
                    chat_id = str(msg["chat"]["id"])
                    if chat_id == str(TELEGRAM_CHAT_ID):
                        _handle_command(msg.get("text", ""), chat_id)
                elif "callback_query" in update:
                    cq = update["callback_query"]
                    chat_id = str(cq["message"]["chat"]["id"])
                    if chat_id == str(TELEGRAM_CHAT_ID):
                        _handle_callback(cq)
        except Exception as e:
            log.error(f"Telegram poll error: {e}")
            time.sleep(5)

def start_polling():
    global _polling_active
    _polling_active = True
    threading.Thread(target=_poll_loop, daemon=True).start()
    log.info("Telegram menu polling activ.")

def stop_polling():
    global _polling_active
    _polling_active = False
