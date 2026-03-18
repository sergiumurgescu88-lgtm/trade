#!/usr/bin/env python3
"""
crypto_dashboard.py — Fixed Dashboard
"""
import sys, os
sys.path.insert(0, '/opt/neurotrade')
os.chdir('/opt/neurotrade')
from datetime import datetime

print("\n" + "=" * 70)
print(f"🚀 NEUROTRADE DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# Sentiment
try:
    import sentiment_analyzer as sentiment
    print("✓ Sentiment Analyzer: OK")
    print(f"\n📊 AI SENTIMENT:")
    for coin in ['BTC', 'ETH', 'SOL', 'ADA', 'DOGE']:
        s = sentiment.sentiment_analyzer.get_aggregate_sentiment(coin)
        ok, sig, _ = sentiment.sentiment_analyzer.should_trade(coin, leverage=10, min_confidence=50)
        emoji = {'bullish': '🟢', 'bearish': '🔴', 'neutral': '🟡'}
        trade = '✓ '+sig.upper() if ok else '✗ HOLD'
        print(f"   {emoji.get(s['trend'], '🟡')} {coin}: {s['trend']:<10} Score: {s['score']:+.3f} Conf: {s['confidence']:>3}% | {trade}")
except Exception as e:
    print(f"❌ Sentiment: {e}")

# Kraken
try:
    import kraken_client as kraken
    if kraken.kraken.test_connection():
        print(f"\n✓ Kraken: Connected")
        print(f"   Configured: {kraken.kraken.is_configured()}")
        if kraken.kraken.is_configured():
            margin = kraken.kraken.get_margin_balance()
            status = kraken.kraken.check_margin_level()
            print(f"   Equity: ${margin.get('equity',0):,.2f}")
            print(f"   Margin Level: {status['level']}% ({status['risk']})")
            positions = kraken.kraken.get_open_positions()
            print(f"   Open Positions: {len(positions)}")
        else:
            print(f"   ⚠️  Add API keys for trading")
    else:
        print(f"\n⚠️  Kraken: Connection issue")
except Exception as e:
    print(f"\n⚠️  Kraken: {e}")

print("\n" + "=" * 70)
print("📊 Dashboard: python3 /opt/neurotrade/crypto_dashboard.py")
print("📰 Sentiment: CryptoPanic + NewsAPI + CoinGecko fallback")
print("🔑 Kraken: Add keys at kraken.com/u/security/api")
print("=" * 70 + "\n")
