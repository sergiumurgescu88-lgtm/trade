"""
sentiment_analyzer.py — Fixed with Fallback Data
"""
import requests, logging, json, re
from datetime import datetime, timedelta

log = logging.getLogger("Sentiment")

# API Keys
CRYPTOPANIC_KEY = "59c682c8661c29f5deba8df58e40b754751b80c4"
CRYPTOPANIC_URL = "https://cryptopanic.com/api/developer/v1"
NEWSAPI_KEY = "905f5a50045a48e3a4a7388fd6d50ac8"
NEWSAPI_URL = "https://newsapi.org/v2/everything"

class CryptoSentimentAnalyzer:
    def __init__(self):
        self.POSITIVE = ['bullish','rally','surge','breakout','adoption','partnership','upgrade','positive','gain','etf','approval','launch','milestone']
        self.NEGATIVE = ['bearish','crash','dump','hack','exploit','ban','regulation','lawsuit','negative','loss','sec','fraud','investigation','warning']
        self._cache = {}
        self._fallback_data = {
            'BTC': {'score': 0.15, 'trend': 'neutral', 'confidence': 45},
            'ETH': {'score': 0.10, 'trend': 'neutral', 'confidence': 40},
            'SOL': {'score': 0.20, 'trend': 'neutral', 'confidence': 35},
            'ADA': {'score': 0.05, 'trend': 'neutral', 'confidence': 30},
            'DOGE': {'score': 0.12, 'trend': 'neutral', 'confidence': 35}
        }
        
    def _get_cryptopanic(self, currency: str = 'BTC', limit: int = 10) -> list:
        try:
            r = requests.get(f"{CRYPTOPANIC_URL}/posts/", params={
                'auth_token': CRYPTOPANIC_KEY, 'currencies': currency, 'kind': 'news', 'public': 'true', 'limit': limit
            }, timeout=8)
            if r.status_code == 200:
                results = r.json().get('results', [])
                return [{'title': i.get('title',''), 'sentiment': i.get('sentiment',{}).get('type','neutral')} for i in results[:limit]]
        except Exception as e:
            log.debug(f"CryptoPanic: {e}")
        return []
    
    def _get_newsapi(self, query: str = 'bitcoin', limit: int = 5) -> list:
        try:
            r = requests.get(NEWSAPI_URL, params={'q': query, 'apiKey': NEWSAPI_KEY, 'language': 'en', 'sortBy': 'publishedAt', 'pageSize': limit}, timeout=8)
            if r.status_code == 200:
                articles = r.json().get('articles', [])
                return [{'title': a.get('title',''), 'description': a.get('description','')} for a in articles[:limit]]
        except Exception as e:
            log.debug(f"NewsAPI: {e}")
        return []
    
    def _analyze_text(self, text: str) -> float:
        text_lower = text.lower()
        pos = sum(1 for w in self.POSITIVE if w in text_lower)
        neg = sum(1 for w in self.NEGATIVE if w in text_lower)
        total = pos + neg
        return (pos - neg) / total if total > 0 else 0.0
    
    def _get_market_sentiment(self, currency: str) -> float:
        """Fallback: Use price-based sentiment from CoinGecko"""
        try:
            coin_ids = {'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana', 'ADA': 'cardano', 'DOGE': 'dogecoin'}
            coin_id = coin_ids.get(currency, 'bitcoin')
            r = requests.get(f'https://api.coingecko.com/api/v3/coins/{coin_id}', timeout=8)
            if r.status_code == 200:
                data = r.json()
                change_24h = data.get('market_data', {}).get('price_change_percentage_24h', 0)
                # Convert price change to sentiment score
                if change_24h > 5: return 0.5
                elif change_24h > 2: return 0.3
                elif change_24h > 0: return 0.1
                elif change_24h < -5: return -0.5
                elif change_24h < -2: return -0.3
                else: return 0.0
        except:
            pass
        return self._fallback_data.get(currency, {}).get('score', 0.0)
    
    def get_aggregate_sentiment(self, currency: str = 'BTC') -> dict:
        cache_key = f"{currency}_{datetime.now().strftime('%Y%m%d%H')}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        cp = self._get_cryptopanic(currency, 10)
        na = self._get_newsapi(currency.lower(), 5)
        all_news = cp + na
        
        scores = []
        for a in all_news[:15]:
            text = a.get('title','') + ' ' + a.get('description','')
            if text.strip():
                score = self._analyze_text(text)
                if a.get('sentiment') == 'positive': score = min(1.0, score + 0.2)
                elif a.get('sentiment') == 'negative': score = max(-1.0, score - 0.2)
                scores.append(score)
        
        # If no news, use market-based sentiment
        if not scores:
            market_score = self._get_market_sentiment(currency)
            scores = [market_score]
            news_count = 0
        else:
            news_count = len(all_news)
        
        avg = sum(scores) / len(scores) if scores else 0.0
        conf = min(100, len(scores) * 8 + news_count * 3)
        
        # Determine trend
        if avg > 0.25: trend = 'bullish'
        elif avg < -0.25: trend = 'bearish'
        else: trend = 'neutral'
        
        signal = 'buy' if trend == 'bullish' and conf > 50 else 'sell' if trend == 'bearish' and conf > 50 else 'hold'
        
        result = {'score': round(avg, 3), 'confidence': conf, 'news_count': news_count, 'trend': trend, 'signal': signal, 'timestamp': datetime.now().isoformat()}
        self._cache[cache_key] = result
        return result
    
    def should_trade(self, currency: str = 'BTC', min_confidence: int = 70, min_score: float = 0.35, leverage: int = 10):
        s = self.get_aggregate_sentiment(currency)
        if s['confidence'] < min_confidence: return False, 'hold', s
        if leverage >= 10: min_score = 0.4
        if s['score'] >= min_score and s['trend'] == 'bullish': return True, 'buy', s
        elif s['score'] <= -min_score and s['trend'] == 'bearish': return True, 'sell', s
        return False, 'hold', s

sentiment_analyzer = CryptoSentimentAnalyzer()

if __name__ == "__main__":
    print("=" * 60)
    print("📊 SENTIMENT ANALYZER")
    print("=" * 60)
    for coin in ['BTC', 'ETH', 'SOL', 'ADA', 'DOGE']:
        s = sentiment_analyzer.get_aggregate_sentiment(coin)
        ok, sig, _ = sentiment_analyzer.should_trade(coin, leverage=10, min_confidence=50)
        emoji = {'bullish': '🟢', 'bearish': '🔴', 'neutral': '🟡'}
        print(f"{emoji.get(s['trend'], '🟡')} {coin}: {s['trend']:<10} Score: {s['score']:+.3f} Conf: {s['confidence']}% | {'✓ '+sig if ok else '✗ HOLD'}")
    print("=" * 60)
