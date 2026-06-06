"""Download, archive, and assemble 1H/8H OHLC data for the signal engine."""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd

from signal8h.catalog import SYNTHETIC_PAIRS, YAHOO_TICKERS

ARCHIVE_PAGE_SIZE = 1000
ARCHIVE_RETENTION_DAYS = int(os.environ.get("SIGNAL_8H_ARCHIVE_RETENTION_DAYS", "730"))
YAHOO_CHART_TIMEOUT_SECONDS = 20
YAHOO_DOWNLOAD_WORKERS = 8
YAHOO_RANGE_FALLBACKS = ["2y", "500d", "300d", "60d"]
YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_USER_AGENT = "Mozilla/5.0 (compatible; FXviewSignal8H/1.0)"
SOURCE_STALE_AFTER_HOURS = 24


def synthesize_8h_candles(df_1h):
    """Aggregate UTC-aligned 1H bars into 8H candles."""
    if df_1h is None or df_1h.empty:
        return pd.DataFrame()

    if df_1h.index.tz is not None:
        df_1h = df_1h.tz_convert('UTC')

    df_1h = df_1h.copy()
    df_1h['bucket'] = df_1h.index.floor('8h')
    ohlc = df_1h.groupby('bucket').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
    }).dropna()

    counts = df_1h.groupby('bucket').size()
    ohlc = ohlc[counts >= 4]
    ohlc.index.name = 'Date'
    return ohlc


def _build_chart_url(ticker, range_period="60d"):
    encoded_ticker = quote(ticker, safe="")
    return (
        f"{YAHOO_CHART_BASE_URL}/{encoded_ticker}"
        f"?range={quote(range_period, safe='')}&interval=1h&includePrePost=false&events=history"
    )


def _download_chart_ticker_once(ticker, range_period):
    """
    Download one ticker through Yahoo's chart API.

    yfinance 0.2.36 currently fails with JSONDecodeError on this machine even
    when the raw chart API returns valid JSON. This direct client keeps the data
    supplier small, observable, and easy to replace later.
    """
    request = Request(_build_chart_url(ticker, range_period), headers={"User-Agent": YAHOO_USER_AGENT})
    with urlopen(request, timeout=YAHOO_CHART_TIMEOUT_SECONDS) as response:
        payload = json.load(response)

    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise ValueError(chart["error"])

    result = (chart.get("result") or [None])[0]
    if not result:
        return pd.DataFrame()

    timestamps = result.get("timestamp") or []
    quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    if not timestamps or not quote_data:
        return pd.DataFrame()

    df = pd.DataFrame({
        "Open": quote_data.get("open") or [],
        "High": quote_data.get("high") or [],
        "Low": quote_data.get("low") or [],
        "Close": quote_data.get("close") or [],
    }, index=pd.to_datetime(timestamps, unit="s", utc=True))

    return df.dropna()


def _download_chart_ticker(ticker, range_period="60d"):
    """
    Download one ticker, with range fallbacks for Yahoo's uneven retention rules.

    Some exchange tickers reject `730d` 1H even though equivalent depth is
    available through `2y` or `500d`. The supplier tries the requested range
    first, then smaller/stable fallbacks so one symbol does not disappear.
    """
    ranges = [range_period]
    ranges.extend(period for period in YAHOO_RANGE_FALLBACKS if period not in ranges)

    errors = []
    for period in ranges:
        try:
            df = _download_chart_ticker_once(ticker, period)
            if not df.empty and period != range_period:
                print(f"    FALLBACK {ticker}: {range_period} -> {period}")
            return df
        except Exception as error:
            errors.append(f"{period}:{error}")

    raise ValueError("; ".join(errors))


def download_1h_data(tickers, range_period="60d"):
    """
    Download fresh 1H data.

    Each ticker is fetched independently through Yahoo's chart API so a single
    symbol cannot hide inside a giant batch failure. The bounded worker pool
    keeps the run fast without turning Yahoo into an uncontrolled fan-out.
    """
    ticker_data = {}
    failures = {}
    workers = min(YAHOO_DOWNLOAD_WORKERS, max(1, len(tickers)))

    print(f"  Downloading via Yahoo chart API ({workers} workers, range={range_period})...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download_chart_ticker, ticker, range_period): ticker
            for ticker in tickers
        }

        for future in as_completed(futures):
            ticker = futures[future]
            try:
                df = future.result()
                if df.empty:
                    failures[ticker] = "empty_chart_response"
                    continue
                ticker_data[ticker] = df
                print(f"    OK {ticker}: {len(df)} bars, latest={latest_timestamp_iso(df)}")
            except Exception as error:
                failures[ticker] = str(error)
                print(f"    WARNING {ticker}: {error}")

    print(f"  -> Yahoo chart data: {len(ticker_data)}/{len(tickers)} tickers")
    if failures:
        print(f"  -> Missing tickers: {len(failures)}")

    return ticker_data


def archive_to_supabase(ticker_data, sb):
    """Upsert downloaded 1H OHLC rows into the archive table."""
    total_rows = 0
    for ticker, df in ticker_data.items():
        if df.empty:
            continue

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

        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            try:
                sb.table('ohlc_1h_archive').upsert(chunk, on_conflict='ticker,ts').execute()
                total_rows += len(chunk)
            except Exception as error:
                print(f"    WARNING: Archive upsert failed for {ticker} (chunk {i}): {error}")

    return total_rows


def load_from_archive(tickers, sb, retention_days=ARCHIVE_RETENTION_DAYS):
    """Load retained 1H data from Supabase with pagination."""
    cutoff = (datetime.utcnow() - timedelta(days=retention_days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    archive_data = {}

    for ticker in tickers:
        try:
            all_records = []
            offset = 0

            while True:
                result = sb.table('ohlc_1h_archive') \
                    .select('ts,open,high,low,close') \
                    .eq('ticker', ticker) \
                    .gte('ts', cutoff) \
                    .order('ts') \
                    .range(offset, offset + ARCHIVE_PAGE_SIZE - 1) \
                    .execute()

                if not result.data:
                    break

                all_records.extend(result.data)
                if len(result.data) < ARCHIVE_PAGE_SIZE:
                    break

                offset += ARCHIVE_PAGE_SIZE

            if all_records:
                df = pd.DataFrame(all_records)
                df['ts'] = pd.to_datetime(df['ts'], utc=True)
                df = df.set_index('ts')
                df.columns = ['Open', 'High', 'Low', 'Close']
                archive_data[ticker] = df.astype(float)
        except Exception as error:
            print(f"    WARNING: Archive load failed for {ticker}: {error}")

    return archive_data


def cleanup_old_archive(sb, retention_days=ARCHIVE_RETENTION_DAYS):
    """Delete archive rows older than the configured retained depth."""
    cutoff = (datetime.utcnow() - timedelta(days=retention_days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        result = sb.table('ohlc_1h_archive').delete().lt('ts', cutoff).execute()
        return len(result.data) if result.data else 0
    except Exception as error:
        print(f"    WARNING: Cleanup failed: {error}")
        return 0


def merge_ticker_data(yahoo_data, archive_data):
    """Merge archive depth with fresh Yahoo overlap, letting Yahoo win."""
    merged = {}
    all_tickers = set(list(yahoo_data.keys()) + list(archive_data.keys()))

    for ticker in all_tickers:
        yahoo_df = yahoo_data.get(ticker, pd.DataFrame())
        archive_df = archive_data.get(ticker, pd.DataFrame())

        if yahoo_df.empty and archive_df.empty:
            continue
        if yahoo_df.empty:
            merged[ticker] = archive_df
            continue
        if archive_df.empty:
            merged[ticker] = yahoo_df
            continue

        combined = pd.concat([archive_df, yahoo_df])
        combined = combined[~combined.index.duplicated(keep='last')]
        merged[ticker] = combined.sort_index()

    return merged


def timestamp_to_utc_naive(value):
    """Normalize pandas/Python timestamps so source freshness comparisons agree."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert('UTC').tz_localize(None)
    return ts.to_pydatetime()


def latest_timestamp_iso(df):
    """Return the latest source timestamp as an ISO string, if available."""
    if df is None or df.empty:
        return None

    latest = timestamp_to_utc_naive(df.index[-1])
    return latest.strftime('%Y-%m-%dT%H:%M:%SZ')


def ticker_source_health(ticker, fresh_ticker_data, expected_close, stale_after_hours):
    """
    Audit this run's fresh Yahoo supply for one ticker.

    Archive rows are useful for indicator depth, but they must not hide that a
    ticker failed to renew today. This helper keeps those two responsibilities
    separate.
    """
    df = fresh_ticker_data.get(ticker, pd.DataFrame()) if fresh_ticker_data is not None else pd.DataFrame()
    metadata = {
        'ticker': ticker,
        'source_latest_at': latest_timestamp_iso(df),
    }

    if df.empty:
        return metadata, f"fresh_ticker_missing:{ticker}"

    if expected_close is not None:
        latest = timestamp_to_utc_naive(df.index[-1])
        staleness_hours = (expected_close - latest).total_seconds() / 3600
        metadata['source_staleness_hours'] = round(staleness_hours, 2)
        if staleness_hours > stale_after_hours:
            return metadata, f"source_stale:{ticker}:{staleness_hours:.1f}h"

    return metadata, None


def compute_synthetic_ohlc(num_df, den_df, operation):
    """Compute approximate synthetic OHLC from two aligned instruments."""
    idx = num_df.index.intersection(den_df.index)
    if len(idx) == 0:
        return pd.DataFrame()

    num = num_df.loc[idx]
    den = den_df.loc[idx]

    if operation == 'divide':
        s_open = num['Open'] / den['Open']
        s_close = num['Close'] / den['Close']
        combos = [
            num['High'] / den['Low'],
            num['High'] / den['High'],
            num['Low'] / den['Low'],
            num['Low'] / den['High'],
        ]
        s_high = pd.concat(combos, axis=1).max(axis=1)
        s_low = pd.concat(combos, axis=1).min(axis=1)
    else:
        s_open = num['Open'] * den['Open']
        s_close = num['Close'] * den['Close']
        combos = [
            num['High'] * den['High'],
            num['High'] * den['Low'],
            num['Low'] * den['High'],
            num['Low'] * den['Low'],
        ]
        s_high = pd.concat(combos, axis=1).max(axis=1)
        s_low = pd.concat(combos, axis=1).min(axis=1)

    return pd.DataFrame({
        'Open': s_open,
        'High': s_high,
        'Low': s_low,
        'Close': s_close,
    })


def resolve_symbol_1h(
    symbol,
    ticker_data,
    fresh_ticker_data=None,
    expected_close=None,
    stale_after_hours=SOURCE_STALE_AFTER_HOURS,
):
    """
    Return (df_1h, metadata) for a provider symbol.

    Metadata lets the engine publish explicit unavailable rows instead of
    silently leaving stale data in signal_8h.
    """
    if symbol in YAHOO_TICKERS:
        ticker = YAHOO_TICKERS[symbol]
        source_metadata, source_error = ticker_source_health(
            ticker,
            fresh_ticker_data,
            expected_close,
            stale_after_hours,
        )
        metadata = {
            'source_type': 'direct',
        }
        metadata.update(source_metadata)
        if source_error:
            metadata['source_error'] = source_error
            return pd.DataFrame(), metadata, source_error

        return ticker_data.get(ticker, pd.DataFrame()), metadata, None

    if symbol in SYNTHETIC_PAIRS:
        num_ticker, den_ticker, operation = SYNTHETIC_PAIRS[symbol]
        num_1h = ticker_data.get(num_ticker, pd.DataFrame())
        den_1h = ticker_data.get(den_ticker, pd.DataFrame())
        missing = []
        if num_1h.empty:
            missing.append(num_ticker)
        if den_1h.empty:
            missing.append(den_ticker)

        num_metadata, num_error = ticker_source_health(
            num_ticker,
            fresh_ticker_data,
            expected_close,
            stale_after_hours,
        )
        den_metadata, den_error = ticker_source_health(
            den_ticker,
            fresh_ticker_data,
            expected_close,
            stale_after_hours,
        )

        metadata = {
            'source_type': 'synthetic',
            'num_ticker': num_ticker,
            'den_ticker': den_ticker,
            'operation': operation,
            'source_latest_at': min(
                [
                    value for value in [
                        num_metadata.get('source_latest_at'),
                        den_metadata.get('source_latest_at'),
                    ] if value
                ],
                default=None,
            ),
            'components': {
                num_ticker: num_metadata,
                den_ticker: den_metadata,
            },
        }
        source_errors = [error for error in [num_error, den_error] if error]
        if missing or source_errors:
            metadata['missing_components'] = missing
            metadata['source_errors'] = source_errors
            source_error = ','.join(source_errors) if source_errors else f"missing_components:{','.join(missing)}"
            return pd.DataFrame(), metadata, source_error

        return compute_synthetic_ohlc(num_1h, den_1h, operation), metadata, None

    return pd.DataFrame(), {'source_type': 'unknown'}, 'unknown_symbol'
