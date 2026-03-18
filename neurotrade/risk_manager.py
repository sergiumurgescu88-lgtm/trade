"""
risk_manager.py — Auto alerts for x10 leverage
"""
import logging, time
from config import MARGIN_CALL_LEVEL, MARGIN_CRITICAL_LEVEL, MAX_OPEN_CRYPTO_POSITIONS, TELEGRAM_ALERTS_ENABLED
import telegram_client as telegram
import kraken_client as kraken
import sentiment_analyzer as sentiment

log = logging.getLogger("RiskManager")

class RiskManager:
    def __init__(self):
        self._last_alert = {}
        self.cooldown = 300
    
    def check_margin_safety(self) -> bool:
        status = kraken.kraken.check_margin_level()
        if status['level'] < MARGIN_CRITICAL_LEVEL:
            if self._can_alert('margin_critical'):
                self._send_alert(f"🚨 MARGIN CRITICAL: {status['level']}% - AUTO CLOSING", 'critical')
                kraken.kraken.close_all_positions('Margin Critical')
            return False
        elif status['level'] < MARGIN_CALL_LEVEL:
            if self._can_alert('margin_warning'):
                self._send_alert(f"⚠️ MARGIN WARNING: {status['level']}%", 'warning')
        return True
    
    def check_liquidation_risk(self) -> bool:
        for pos in kraken.kraken.get_open_positions():
            risk = kraken.kraken.check_position_risk(pos)
            if risk['risk'] == 'CRITICAL' and self._can_alert('liq_' + pos['symbol']):
                self._send_alert(f"🚨 LIQUIDATION RISK: {pos['symbol']} - {risk['distance_to_liq_pct']}% from liq", 'critical')
                kraken.kraken.close_position(pos['id'], 'Liquidation Risk')
        return True
    
    def check_position_count(self) -> bool:
        positions = [p for p in kraken.kraken.get_open_positions() if '/' in p['symbol']]
        return len(positions) < MAX_OPEN_CRYPTO_POSITIONS
    
    def get_sentiment_signal(self, symbol: str):
        currency = symbol.split('/')[0] if '/' in symbol else symbol
        return sentiment.sentiment_analyzer.should_trade(currency, min_confidence=70, min_score=0.35, leverage=10)
    
    def _can_alert(self, key: str) -> bool:
        now = time.time()
        if now - self._last_alert.get(key, 0) > self.cooldown:
            self._last_alert[key] = now
            return True
        return False
    
    def _send_alert(self, message: str, level: str = 'info'):
        if TELEGRAM_ALERTS_ENABLED:
            telegram.send_message(message)
        log.warning(message)

risk_manager = RiskManager()

if __name__ == "__main__":
    print("=" * 60)
    print("🛡️ RISK MANAGER CHECK")
    print("=" * 60)
    rm = RiskManager()
    print(f"Margin Safe: {rm.check_margin_safety()}")
    print(f"Liquidation Safe: {rm.check_liquidation_risk()}")
    print(f"Position Limit OK: {rm.check_position_count()}")
    print("=" * 60)
