#!/usr/bin/env python3
"""Sync Hermes equity la Supabase la fiecare 5 minute"""
import requests, subprocess, re, time, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger("HermesSync")

KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqeXl5dWl6c2ZycXBqb2d3ZnNlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzQ5OTQ2NCwiZXhwIjoyMDg5MDc1NDY0fQ.NDyJMccbMkbfIARLxLLMZmUEIYvla8hLx69rR89X-N0"
URL = "https://rjyyyuizsfrqpjogwfse.supabase.co"
INITIAL = 20000

def sync():
    try:
        out = subprocess.run(['journalctl','-u','neurotrade-hermes','--since','10 minutes ago','--no-pager'],
            capture_output=True, text=True).stdout
        eq_matches = re.findall(r'equity=\$([\d,]+\.?\d*)', out)
        pos_matches = re.findall(r'(\d+)/4 pos', out)
        if not eq_matches:
            log.warning("Nu gasesc equity in log")
            return
        eq = float(eq_matches[-1].replace(',',''))
        n_pos = int(pos_matches[-1]) if pos_matches else 0
        pnl = eq - INITIAL
        pnl_pct = (pnl / INITIAL) * 100
        h = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
        r = requests.patch(f"{URL}/rest/v1/portfolio_snapshot?id=eq.1",
            headers=h, json={"equity": eq, "cash": eq * 0.75,
                "pnl": pnl, "pnl_pct": pnl_pct, "total_pl": pnl,
                "open_positions": n_pos, "updated_at": "now()"}, timeout=5)
        log.info(f"Hermes sync: ${eq:,.2f} pnl={pnl:+,.2f} pos={n_pos} → {r.status_code}")
    except Exception as e:
        log.error(f"Sync error: {e}")

while True:
    sync()
    time.sleep(300)
