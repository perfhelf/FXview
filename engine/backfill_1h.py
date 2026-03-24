"""
FXview — 1H OHLC Backfill Script (One-Time)

Downloads up to 10 months of 1H data from Yahoo Finance and
upserts it into the ohlc_1h_archive table in Supabase.

This is meant to be run ONCE to bootstrap historical data,
so the signal engine immediately has enough depth for
RSI 369-SMA calculations.

Usage:
    python engine/backfill_1h.py
"""

import os
import sys
import time
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client

# ==========================================
# Config
# ==========================================

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Import ticker mappings from signal engine
sys.path.insert(0, os.path.dirname(__file__))
from signal_8h import get_all_yahoo_tickers

# ==========================================
# Backfill Logic
# ==========================================

def download_1h_history(ticker, period="300d"):
    """
    Download 1H data for a single ticker.
    Uses individual download (not batch) for reliability with long periods.
    """
    try:
        df = yf.download(
            ticker,
            period=period,
            interval="1h",
            progress=False,
        )
        if df.empty:
            return pd.DataFrame()
        
        # Handle MultiIndex columns from single-ticker download
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df = df[['Open', 'High', 'Low', 'Close']].dropna()
        return df
    except Exception as e:
        print(f"    ⚠️ Download failed: {e}")
        return pd.DataFrame()


def upsert_to_archive(sb, ticker, df):
    """Upsert DataFrame rows to ohlc_1h_archive table."""
    if df.empty:
        return 0
    
    rows = []
    for ts, row in df.iterrows():
        if hasattr(ts, 'tz') and ts.tz is not None:
            ts_str = ts.tz_convert('UTC').strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            ts_str = ts.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        rows.append({
            'ticker': ticker,
            'ts': ts_str,
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
        })
    
    total = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i+500]
        try:
            sb.table('ohlc_1h_archive').upsert(chunk, on_conflict='ticker,ts').execute()
            total += len(chunk)
        except Exception as e:
            print(f"    ⚠️ Upsert failed (chunk {i}): {e}")
    
    return total


def main():
    print("=" * 60)
    print("FXview — 1H OHLC Backfill (One-Time)")
    print(f"Run Time: {datetime.utcnow().isoformat()}Z")
    print(f"Target: 300 days (~10 months) of 1H data")
    print("=" * 60)
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    tickers = get_all_yahoo_tickers()
    
    print(f"\nBackfilling {len(tickers)} tickers...\n")
    
    total_rows = 0
    success_count = 0
    fail_count = 0
    
    for i, ticker in enumerate(tickers):
        print(f"  [{i+1}/{len(tickers)}] {ticker}...", end=" ", flush=True)
        
        # Download with retry
        df = pd.DataFrame()
        for attempt in range(3):
            df = download_1h_history(ticker, period="300d")
            if not df.empty:
                break
            if attempt < 2:
                print(f"retry {attempt+2}...", end=" ", flush=True)
                time.sleep(2)
        
        if df.empty:
            print("❌ no data")
            fail_count += 1
            continue
        
        # Upsert to archive
        rows = upsert_to_archive(sb, ticker, df)
        total_rows += rows
        success_count += 1
        
        # Show date range
        earliest = df.index[0]
        latest = df.index[-1]
        print(f"✅ {rows} rows ({earliest.strftime('%Y-%m-%d')} → {latest.strftime('%Y-%m-%d')})")
        
        # Rate limit: small delay between tickers
        time.sleep(0.5)
    
    print(f"\n{'=' * 60}")
    print(f"Backfill complete: {success_count} success, {fail_count} failed")
    print(f"Total rows archived: {total_rows}")
    print(f"{'=' * 60}")
    
    # Verify archive depth
    print("\nVerifying archive depth...")
    result = sb.table('ohlc_1h_archive') \
        .select('ticker') \
        .execute()
    
    if result.data:
        total = len(result.data)
        # Get a sample
        sample = sb.table('ohlc_1h_archive') \
            .select('ts') \
            .eq('ticker', 'EURUSD=X') \
            .order('ts') \
            .limit(1) \
            .execute()
        if sample.data:
            earliest = sample.data[0]['ts']
            print(f"  Archive total: {total} rows")
            print(f"  EURUSD earliest: {earliest}")
    
    print("\nDone. ✅")


if __name__ == "__main__":
    main()
