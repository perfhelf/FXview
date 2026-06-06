"""
Daily 8H signal supervisor / 每日供货监督员.

This script checks the finished signal_8h table. It does not calculate market
signals; it audits whether the provider actually delivered fresh rows for every
expected symbol. A failure here is actionable: run the engine, inspect the
symbol-level data_error, or fix the source mapping.
"""

import os
from datetime import datetime, timedelta, timezone

from supabase import create_client

from signal8h.catalog import get_all_signal_symbols

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
STALE_AFTER_HOURS = int(os.environ.get("SIGNAL_8H_STALE_AFTER_HOURS", "24"))


def parse_timestamp(value):
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Missing Supabase credentials for 8H supervisor.")
        raise SystemExit(1)

    expected_symbols = get_all_signal_symbols()
    expected_set = set(expected_symbols)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_AFTER_HOURS)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    result = sb.table('signal_8h').select('symbol,updated_at,data').execute()
    rows = result.data or []
    rows_by_symbol = {row.get('symbol'): row for row in rows if row.get('symbol')}

    missing = [symbol for symbol in expected_symbols if symbol not in rows_by_symbol]
    stale = []
    unavailable = []
    extras = sorted(symbol for symbol in rows_by_symbol.keys() if symbol not in expected_set)

    for symbol in expected_symbols:
        row = rows_by_symbol.get(symbol)
        if not row:
            continue

        data = row.get('data') or {}
        updated_at = parse_timestamp(row.get('updated_at') or data.get('last_update'))
        if not updated_at or updated_at < cutoff:
            stale.append({
                "symbol": symbol,
                "updated_at": row.get('updated_at'),
                "last_update": data.get('last_update'),
                "data_status": data.get('data_status'),
                "data_error": data.get('data_error'),
            })

        if data.get('data_status') not in (None, 'ok'):
            unavailable.append({
                "symbol": symbol,
                "data_status": data.get('data_status'),
                "data_error": data.get('data_error'),
                "updated_at": row.get('updated_at'),
            })

    print("8H signal supervisor")
    print(f"  expected: {len(expected_symbols)}")
    print(f"  rows: {len(rows)}")
    print(f"  stale_after_hours: {STALE_AFTER_HOURS}")
    print(f"  missing: {len(missing)}")
    print(f"  stale: {len(stale)}")
    print(f"  unavailable: {len(unavailable)}")
    print(f"  extras: {len(extras)}")

    if missing:
        print("\nMissing symbols:")
        for symbol in missing:
            print(f"  - {symbol}")

    if stale:
        print("\nStale symbols:")
        for item in stale:
            print(f"  - {item['symbol']}: updated_at={item['updated_at']} last_update={item['last_update']} status={item['data_status']} error={item['data_error']}")

    if unavailable:
        print("\nUnavailable symbols:")
        for item in unavailable:
            print(f"  - {item['symbol']}: status={item['data_status']} error={item['data_error']} updated_at={item['updated_at']}")

    if extras:
        print("\nUnexpected extra symbols:")
        for symbol in extras:
            print(f"  - {symbol}")

    if missing or stale or unavailable:
        raise SystemExit(1)

    print("\nAll expected 8H signals are fresh. ✅")


if __name__ == "__main__":
    main()
