#!/usr/bin/env python3
"""
crypto_dashboard.py — V5 Simple & Robust
"""
import os, sys
from datetime import datetime

# Set paths BEFORE any imports
os.chdir('/opt/neurotrade-v5')
if '/opt/neurotrade-v5' not in sys.path:
    sys.path.insert(0, '/opt/neurotrade-v5')
if '/opt/neurotrade' not in sys.path:
    sys.path.insert(0, '/opt/neurotrade')

print("\n" + "=" * 70)
print(f"🚀 NEUROTRADE V5 DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# Sentiment
print("\n📊 AI SENTIMENT:")
try:
    import sentiment_analyzer as sentiment
    for coin in ['BTC', 'ETH', 'SOL', 'ADA', 'DOGE']:
        s = sentiment.sentiment_analyzer.get_aggregate_sentiment(coin)
        ok, sig, _ = sentiment.sentiment_analyzer.should_trade(coin, leverage=10, min_confidence=50)
        emoji = {'bullish': '🟢', 'bearish': '🔴', 'neutral': '🟡'}
        trade = '✓ '+sig.upper() if ok else '✗ HOLD'
        print(f"   {emoji.get(s['trend'], '🟡')} {coin}: {s['trend']:<10} Score: {s['score']:+.3f} Conf: {s['confidence']:>3}% | {trade}")
except Exception as e:
    print(f"   ❌ {e}")

# Binance
print("\n🪙 BINANCE TESTNET:")
try:
    import binance_client as bn
    conn = bn.binance.test_connection()
    conf = bn.binance.is_configured()
    print(f"   Connection: {'✓' if conn else '✗'}")
    print(f"   Configured: {'✓' if conf else '✗'}")
    if conn and conf:
        orders = bn.binance.get_open_orders()
        print(f"   Open Orders: {len(orders)}")
        for coin in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
            t = bn.binance.get_ticker(coin)
            if t and t.get('last'):
                print(f"   📈 {coin}: ${t['last']:,.2f}")
except Exception as e:
    print(f"   ❌ {e}")

# Services
print("\n🤖 SERVICES:")
for svc in ['neurotrade.service', 'neurotrade-v2.service', 'neurotrade-v5.service']:
    try:
        import subprocess
        r = subprocess.run(['systemctl', 'is-active', svc], capture_output=True, text=True)
        print(f"   {svc.replace('.service', '')}: {'✓' if r.stdout.strip()=='active' else '✗'}")
    except:
        print(f"   {svc}: ?")

print("\n" + "=" * 70)
print("📊 DEMO MODE | 🔗 testnet.binance.vision")
print("=" * 70 + "\n")
