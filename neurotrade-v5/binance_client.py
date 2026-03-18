"""
binance_client.py — Binance Testnet Client (Path-Fixed)
"""
import requests, hmac, hashlib, time, logging, sys, os
from urllib.parse import urlencode

log = logging.getLogger("Binance")

# FIX: Try multiple config paths
BINANCE_API_KEY = ""
BINANCE_SECRET_KEY = ""
BINANCE_BASE_URL = "https://testnet.binance.vision/api/v3"
BINANCE_TESTNET = True

# Try to load from config
for config_path in ['/opt/neurotrade-v5/config.py', '/opt/neurotrade/config.py']:
    if os.path.exists(config_path):
        try:
            config_dir = os.path.dirname(config_path)
            if config_dir not in sys.path:
                sys.path.insert(0, config_dir)
            exec(open(config_path).read())
            break
        except:
            pass

# Override with hardcoded testnet keys if still empty
if not BINANCE_API_KEY or len(BINANCE_API_KEY) < 10:
    BINANCE_API_KEY = "mJUa3UJy5oQocSDbubuXUsWK5S02YIsQ4wDx3BxYvUsnYXhpZ61pFtBfy2MCfClm"
    BINANCE_SECRET_KEY = "8fXXbxW3Or9bsTcj36uIJDef4d5xmXoT50ELEg22Ne4lS6AYy3ND7GnsZMms53uD"

class BinanceClient:
    def __init__(self):
        self.api_key = BINANCE_API_KEY
        self.secret = BINANCE_SECRET_KEY
        self.base_url = BINANCE_BASE_URL
        self.testnet = BINANCE_TESTNET
        self.session = requests.Session()
        self._configured = bool(self.api_key and len(self.api_key) > 10)
        log.info(f"Binance initialized: configured={self._configured}, url={self.base_url}")
        
    def _generate_signature(self, query_string: str) -> str:
        return hmac.new(self.secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    
    def _request(self, method: str, endpoint: str, params=None, signed=False):
        if not self._configured:
            return None
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params['timestamp'] = int(time.time() * 1000)
        query_string = urlencode(params)
        if signed:
            signature = self._generate_signature(query_string)
            params['signature'] = signature
        headers = {'X-MBX-APIKEY': self.api_key}
        try:
            if method == 'GET':
                response = self.session.get(url, params=params, headers=headers, timeout=10)
            else:
                response = self.session.post(url, params=params, headers=headers, timeout=10)
            result = response.json()
            if isinstance(result, dict) and result.get('code', 0) < 0:
                return None
            return result
        except Exception as e:
            log.debug(f"Binance error: {e}")
            return None
    
    def get_ticker(self, symbol: str) -> dict:
        result = self._request('GET', '/ticker/price', {'symbol': symbol})
        if result and 'price' in result:
            return {'last': float(result['price']), 'symbol': symbol}
        return {}
    
    def get_klines(self, symbol: str, interval: str = '5m', limit: int = 60) -> list:
        result = self._request('GET', '/klines', {'symbol': symbol, 'interval': interval, 'limit': limit})
        if result and isinstance(result, list):
            return [{'timestamp': k[0], 'open': float(k[1]), 'high': float(k[2]), 
                    'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])} for k in result]
        return []
    
    def get_balance(self) -> dict:
        result = self._request('GET', '/account', signed=True)
        if result and isinstance(result, dict) and 'balances' in result:
            return {b['asset']: {'free': float(b['free']), 'locked': float(b['locked'])} 
                    for b in result['balances'] if float(b['free']) > 0}
        return {}
    
    def get_open_orders(self) -> list:
        result = self._request('GET', '/openOrders', {'symbol': 'BTCUSDT'}, signed=True)
        if result and isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            return [{'symbol': o.get('symbol', ''), 'side': o.get('side', ''), 
                    'quantity': float(o.get('origQty', 0)), 'price': float(o.get('price', 0)),
                    'order_id': o.get('orderId', 0)} for o in result]
        return []
    
    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = 'MARKET', price: float = None) -> dict:
        params = {'symbol': symbol, 'side': side, 'type': order_type, 'quantity': str(quantity)}
        if order_type == 'LIMIT' and price:
            params['price'] = str(price)
            params['timeInForce'] = 'GTC'
        result = self._request('POST', '/order', params, signed=True)
        if result and isinstance(result, dict):
            return {'order_id': result.get('orderId', ''), 'status': result.get('status', ''),
                    'symbol': symbol, 'side': side, 'quantity': quantity}
        return {}
    
    def cancel_order(self, symbol: str, order_id: int) -> bool:
        result = self._request('DELETE', '/order', {'symbol': symbol, 'orderId': order_id}, signed=True)
        return result is not None
    
    def close_position(self, symbol: str, side: str, quantity: float) -> dict:
        close_side = 'SELL' if side == 'BUY' else 'BUY'
        return self.place_order(symbol, close_side, quantity)
    
    def test_connection(self) -> bool:
        try:
            result = self._request('GET', '/ping')
            return result is not None
        except:
            return False
    
    def is_configured(self) -> bool:
        return self._configured

binance = BinanceClient()

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 BINANCE TESTNET - TEST")
    print("=" * 60)
    print(f"✓ Connected: {binance.test_connection()}")
    print(f"⚙️  Configured: {binance.is_configured()}")
    print(f"🔑 API Key: {binance.api_key[:10]}...")
    if binance.is_configured():
        print(f"💰 Balance: {binance.get_balance()}")
        print(f"📍 Open Orders: {binance.get_open_orders()}")
        for coin in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
            ticker = binance.get_ticker(coin)
            if ticker:
                print(f"📈 {coin}: ${ticker.get('last', 'N/A'):,.2f}")
    print("=" * 60)
