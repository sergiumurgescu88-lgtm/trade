"""
kraken_client.py — Fixed v2
"""
import requests, hmac, hashlib, base64, time, logging, json
from urllib.parse import urlencode

log = logging.getLogger("Kraken")

try:
    from config import KRAKEN_API_KEY, KRAKEN_SECRET_KEY, KRAKEN_BASE_URL
except:
    KRAKEN_API_KEY = ""
    KRAKEN_SECRET_KEY = ""
    KRAKEN_BASE_URL = "https://api.kraken.com"

class KrakenClient:
    def __init__(self):
        self.api_key = KRAKEN_API_KEY
        self.secret = KRAKEN_SECRET_KEY
        self.base_url = KRAKEN_BASE_URL
        self.session = requests.Session()
        self._configured = bool(self.api_key and len(self.api_key) > 20)
        
    def _generate_signature(self, urlpath: str, postdata: dict) -> str:
        encoded = urlencode(postdata).encode()
        sha256 = hashlib.sha256(postdata['nonce'].encode() + encoded).digest()
        secret = self.secret
        missing_padding = len(secret) % 4
        if missing_padding:
            secret += '=' * (4 - missing_padding)
        decode = base64.b64decode(secret)
        sig = hmac.new(decode, urlpath.encode() + sha256, hashlib.sha512)
        return base64.b64encode(sig.digest()).decode()
    
    def _request(self, endpoint: str, postdata=None, public=False):
        """FIXED: Renamed 'data' to 'postdata' to avoid conflict"""
        if not self._configured and not public:
            return None
        url = f"{self.base_url}{endpoint}"
        if postdata is None:
            postdata = {}
        if not public:
            postdata['nonce'] = str(int(time.time() * 1000))
            signature = self._generate_signature(endpoint, postdata)
            headers = {'API-Key': self.api_key, 'API-Sign': signature}
        else:
            headers = {}
        try:
            response = self.session.post(url, data=postdata, headers=headers, timeout=10)
            result = response.json()
            if result.get('error'):
                return None
            return result.get('result', {})
        except Exception as e:
            log.debug(f"Kraken error: {e}")
            return None
    
    def get_ticker(self, pair: str) -> dict:
        kraken_pair = self._format_pair(pair)
        result = self._request('/0/public/Ticker', {'pair': kraken_pair}, public=True)
        if result:
            for key, value in result.items():
                return {'bid': float(value['b'][0]), 'ask': float(value['a'][0]),
                        'last': float(value['c'][0]), 'volume': float(value['v'][1])}
        return {}
    
    def get_balance(self) -> dict:
        if not self._configured:
            return {}
        result = self._request('/0/private/Balance')
        return {k: float(v) for k, v in result.items()} if result else {}
    
    def get_margin_balance(self) -> dict:
        if not self._configured:
            return {'equity': 0, 'margin_balance': 0, 'unrealized_pl': 0}
        result = self._request('/0/private/T Margins')
        if result:
            return {'equity': float(result.get('n', 0)), 'margin_balance': float(result.get('m', 0)),
                    'unrealized_pl': float(result.get('u', 0))}
        return {'equity': 0, 'margin_balance': 0, 'unrealized_pl': 0}
    
    def get_open_positions(self) -> list:
        if not self._configured:
            return []
        result = self._request('/0/private/OpenPositions')
        if result:
            positions = []
            for pos_id, pos in result.items():
                vol = float(pos['vol'])
                positions.append({
                    'id': pos_id, 'symbol': self._unformat_pair(pos['pair']),
                    'size': abs(vol), 'entry_price': float(pos['price']),
                    'current_price': float(pos.get('ccol', 0) or pos['price']),
                    'unrealized_pl': float(pos.get('float', 0) or 0),
                    'unrealized_pl_pct': (float(pos.get('float', 0) or 0) / (float(pos['price']) * abs(vol)) * 100) if (float(pos['price']) * abs(vol)) > 0 else 0,
                    'side': 'long' if vol > 0 else 'short',
                    'leverage': int(pos.get('leverage', 1)),
                    'margin_used': float(pos.get('margin', 0) or 0)
                })
            return positions
        return []
    
    def place_order(self, pair: str, side: str, volume: float, order_type: str = 'market', leverage: int = 1) -> dict:
        if not self._configured:
            return {}
        kraken_pair = self._format_pair(pair)
        postdata = {'pair': kraken_pair, 'side': side, 'type': order_type, 'volume': str(volume), 'leverage': str(leverage)}
        result = self._request('/0/private/AddOrder', postdata)
        if result:
            return {'order_id': result.get('txid', [''])[0], 'status': 'opened', 'leverage': leverage}
        return {}
    
    def close_position(self, pos_id: str, reason: str = '') -> dict:
        positions = self.get_open_positions()
        pos = next((p for p in positions if p['id'] == pos_id), None)
        if not pos: return {}
        side = 'sell' if pos['side'] == 'long' else 'buy'
        return self.place_order(pos['symbol'], side, abs(pos['size']), leverage=1)
    
    def close_all_positions(self, reason: str = 'Emergency') -> list:
        positions = self.get_open_positions()
        return [p['symbol'] for p in positions if self.close_position(p['id'], reason)]
    
    def check_margin_level(self) -> dict:
        if not self._configured:
            return {'level': 100, 'risk': 'low', 'liquidation_risk': False, 'equity': 0, 'margin_used': 0}
        margin = self.get_margin_balance()
        positions = self.get_open_positions()
        equity = margin.get('equity', 0)
        if equity <= 0:
            return {'level': 100, 'risk': 'low', 'liquidation_risk': False, 'equity': 0, 'margin_used': 0}
        margin_used = sum(p.get('margin_used', 0) for p in positions)
        if margin_used <= 0:
            return {'level': 100, 'risk': 'low', 'liquidation_risk': False, 'equity': equity, 'margin_used': 0}
        level = (equity / margin_used) * 100
        risk = 'CRITICAL' if level < 120 else 'HIGH' if level < 150 else 'MEDIUM' if level < 200 else 'LOW'
        return {'level': round(level, 2), 'risk': risk, 'liquidation_risk': level < 150, 'equity': equity, 'margin_used': margin_used}
    
    def check_position_risk(self, position: dict) -> dict:
        maintenance = 0.05
        initial = 1 / max(position['leverage'], 1)
        liq_price = position['entry_price'] * (1 - (initial - maintenance)) if position['side'] == 'long' else position['entry_price'] * (1 + (initial - maintenance))
        dist = abs(position['current_price'] - liq_price) / position['current_price'] * 100
        return {'liquidation_price': round(liq_price, 2), 'distance_to_liq_pct': round(dist, 2),
                'risk': 'CRITICAL' if dist < 5 else 'HIGH' if dist < 10 else 'MEDIUM' if dist < 20 else 'LOW'}
    
    def get_effective_leverage(self) -> float:
        if not self._configured:
            return 0
        margin = self.get_margin_balance()
        positions = self.get_open_positions()
        equity = margin.get('equity', 0)
        if equity <= 0: return 0
        total_value = sum(abs(p['size'] * p['current_price']) for p in positions)
        return round(total_value / equity, 2)
    
    def _format_pair(self, pair: str) -> str:
        pair = pair.replace('/', '').replace('USDT', 'USD')
        if pair.startswith('BTC'): pair = pair.replace('BTC', 'XBT')
        return pair.upper()
    
    def _unformat_pair(self, pair: str) -> str:
        pair = pair.replace('XBT', 'BTC')
        if pair.endswith('USD'): pair = pair.replace('USD', 'USDT')
        return f"{pair[:3]}/{pair[3:]}"
    
    def test_connection(self) -> bool:
        try:
            result = self._request('/0/public/Time', public=True)
            return result is not None
        except:
            return False
    
    def is_configured(self) -> bool:
        return self._configured

kraken = KrakenClient()

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 KRAKEN TEST")
    print("=" * 60)
    print(f"✓ Connected: {kraken.test_connection()}")
    print(f"⚙️  Configured: {kraken.is_configured()}")
    if kraken.is_configured():
        print(f"💰 Balance: {kraken.get_balance()}")
        print(f"📊 Margin: {kraken.get_margin_balance()}")
        print(f"⚠️  Margin Level: {kraken.check_margin_level()}")
    else:
        print("⚠️  Kraken not configured - using demo mode")
    print("=" * 60)
