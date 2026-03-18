import requests
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import sys

class SupabaseClient:
    def __init__(self):
        url = ""
        key = ""
        try:
            sys.path.insert(0, '/opt/neurotrade-v5')
            from config import SUPABASE_URL, SUPABASE_KEY
            url = SUPABASE_URL
            key = SUPABASE_KEY
        except Exception:
            pass
        if not url or not key:
            try:
                for line in open('/opt/neurotrade-v5/.env'):
                    line = line.strip()
                    if line.startswith('SUPABASE_URL=') and not url:
                        url = line.split('=', 1)[1]
                    if line.startswith('SUPABASE_KEY=') and not key:
                        key = line.split('=', 1)[1]
            except Exception:
                pass
        self.url = url.rstrip('/')
        self.key = key
        self.headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def test_connection(self) -> bool:
        try:
            r = requests.get(
                f'{self.url}/rest/v1/portfolio_snapshot?limit=1',
                headers=self.headers, timeout=5
            )
            return r.status_code in (200, 206)
        except Exception as e:
            print(f'[Supabase] Connection error: {e}')
            return False

    def _upsert(self, table: str, data: Dict) -> bool:
        try:
            h = {**self.headers, 'Prefer': 'resolution=merge-duplicates,return=representation'}
            r = requests.post(
                f'{self.url}/rest/v1/{table}',
                headers=h, data=json.dumps(data), timeout=10
            )
            if r.status_code in (200, 201):
                return True
            print(f'[Supabase] Upsert {table}: {r.status_code} {r.text[:150]}')
            return False
        except Exception as e:
            print(f'[Supabase] Upsert error: {e}')
            return False

    def _insert(self, table: str, data: Dict) -> bool:
        try:
            r = requests.post(
                f'{self.url}/rest/v1/{table}',
                headers=self.headers, data=json.dumps(data), timeout=10
            )
            if r.status_code in (200, 201):
                return True
            print(f'[Supabase] Insert {table}: {r.status_code} {r.text[:150]}')
            return False
        except Exception as e:
            print(f'[Supabase] Insert error: {e}')
            return False

    def save_snapshot(self, equity: float, cash: float, open_positions: int,
                      pnl: float = 0, pnl_pct: float = 0,
                      market_trend: str = "NEUTRAL", cycle: int = 0,
                      safe_mode: bool = False, **kwargs) -> bool:
        data = {
            'equity': round(equity, 2),
            'cash': round(cash, 2),
            'open_positions': open_positions,
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 6),
            'market_trend': market_trend,
            'cycle_count': cycle,
            'safe_mode': safe_mode,
            'updated_at': self._now(),
        }
        return self._upsert('portfolio_snapshot', data)

    def update_portfolio(self, **kwargs) -> bool:
        return self.save_snapshot(**kwargs)

    def save_trade(self, symbol: str, side: str, qty: float, price: float,
                   pnl: float = 0, confidence: float = 0,
                   market: str = "stocks", **kwargs) -> bool:
        data = {
            'symbol': symbol,
            'side': side,
            'qty': round(float(qty), 6),
            'price': round(float(price), 6),
            'pnl': round(float(pnl), 2),
            'confidence': round(float(confidence), 4),
            'market': market,
            'timestamp': self._now(),
        }
        return self._insert('trades', data)

    def log_trade(self, **kwargs) -> bool:
        return self.save_trade(**kwargs)

    def save_signal(self, symbol: str, action: str, confidence: float,
                    reason: str = "", market: str = "stocks", **kwargs) -> bool:
        data = {
            'symbol': symbol,
            'action': action,
            'confidence': round(float(confidence), 4),
            'reason': str(reason)[:500],
            'market': market,
            'updated_at': self._now(),
        }
        return self._upsert('signals', data)

    def save_signal_analysis(self, **kwargs) -> bool:
        return self.save_signal(**kwargs)

    def log(self, level: str, message: str, **kwargs) -> bool:
        data = {
            'level': level.upper(),
            'message': str(message)[:1000],
            'timestamp': self._now(),
        }
        return self._insert('bot_logs', data)

    def log_message(self, level: str, message: str, **kwargs) -> bool:
        return self.log(level, message)

    def save_equity_point(self, equity: float) -> bool:
        return self._insert('equity_history', {
            'equity': round(float(equity), 2),
            'created_at': self._now(),
        })

    def get_open_positions(self) -> List[Dict]:
        try:
            r = requests.get(f'{self.url}/rest/v1/open_positions?select=*',
                             headers=self.headers, timeout=5)
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []

    def upsert_position(self, symbol: str, qty: float, avg_entry: float,
                        current_price: float, market_value: float,
                        unrealized_pl: float, market: str = "stocks", **kwargs) -> bool:
        data = {
            'symbol': symbol,
            'qty': round(float(qty), 6),
            'avg_entry': round(float(avg_entry), 6),
            'current_price': round(float(current_price), 6),
            'market_value': round(float(market_value), 2),
            'unrealized_pl': round(float(unrealized_pl), 2),
            'market': market,
            'updated_at': self._now(),
        }
        return self._upsert('open_positions', data)

    def update_position(self, **kwargs) -> bool:
        return self.upsert_position(**kwargs)

    def delete_position(self, symbol: str) -> bool:
        try:
            r = requests.delete(
                f'{self.url}/rest/v1/open_positions?symbol=eq.{symbol}',
                headers=self.headers, timeout=5
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    def remove_position(self, symbol: str) -> bool:
        return self.delete_position(symbol)

# Module-level instance pentru compatibilitate cu bot.py
_client = SupabaseClient()

def test_connection(): return _client.test_connection()
def save_snapshot(**kw): return _client.save_snapshot(**kw)
def update_portfolio(**kw): return _client.save_snapshot(**kw)
def save_trade(**kw): return _client.save_trade(**kw)
def log_trade(**kw): return _client.save_trade(**kw)
def save_signal(**kw): return _client.save_signal(**kw)
def save_signal_analysis(**kw): return _client.save_signal(**kw)
def log(level, message, **kw): return _client.log(level, message)
def log_message(level, message, **kw): return _client.log(level, message)
def save_equity_point(equity): return _client.save_equity_point(equity)
def get_open_positions(): return _client.get_open_positions()
def upsert_position(**kw): return _client.upsert_position(**kw)
def update_position(**kw): return _client.upsert_position(**kw)
def delete_position(symbol): return _client.delete_position(symbol)
def remove_position(symbol): return _client.delete_position(symbol)

# Module-level instance pentru compatibilitate cu bot.py
_client = SupabaseClient()

def test_connection(): return _client.test_connection()
def save_snapshot(**kw): return _client.save_snapshot(**kw)
def update_portfolio(**kw): return _client.save_snapshot(**kw)
def save_trade(**kw): return _client.save_trade(**kw)
def log_trade(**kw): return _client.save_trade(**kw)
def save_signal(**kw): return _client.save_signal(**kw)
def save_signal_analysis(**kw): return _client.save_signal(**kw)
def log(level, message, **kw): return _client.log(level, message)
def log_message(level, message, **kw): return _client.log(level, message)
def save_equity_point(equity): return _client.save_equity_point(equity)
def get_open_positions(): return _client.get_open_positions()
def upsert_position(**kw): return _client.upsert_position(**kw)
def update_position(**kw): return _client.upsert_position(**kw)
def delete_position(symbol): return _client.delete_position(symbol)
def remove_position(symbol): return _client.delete_position(symbol)

def push_signal(symbol=None, action=None, confidence=None, price=None, tech=None, reasoning=None, risk=None, can_trade=None, reason=None, market=None, **kw): return save_signal(symbol=symbol, action=action or "HOLD", confidence=float(confidence or 0), reason=str(reasoning or reason or ""), market=str(market or "stock"))
def push_trade(**kw): return save_trade(**kw)
def push_portfolio(**kw): return save_snapshot(**kw)
def push_positions(positions):
    if not positions: return True
    for p in positions:
        if isinstance(p, dict): upsert_position(**p)
    return True
