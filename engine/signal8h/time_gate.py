"""8H freshness gate for scheduled provider runs."""

from datetime import datetime, timedelta


def get_expected_8h_close():
    """
    Determine the most recent UTC 8H candle close.

    Scheduled jobs run after 00:00 / 08:00 / 16:00 UTC closes. The gate keeps
    the provider from pushing old bars just because the cron fired.
    """
    now = datetime.utcnow()
    hour = now.hour

    if hour < 8:
        close_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        bucket_start = close_time - timedelta(hours=8)
    elif hour < 16:
        close_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        bucket_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
        bucket_start = now.replace(hour=8, minute=0, second=0, microsecond=0)

    return close_time, bucket_start


def check_data_freshness(ticker_data, expected_close):
    """
    Verify at least one reliable reference ticker has renewed.

    This gate checks the market-wide data feed. Per-symbol health is handled
    later by publishing unavailable rows for any individual missing ticker.
    """
    reference_tickers = ['EURUSD=X', 'GBPUSD=X', 'GC=F']

    for ref_ticker in reference_tickers:
        if ref_ticker not in ticker_data:
            continue

        df = ticker_data[ref_ticker]
        if df.empty:
            continue

        latest_ts = df.index[-1]
        if hasattr(latest_ts, 'tz') and latest_ts.tz is not None:
            latest_ts = latest_ts.tz_convert('UTC').tz_localize(None)

        staleness = expected_close - latest_ts
        hours_stale = staleness.total_seconds() / 3600

        print(f"  -> Freshness check [{ref_ticker}]: latest={latest_ts}, expected_close={expected_close}, staleness={hours_stale:.1f}h")
        if hours_stale <= 4:
            return True

    return False
