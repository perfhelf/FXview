"""Output helpers for Supabase signal rows."""

from datetime import datetime

import numpy as np


def utc_now_iso():
    return datetime.utcnow().isoformat() + "Z"


def clean_nan(obj):
    """Convert numpy/pandas values to JSON-safe primitives before upsert."""
    if isinstance(obj, (float, np.floating)):
        if np.isnan(obj) or np.isinf(obj):
            return 0.0
        return float(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, dict):
        return {key: clean_nan(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(item) for item in obj]
    if isinstance(obj, bool):
        return obj
    return obj


def make_unavailable_payload(symbol, data_status, data_error, metadata=None, candles_count=0):
    """
    Publish an explicit no-signal row.

    This is the important anti-stale behavior: when CADCHF or any other symbol
    cannot be computed today, consumers receive a current "unavailable" marker
    instead of silently reading an old status from Supabase.
    """
    payload = {
        "symbol": symbol,
        "trend": "等待",
        "first_wave": "等待",
        "trend_status": 0,
        "fw_status": 0,
        "candles_count": candles_count,
        "last_update": utc_now_iso(),
        "data_status": data_status,
        "data_error": data_error,
    }
    if metadata:
        payload.update(metadata)
    return payload


def push_signal_results(sb, results):
    """Upsert every computed or unavailable symbol row."""
    pushed = 0
    for symbol, data in results.items():
        clean_data = clean_nan(data)
        sb.table('signal_8h').upsert({
            'symbol': symbol,
            'data': clean_data,
            'updated_at': utc_now_iso(),
        }).execute()
        pushed += 1
    return pushed
