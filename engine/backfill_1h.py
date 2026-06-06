"""
FXview — 1H OHLC archive backfill.

This is the historical-data warehouse clerk for the 8H signal engine. The
daily engine only needs a fresh 60-day overlap, but stock indices create only
about one valid 8H candle per trading day. A one-year archive is therefore too
shallow for the first-wave RSI 369-SMA module.

Environment:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
    SIGNAL_8H_BACKFILL_RANGE=730d
    SIGNAL_8H_ARCHIVE_RETENTION_DAYS=730
    SIGNAL_8H_BACKFILL_SYMBOLS=JPN225,US30,WHEAT  (optional)
    SIGNAL_8H_MIN_8H_CANDLES=370
"""

import os
import sys
from datetime import datetime

import pandas as pd
from supabase import create_client

sys.path.insert(0, os.path.dirname(__file__))

from signal8h.catalog import (  # noqa: E402
    SYNTHETIC_PAIRS,
    YAHOO_TICKERS,
    get_all_signal_symbols,
    get_all_yahoo_tickers,
)
from signal8h.ohlc import (  # noqa: E402
    ARCHIVE_RETENTION_DAYS,
    SOURCE_STALE_AFTER_HOURS,
    archive_to_supabase,
    cleanup_old_archive,
    download_1h_data,
    load_from_archive,
    resolve_symbol_1h,
    synthesize_8h_candles,
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
BACKFILL_RANGE = os.environ.get("SIGNAL_8H_BACKFILL_RANGE", f"{ARCHIVE_RETENTION_DAYS}d")
MIN_8H_CANDLES = int(os.environ.get("SIGNAL_8H_MIN_8H_CANDLES", "370"))


def parse_requested_symbols():
    """Return the provider symbols that should be audited after this run."""
    all_symbols = get_all_signal_symbols()
    raw = os.environ.get("SIGNAL_8H_BACKFILL_SYMBOLS", "").strip()
    if not raw:
        return all_symbols

    requested = [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]
    unknown = [symbol for symbol in requested if symbol not in all_symbols]
    if unknown:
        print(f"ERROR: Unknown SIGNAL_8H_BACKFILL_SYMBOLS: {', '.join(unknown)}")
        raise SystemExit(1)

    return requested


def tickers_for_symbols(symbols):
    """Translate provider symbols into the Yahoo tickers they need."""
    if set(symbols) == set(get_all_signal_symbols()):
        return get_all_yahoo_tickers()

    tickers = set()
    for symbol in symbols:
        direct_ticker = YAHOO_TICKERS.get(symbol)
        if direct_ticker:
            tickers.add(direct_ticker)
            continue

        synthetic = SYNTHETIC_PAIRS.get(symbol)
        if synthetic:
            num_ticker, den_ticker, _ = synthetic
            tickers.add(num_ticker)
            tickers.add(den_ticker)

    return sorted(tickers)


def timestamp_label(index_value):
    if index_value is None:
        return None
    return pd.Timestamp(index_value).strftime("%Y-%m-%d %H:%M:%SZ")


def audit_symbol_depth(symbols, ticker_data, fresh_ticker_data):
    """
    Verify business depth after the archive write.

    Row counts alone are misleading: FX pairs trade nearly 24h, while indices
    have short exchange sessions. The reliable check is the final synthesized
    8H candle count for each provider symbol.
    """
    report = []
    shallow = []
    missing = []

    for symbol in symbols:
        df_1h, metadata, source_error = resolve_symbol_1h(
            symbol,
            ticker_data,
            fresh_ticker_data,
            expected_close=None,
            stale_after_hours=SOURCE_STALE_AFTER_HOURS,
        )

        if source_error or df_1h.empty:
            item = {
                "symbol": symbol,
                "status": "missing",
                "error": source_error or "no_1h_data",
                "source": metadata,
            }
            report.append(item)
            missing.append(item)
            continue

        df_8h = synthesize_8h_candles(df_1h)
        item = {
            "symbol": symbol,
            "status": "ok" if len(df_8h) >= MIN_8H_CANDLES else "shallow",
            "candles_8h": len(df_8h),
            "rows_1h": len(df_1h),
            "first_1h": timestamp_label(df_1h.index[0]) if not df_1h.empty else None,
            "latest_1h": timestamp_label(df_1h.index[-1]) if not df_1h.empty else None,
            "source": metadata,
        }
        report.append(item)
        if item["status"] == "shallow":
            shallow.append(item)

    return report, missing, shallow


def print_depth_report(report):
    print("\nSymbol depth audit:")
    for item in report:
        if item["status"] == "missing":
            print(f"  - {item['symbol']}: missing ({item['error']})")
            continue

        marker = "OK" if item["status"] == "ok" else "SHALLOW"
        print(
            f"  - {item['symbol']}: {marker}, "
            f"8H={item['candles_8h']}, 1H={item['rows_1h']}, "
            f"{item['first_1h']} -> {item['latest_1h']}"
        )


def main():
    print("=" * 72)
    print("FXview — 1H OHLC Archive Backfill")
    print(f"Run Time: {datetime.utcnow().isoformat()}Z")
    print(f"Yahoo range: {BACKFILL_RANGE}")
    print(f"Archive retention: {ARCHIVE_RETENTION_DAYS} days")
    print(f"Minimum 8H depth: {MIN_8H_CANDLES} candles")
    print("=" * 72)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY")
        raise SystemExit(1)

    symbols = parse_requested_symbols()
    tickers = tickers_for_symbols(symbols)
    print(f"\nBackfilling {len(tickers)} Yahoo tickers for {len(symbols)} provider symbols.")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    fresh_data = download_1h_data(tickers, range_period=BACKFILL_RANGE)
    if not fresh_data:
        print("ERROR: Yahoo returned no 1H data; archive was not changed.")
        raise SystemExit(1)

    print("\nWriting archive rows to Supabase...")
    archived_rows = archive_to_supabase(fresh_data, sb)
    print(f"  -> Upserted {archived_rows} rows")

    print("\nCleaning archive to the same retention window used by the daily engine...")
    deleted_rows = cleanup_old_archive(sb, retention_days=ARCHIVE_RETENTION_DAYS)
    print(f"  -> Deleted {deleted_rows} rows outside the retained window")

    print("\nReloading retained archive for verification...")
    archive_data = load_from_archive(tickers, sb, retention_days=ARCHIVE_RETENTION_DAYS)
    # Audit the same data shape the daily engine will consume after cleanup:
    # retained archive depth plus symbol-level source freshness metadata.
    report, missing, shallow = audit_symbol_depth(symbols, archive_data, fresh_data)
    print_depth_report(report)

    if missing or shallow:
        print("\nBackfill finished with unresolved depth gaps.")
        if missing:
            print(f"  Missing symbols: {', '.join(item['symbol'] for item in missing)}")
        if shallow:
            print(f"  Shallow symbols: {', '.join(item['symbol'] for item in shallow)}")
        raise SystemExit(1)

    print("\nBackfill complete. All audited symbols have enough 8H depth. OK")


if __name__ == "__main__":
    main()
