-- ============================================================
-- NEUROTRADE BOT v2 — SUPABASE SETUP
-- Ruleaza asta in SQL Editor din Supabase Dashboard
-- ============================================================

-- 1. PORTFOLIO SNAPSHOT (o singura inregistrare, mereu actualizata)
CREATE TABLE IF NOT EXISTS portfolio_snapshot (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    cycle           INTEGER DEFAULT 0,
    equity          NUMERIC(12,2) DEFAULT 0,
    cash            NUMERIC(12,2) DEFAULT 0,
    buying_power    NUMERIC(12,2) DEFAULT 0,
    pnl             NUMERIC(12,2) DEFAULT 0,
    pnl_pct         NUMERIC(8,4)  DEFAULT 0,
    safe_mode        BOOLEAN DEFAULT FALSE,
    spy_change_pct  NUMERIC(6,3)  DEFAULT 0,
    market_trend    TEXT DEFAULT 'NEUTRAL',
    open_positions  INTEGER DEFAULT 0,
    total_trades    INTEGER DEFAULT 0,
    total_pl        NUMERIC(12,2) DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Insereaza randul initial (daca nu exista)
INSERT INTO portfolio_snapshot (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;


-- 2. OPEN POSITIONS (pozitii deschise, sterse si recreate la fiecare ciclu)
CREATE TABLE IF NOT EXISTS open_positions (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    qty             NUMERIC(10,4) DEFAULT 0,
    avg_entry       NUMERIC(12,4) DEFAULT 0,
    current_price   NUMERIC(12,4) DEFAULT 0,
    market_value    NUMERIC(12,2) DEFAULT 0,
    unrealized_pl   NUMERIC(12,2) DEFAULT 0,
    unrealized_pct  NUMERIC(8,4)  DEFAULT 0,
    stop_loss       NUMERIC(12,4) DEFAULT 0,
    take_profit     NUMERIC(12,4) DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);


-- 3. SIGNALS (semnale Gemini, unul per simbol, actualizat la fiecare ciclu)
CREATE TABLE IF NOT EXISTS signals (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    action          TEXT DEFAULT 'HOLD',     -- BUY / SELL / HOLD
    confidence      INTEGER DEFAULT 0,
    price           NUMERIC(12,4) DEFAULT 0,
    rsi             NUMERIC(6,2)  DEFAULT 0,
    macd            TEXT DEFAULT 'none',
    ema_trend       TEXT DEFAULT 'neutral',
    tech_score      INTEGER DEFAULT 0,
    reasoning       TEXT DEFAULT '',
    risk_level      TEXT DEFAULT 'LOW',
    executed        BOOLEAN DEFAULT FALSE,
    block_reason    TEXT DEFAULT '',
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);


-- 4. TRADES (istoric tranzactii, append-only)
CREATE TABLE IF NOT EXISTS trades (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    action          TEXT NOT NULL,           -- BUY / SELL
    qty             INTEGER DEFAULT 0,
    price           NUMERIC(12,4) DEFAULT 0,
    value           NUMERIC(12,2) DEFAULT 0,
    confidence      INTEGER DEFAULT 0,
    close_type      TEXT DEFAULT 'SIGNAL',  -- SIGNAL / STOP_LOSS / TAKE_PROFIT / TRAILING_STOP
    pl              NUMERIC(12,2) DEFAULT 0,
    order_id        TEXT DEFAULT '',
    timestamp       TIMESTAMPTZ DEFAULT NOW()
);


-- 5. CYCLE LOGS (log-uri live, ultimele 200)
CREATE TABLE IF NOT EXISTS cycle_logs (
    id          BIGSERIAL PRIMARY KEY,
    cycle       INTEGER DEFAULT 0,
    level       TEXT DEFAULT 'INFO',        -- INFO / WARNING / ERROR
    message     TEXT DEFAULT '',
    timestamp   TIMESTAMPTZ DEFAULT NOW()
);

-- Index pentru performanta
CREATE INDEX IF NOT EXISTS idx_trades_timestamp    ON trades(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_symbol       ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_symbol      ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_cycle_logs_ts       ON cycle_logs(timestamp DESC);


-- 6. REALTIME — activeaza pentru toate tabelele
-- (din Supabase Dashboard: Database → Replication → toggle ON pentru fiecare tabel)


-- 7. ROW LEVEL SECURITY — permite citire publica pentru dashboard
ALTER TABLE portfolio_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE open_positions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals            ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades             ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycle_logs         ENABLE ROW LEVEL SECURITY;

-- Politici: toata lumea poate citi (dashboard-ul Lovable are nevoie de asta)
CREATE POLICY "public read portfolio" ON portfolio_snapshot FOR SELECT USING (true);
CREATE POLICY "public read positions" ON open_positions     FOR SELECT USING (true);
CREATE POLICY "public read signals"   ON signals            FOR SELECT USING (true);
CREATE POLICY "public read trades"    ON trades             FOR SELECT USING (true);
CREATE POLICY "public read logs"      ON cycle_logs         FOR SELECT USING (true);

-- Politici: doar service_role poate scrie (botul foloseste anon key cu INSERT permis)
-- IMPORTANT: In Supabase Dashboard → Authentication → Policies,
-- daca vrei sa pastrezi securitate maxima, schimba botul sa foloseasca SERVICE_ROLE key
-- Pentru test rapid, poti permite INSERT cu anon key:
CREATE POLICY "anon insert portfolio" ON portfolio_snapshot FOR INSERT WITH CHECK (true);
CREATE POLICY "anon insert positions" ON open_positions     FOR INSERT WITH CHECK (true);
CREATE POLICY "anon upsert positions" ON open_positions     FOR DELETE USING (true);
CREATE POLICY "anon insert signals"   ON signals            FOR INSERT WITH CHECK (true);
CREATE POLICY "anon delete signals"   ON signals            FOR DELETE USING (true);
CREATE POLICY "anon insert trades"    ON trades             FOR INSERT WITH CHECK (true);
CREATE POLICY "anon insert logs"      ON cycle_logs         FOR INSERT WITH CHECK (true);
CREATE POLICY "anon update portfolio" ON portfolio_snapshot FOR UPDATE USING (true);

-- ============================================================
-- GATA! Acum configureaza supabase_client.py cu URL si KEY-ul tau.
-- ============================================================
