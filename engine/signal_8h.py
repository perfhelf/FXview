"""
鲲侯 FXview — 8H Signal Engine (signal_8h.py)
=============================================

核心功能 / Core Purpose:
    为 FXview 供货清单中的交易品种计算 8H 级别的趋势和一浪信号。
    Computes trend-following and first-wave signals on the 8H timeframe
    for the FXview provider manifest.

信号输出 / Signal Output:
    每个品种输出 2 个信号，各有 3 种状态：
    Each instrument outputs 2 signals, each with 3 possible states:

    ┌──────────────┬───────────────────────────────────────────┐
    │ trend        │ 趋势跟随方向: "多" (long) / "空" (short) / "等待" (wait)   │
    │ first_wave   │ 第一浪方向:   "多" (long) / "空" (short) / "等待" (wait)   │
    └──────────────┴───────────────────────────────────────────┘

算法来源 / Algorithm Origin:
    移植自 godview.py 的 "鲲侯 S+" 趋势跟随体系 (单 8H 周期版)。
    趋势跟随: RSI 三兵 + MACD 三兵 + ADX 三兵 → 指挥官聚合
    第一浪:   RSI 369-SMA + MACD 斜率 + ADX 位置矩阵 → 指挥官聚合
    Ported from godview.py "Kun Hou S+" trend-following system (single 8H TF).
    Trend: RSI 3-soldier + MACD 3-soldier + ADX 3-soldier → Commander aggregation
    First Wave: RSI 369-SMA + MACD slope + ADX position matrix → Commander

数据流 / Data Pipeline (6 Steps):
    ┌────────────────────────────────────────────────────────────────────────┐
    │ Step 1: Yahoo Finance 下载最新 60 天 1H 数据 (batch + individual fallback)│
    │ Step 2: 增量归档到 Supabase ohlc_1h_archive 表 (1年保留, >1年自动清理)   │
    │ Step 3: 从归档表加载完整 1 年 1H 历史 (分页读取, 突破60天限制)            │
    │ Step 4: 归档数据 + Yahoo 数据合并 → 合成 8H K线 → 计算信号               │
    │ Step 5: 信号结果推送到 Supabase signal_8h 表 (静态 API)                  │
    │ Step 6: 清理超过 1 年的归档数据                                          │
    └────────────────────────────────────────────────────────────────────────┘

运行方式 / Execution:
    正式轮询必须由 cron-job.org 或独立 worker 唤醒 HTTP/worker 入口；
    GitHub Actions 只保留 emergency workflow_dispatch，不再承担定时写库。
    Scheduled runs keep a freshness gate so old bars cannot be republished as
    fresh data. Manual emergency runs bypass only the market-wide gate; each
    symbol still publishes explicit source status.

消费者 / Consumers:
    - Next.js API Route: GET /api/signal-8h → 前端 / Swift 客户端读取
    - AlertDashboard-Swift 客户端 (Phase 2)

Supabase 表结构 / Tables:
    signal_8h:        symbol(PK), data(JSONB), updated_at
    ohlc_1h_archive:  ticker+ts(composite PK), open, high, low, close
"""

import os
import json
import traceback
import pandas as pd
import numpy as np
from datetime import datetime
from supabase import create_client

from signal8h.catalog import get_all_signal_symbols, get_all_yahoo_tickers
from signal8h.ohlc import (
    SOURCE_STALE_AFTER_HOURS,
    archive_to_supabase,
    cleanup_old_archive,
    download_1h_data,
    load_from_archive,
    merge_ticker_data,
    resolve_symbol_1h,
    synthesize_8h_candles,
)
from signal8h.sink import make_unavailable_payload, push_signal_results, utc_now_iso
from signal8h.time_gate import check_data_freshness, get_expected_8h_close

# ==========================================
# Configuration
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
SIGNAL_8H_SOURCE_STALE_AFTER_HOURS = int(
    os.environ.get("SIGNAL_8H_SOURCE_STALE_AFTER_HOURS", str(SOURCE_STALE_AFTER_HOURS))
)

# ==========================================
# Technical Indicator Functions
# (Reused from godview.py with 8H adaptation)
# ==========================================

def calc_ema(series, length):
    """Exponential Moving Average."""
    return series.ewm(span=length, adjust=False).mean()

def calc_rsi(series, length=14):
    """RSI using Wilder's smoothing (matching PineScript)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_macd(series, fast=12, slow=26, signal=9):
    """MACD: returns (macd_line, signal_line, histogram)."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ==========================================
# Trend Following (趋势跟随) — 8H Single-TF
# ==========================================

def calc_rsi_votes(series, n_votes=3):
    """
    RSI Soldier Module — slope voting across 6 SMA periods.
    Matches godview.py `calc_rsi_votes` logic.
    """
    rsi = calc_rsi(series, length=14)
    if rsi is None or len(rsi) == 0:
        return False, False
    
    mas = [16, 25, 37, 157, 248, 369]
    up_count = 0
    down_count = 0
    
    for length in mas:
        if len(rsi) < length + 2:
            continue
        ma = rsi.rolling(window=length).mean()
        slope = ma.diff()
        if len(slope) > 0:
            val = slope.iloc[-1]
            if pd.isna(val):
                continue
            if val >= 0: up_count += 1
            if val <= 0: down_count += 1
    
    long_sig = False
    short_sig = False
    
    if n_votes <= 3:
        if up_count >= n_votes and down_count >= n_votes:
            long_sig, short_sig = True, True
        elif up_count >= n_votes:
            long_sig = True
        elif down_count >= n_votes:
            short_sig = True
    else:
        if up_count >= n_votes:
            long_sig = True
        elif down_count >= n_votes:
            short_sig = True
    
    return long_sig, short_sig


def calc_macd_signal(series):
    """
    MACD Soldier Module — 0-axis judgment.
    Matches godview.py `calc_macd_signal` logic.
    """
    macd_line, signal_line, _ = calc_macd(series, fast=12, slow=26, signal=9)
    if macd_line is None or len(macd_line) == 0:
        return False, False
    
    m_val = macd_line.iloc[-1]
    s_val = signal_line.iloc[-1]
    
    if pd.isna(m_val) or pd.isna(s_val):
        return True, True
    
    if m_val == 0 or s_val == 0:
        return True, True
    
    if m_val > 0 and s_val > 0:
        return True, False
    elif m_val < 0 and s_val < 0:
        return False, True
    else:
        return True, True


def calc_adx_signal(high, low, close, length=14):
    """
    ADX Soldier Module — DI+/DI- army voting.
    Matches godview.py `calc_adx_signal` logic.
    """
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(window=length).mean()
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    plus_dm_s = pd.Series(plus_dm, index=high.index)
    minus_dm_s = pd.Series(minus_dm, index=high.index)
    
    plus_di = (plus_dm_s.rolling(window=length).mean() / atr) * 100
    minus_di = (minus_dm_s.rolling(window=length).mean() / atr) * 100
    
    plus_di = plus_di.fillna(0)
    minus_di = minus_di.fillna(0)
    
    lengths = [16, 25, 37]
    
    if len(plus_di) < 38:
        return False, False
    
    p_mas = [plus_di.rolling(window=l).mean().iloc[-1] for l in lengths]
    m_mas = [minus_di.rolling(window=l).mean().iloc[-1] for l in lengths]
    
    if any(np.isnan(p_mas)) or any(np.isnan(m_mas)):
        return False, False
    
    p1_wins = sum([p_mas[0] > m for m in m_mas])
    p2_wins = sum([p_mas[1] > m for m in m_mas])
    p3_wins = sum([p_mas[2] > m for m in m_mas])
    
    total_long_votes = (1 if p1_wins >= 2 else 0) + (1 if p2_wins >= 2 else 0) + (1 if p3_wins >= 2 else 0)
    
    m1_wins = sum([m_mas[0] > p for p in p_mas])
    m2_wins = sum([m_mas[1] > p for p in p_mas])
    m3_wins = sum([m_mas[2] > p for p in p_mas])
    
    total_short_votes = (1 if m1_wins >= 2 else 0) + (1 if m2_wins >= 2 else 0) + (1 if m3_wins >= 2 else 0)
    
    long_sig = total_long_votes >= 2
    short_sig = total_short_votes >= 2
    
    if long_sig and not short_sig: return True, False
    if short_sig and not long_sig: return False, True
    return True, True


def calc_trend_aggregation(rsi_l, rsi_s, macd_l, macd_s, adx_l, adx_s):
    """
    趋势跟随 Commander Aggregation — single timeframe version.
    Matches godview.py trend aggregation logic (without weekly cross-check).
    
    Returns: status integer (1=多, -1=空, 2=双向, 0=等待)
    """
    # For single-TF: treat each indicator as its own "general"
    rsi_gen_long = rsi_l and not rsi_s
    rsi_gen_short = rsi_s and not rsi_l
    rsi_gen_wait = not rsi_l and not rsi_s
    rsi_gen_both = not rsi_gen_long and not rsi_gen_short and not rsi_gen_wait
    
    macd_gen_long = macd_l and not macd_s
    macd_gen_short = macd_s and not macd_l
    macd_gen_both = not macd_gen_long and not macd_gen_short
    
    adx_gen_long = adx_l and not adx_s
    adx_gen_short = adx_s and not adx_l
    adx_gen_both = not adx_gen_long and not adx_gen_short
    
    trend_long = False
    trend_short = False
    
    if not rsi_gen_wait:
        long_votes = (1 if rsi_gen_long else 0) + (1 if macd_gen_long else 0) + (1 if adx_gen_long else 0)
        short_votes = (1 if rsi_gen_short else 0) + (1 if macd_gen_short else 0) + (1 if adx_gen_short else 0)
        both_votes = (1 if rsi_gen_both else 0) + (1 if macd_gen_both else 0) + (1 if adx_gen_both else 0)
        
        if long_votes > 0 and short_votes > 0:
            pass  # conflict → wait
        else:
            if long_votes == 3 or (long_votes == 2 and both_votes == 1) or (long_votes == 1 and both_votes == 2) or both_votes == 3:
                trend_long = True
            if short_votes == 3 or (short_votes == 2 and both_votes == 1) or (short_votes == 1 and both_votes == 2):
                trend_short = True
    
    if trend_long and trend_short: return 2
    if trend_long: return 1
    if trend_short: return -1
    return 0


# ==========================================
# First Wave (第一浪) — 8H Single-TF
# ==========================================

def calc_fw_rsi(series):
    """
    First Wave RSI — slope voting (6 SMA periods, threshold >= 2).
    Matches godview.py `calc_rsi_fw_day` logic.
    """
    rsi = calc_rsi(series, length=14)
    if rsi is None or len(rsi) < 370:
        return False, False
    
    mas = [16, 25, 37, 157, 248, 369]
    up_count = 0
    down_count = 0
    
    for length in mas:
        ma = rsi.rolling(window=length).mean()
        slope = ma.diff()
        if len(slope) > 0:
            val = slope.iloc[-1]
            if pd.isna(val): continue
            if val >= 0: up_count += 1
            if val <= 0: down_count += 1
    
    return up_count >= 2, down_count >= 2


def calc_fw_macd(series):
    """
    First Wave MACD — DIF/DEA slope counting.
    Matches godview.py `calc_macd_fw` logic.
    Returns: (dif, dea, up_count, down_count)
    """
    macd_line, signal_line, histogram = calc_macd(series, fast=12, slow=26, signal=9)
    if macd_line is None or len(macd_line) < 38:
        return 0, 0, 0, 0
    
    dif = macd_line.iloc[-1]
    dea = signal_line.iloc[-1]
    
    if pd.isna(dif) or pd.isna(dea):
        return 0, 0, 0, 0
    
    up_count = 0
    down_count = 0
    
    # DIF slope
    dif_slope = macd_line.diff().iloc[-1]
    if not pd.isna(dif_slope):
        if dif_slope > 0: up_count += 1
        elif dif_slope < 0: down_count += 1
    
    # DEA slope
    dea_slope = signal_line.diff().iloc[-1]
    if not pd.isna(dea_slope):
        if dea_slope > 0: up_count += 1
        elif dea_slope < 0: down_count += 1
    
    # Histogram SMA slopes
    for length in [16, 25, 37]:
        ma = histogram.rolling(window=length).mean()
        slope = ma.diff().iloc[-1]
        if not pd.isna(slope):
            if slope > 0: up_count += 1
            elif slope < 0: down_count += 1
    
    return dif, dea, up_count, down_count


def calc_fw_adx(high, low, close, length=14):
    """
    First Wave ADX — position/slope matrix.
    Matches godview.py `calc_adx_fw` logic.
    Returns 8 values for position/slope analysis.
    """
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(window=length).mean()
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    plus_dm_s = pd.Series(plus_dm, index=high.index)
    minus_dm_s = pd.Series(minus_dm, index=high.index)
    
    plus_di = (plus_dm_s.rolling(window=length).mean() / atr) * 100
    minus_di = (minus_dm_s.rolling(window=length).mean() / atr) * 100
    
    plus_di = plus_di.fillna(0)
    minus_di = minus_di.fillna(0)
    
    if len(plus_di) < 38:
        return 0, 0, 0, 0, 0, 0, 0, 0
    
    p_mas = [plus_di.rolling(window=l).mean() for l in [16, 25, 37]]
    m_mas = [minus_di.rolling(window=l).mean() for l in [16, 25, 37]]
    
    p_ma_vals = [ma.iloc[-1] for ma in p_mas]
    m_ma_vals = [ma.iloc[-1] for ma in m_mas]
    
    if any(pd.isna(p_ma_vals)) or any(pd.isna(m_ma_vals)):
        return 0, 0, 0, 0, 0, 0, 0, 0
    
    # Slope counts
    p_up_count = 0
    p_down_count = 0
    m_up_count = 0
    m_down_count = 0
    
    for ma in p_mas:
        slope = ma.diff().iloc[-1]
        if not pd.isna(slope):
            if slope >= 0: p_up_count += 1
            if slope <= 0: p_down_count += 1
    
    for ma in m_mas:
        slope = ma.diff().iloc[-1]
        if not pd.isna(slope):
            if slope >= 0: m_up_count += 1
            if slope <= 0: m_down_count += 1
    
    # Position counts
    p_below_count = sum(1 for p in p_ma_vals for m in m_ma_vals if p < m)
    p_above_count = sum(1 for p in p_ma_vals for m in m_ma_vals if p > m)
    m_below_count = sum(1 for m in m_ma_vals for p in p_ma_vals if m < p)
    m_above_count = sum(1 for m in m_ma_vals for p in p_ma_vals if m > p)
    
    return p_up_count, p_down_count, m_up_count, m_down_count, p_below_count, p_above_count, m_below_count, m_above_count


def calc_fw_aggregation(close, high, low):
    """
    First Wave Commander — single-TF aggregation.
    Simplified from godview.py dual-TF (day + week) to single-TF.
    
    Returns: status integer (1=多, -1=空, 2=双向, 0=等待)
    """
    # RSI
    rsi_l, rsi_s = calc_fw_rsi(close)
    
    # MACD
    dif, dea, up_count, down_count = calc_fw_macd(close)
    both_below = dif < 0 and dea < 0
    both_above = dif > 0 and dea > 0
    cross_zero = (dif > 0 and dea < 0) or (dif < 0 and dea > 0) or dif == 0 or dea == 0
    
    macd_l, macd_s, macd_w = False, False, False
    if both_below and up_count >= 3:
        macd_l = True
    elif both_above and down_count >= 3:
        macd_s = True
    elif cross_zero and up_count >= 3:
        macd_l = True
    elif cross_zero and down_count >= 3:
        macd_s = True
    elif both_above and up_count >= 3:
        macd_w = True
    elif both_below and down_count >= 3:
        macd_w = True
    
    # ADX
    p_up, p_down, m_up, m_down, p_b, p_a, m_b, m_a = calc_fw_adx(high, low, close, 14)
    adx_l, adx_s, adx_b, adx_w = False, False, False, False
    
    if p_up >= 1 and p_b >= 6:
        adx_l = True
    elif m_up >= 1 and m_b >= 6:
        adx_s = True
    elif p_up >= 1 and m_up >= 2:
        adx_b = True
    elif p_down >= 1 and m_down >= 2:
        adx_b = True
    elif p_up == 3 and p_a >= 6:
        if p_down >= 1:
            adx_s = True
        else:
            adx_w = True
    elif m_up == 3 and m_a >= 6:
        if m_down >= 1:
            adx_l = True
        else:
            adx_w = True
    
    # Commander
    # Any wait → overall wait
    if macd_w or adx_w:
        return 0
    
    fw_l = rsi_l and macd_l and (adx_l or adx_b)
    fw_s = rsi_s and macd_s and (adx_s or adx_b)
    
    if fw_l and fw_s: return 2
    if fw_l: return 1
    if fw_s: return -1
    return 0


# ==========================================
# Status → Chinese Label
# ==========================================

def status_to_label(status):
    """Convert numeric status to Chinese trend label."""
    if status == 1: return "多"
    if status == -1: return "空"
    if status == 2: return "多/空"
    return "等待"


# ==========================================
# Main Execution
# ==========================================

def main():
    print("=" * 60)
    print("鲲侯 FXview — 8H Signal Engine")
    print(f"Run Time: {datetime.utcnow().isoformat()}Z")
    print("=" * 60)
    
    # Check if manual trigger (bypass freshness gate)
    is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    
    # Show expected 8H window
    expected_close, bucket_start = get_expected_8h_close()
    print(f"\n8H Window: {bucket_start.strftime('%Y-%m-%d %H:%M')} → {expected_close.strftime('%Y-%m-%d %H:%M')} UTC")
    if is_manual:
        print("  → Manual trigger: freshness gate BYPASSED")
    
    # Initialize Supabase client
    sb = None
    if SUPABASE_URL and SUPABASE_KEY:
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Determine all tickers needed
    all_tickers = get_all_yahoo_tickers()
    print(f"\nStep 1: Downloading 1H data from Yahoo Finance ({len(all_tickers)} tickers)...")
    
    # 2. Download fresh 1H data from Yahoo (60-day window)
    yahoo_data = download_1h_data(all_tickers)
    
    if not yahoo_data:
        print("WARNING: No fresh data returned from Yahoo Finance.")
        print("  → The engine will publish explicit unavailable rows instead of leaving stale signals untouched.")
        outage_results = {}
        all_symbols = get_all_signal_symbols()
        for symbol in all_symbols:
            _, source_metadata, source_error = resolve_symbol_1h(
                symbol,
                {},
                yahoo_data,
                expected_close,
                SIGNAL_8H_SOURCE_STALE_AFTER_HOURS,
            )
            outage_results[symbol] = make_unavailable_payload(
                symbol,
                "unavailable",
                source_error or "source_outage",
                source_metadata,
            )

        if sb:
            print(f"  → Publishing {len(outage_results)} explicit outage rows to Supabase.")
            pushed = push_signal_results(sb, outage_results)
            print(f"  → Pushed {pushed} outage records to Supabase")
            print("\nDone. ✅")
        else:
            print(json.dumps(outage_results, default=str, indent=2, ensure_ascii=False))
        return
    else:
        print(f"  → Yahoo data: {len(yahoo_data)} tickers")
    
    # 3. Freshness Gate — "Get then Push"
    if not is_manual:
        print(f"\nFreshness Gate: checking if 8H candle has renewed...")
        is_fresh = check_data_freshness(yahoo_data, expected_close)
        if not is_fresh:
            print("  ⏸  Data NOT yet renewed for this 8H window. Skipping push.")
            print("  → This is normal on weekends/holidays. Will retry next cron.")
            return
        print("  ✅ Data is FRESH — proceeding to archive, compute & push.")
    
    # 4. Archive — upsert Yahoo data to Supabase for accumulation
    if sb:
        print(f"\nStep 2: Archiving 1H data to Supabase (incremental upsert)...")
        archived_rows = archive_to_supabase(yahoo_data, sb)
        print(f"  → Archived {archived_rows} rows")
    
    # 5. Load full archive (up to 1 year of accumulated data)
    archive_data = {}
    if sb:
        print(f"\nStep 3: Loading 1H archive from Supabase (up to 1 year)...")
        archive_data = load_from_archive(all_tickers, sb)
        print(f"  → Archive data: {len(archive_data)} tickers")
        if archive_data:
            sample_ticker = next(iter(archive_data))
            sample_len = len(archive_data[sample_ticker])
            print(f"  → Sample depth [{sample_ticker}]: {sample_len} bars")
    
    # 6. Merge: archive (deep) + Yahoo (fresh) → full dataset
    if archive_data:
        ticker_data = merge_ticker_data(yahoo_data, archive_data)
        print(f"  → Merged: {len(ticker_data)} tickers (archive + Yahoo)")
    else:
        ticker_data = yahoo_data
        print(f"  → Using Yahoo data only: {len(ticker_data)} tickers")
    
    # 7. Process each symbol
    results = {}
    success_count = 0
    unavailable_count = 0
    error_count = 0
    
    all_symbols = get_all_signal_symbols()
    print(f"\nStep 4: Processing {len(all_symbols)} symbols on 8H timeframe...")
    
    for symbol in all_symbols:
        try:
            # The resolver is the symbol-level warehouse clerk. It tells us
            # exactly which ticker or synthetic component failed, so one bad
            # instrument cannot disappear inside a giant loop.
            df_1h, source_metadata, source_error = resolve_symbol_1h(
                symbol,
                ticker_data,
                yahoo_data,
                expected_close,
                SIGNAL_8H_SOURCE_STALE_AFTER_HOURS,
            )
            
            if source_error or df_1h.empty:
                payload = make_unavailable_payload(
                    symbol,
                    "unavailable",
                    source_error or "no_1h_data",
                    source_metadata,
                )
                results[symbol] = payload
                unavailable_count += 1
                print(f"  ⚠️  {symbol}: Source unavailable ({payload['data_error']})")
                continue
            
            # Synthesize 8H candles
            df_8h = synthesize_8h_candles(df_1h)
            
            if len(df_8h) < 50:
                payload = make_unavailable_payload(
                    symbol,
                    "unavailable",
                    f"not_enough_8h_candles:{len(df_8h)}",
                    source_metadata,
                    candles_count=len(df_8h),
                )
                results[symbol] = payload
                unavailable_count += 1
                print(f"  ⚠️  {symbol}: Not enough 8H candles ({len(df_8h)} < 50)")
                continue
            
            s_close = df_8h['Close']
            s_high = df_8h['High']
            s_low = df_8h['Low']
            
            # ── 趋势跟随 Trend Following ──
            # 三兵投票体系: RSI 三兵 + MACD 三兵 + ADX 三兵
            # 最终由 Commander (指挥官) 聚合:
            #   1 (多/Long) = 三路全部看多
            #  -1 (空/Short) = 三路全部看空
            #   0 (等待/Wait) = 信号不一致, 观望
            rsi_l, rsi_s = calc_rsi_votes(s_close, 3)
            macd_l, macd_s = calc_macd_signal(s_close)
            adx_l, adx_s = calc_adx_signal(s_high, s_low, s_close, 14)
            
            trend_status = calc_trend_aggregation(rsi_l, rsi_s, macd_l, macd_s, adx_l, adx_s)
            
            # ── 第一浪 First Wave ──
            # 捕捉趋势反转的初始信号 (比趋势跟随更灵敏)
            # RSI 369-SMA 需要 ≥383 根 8H K线 才能正常计算
            # 同样由 Commander 聚合: 1=多, -1=空, 0=等待
            fw_status = calc_fw_aggregation(s_close, s_high, s_low)
            
            # ── 构建信号 Payload ──
            # 核心字段: trend + first_wave (各只有 "多"/"空"/"等待" 三种状态)
            # 辅助字段: trend_status, fw_status (数值版), candles_count, last_update
            payload = {
                "symbol": symbol,
                "trend": status_to_label(trend_status),         # "多" / "空" / "等待"
                "first_wave": status_to_label(fw_status),       # "多" / "空" / "等待"
                "trend_status": trend_status,                   # 1 / -1 / 0 (数值版)
                "fw_status": fw_status,                         # 1 / -1 / 0 (数值版)
                "candles_count": len(df_8h),                    # 8H K线数量 (数据深度)
                "last_update": utc_now_iso(),
                "data_status": "ok",
                **source_metadata,
            }
            
            results[symbol] = payload
            success_count += 1
            print(f"  ✅ {symbol}: 趋势={payload['trend']}, 一浪={payload['first_wave']} ({len(df_8h)} candles)")
            
        except Exception as e:
            print(f"  ❌ {symbol}: Error - {e}")
            traceback.print_exc()
            results[symbol] = make_unavailable_payload(
                symbol,
                "unavailable",
                f"engine_error:{e}",
            )
            error_count += 1
    
    # 8. Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {success_count} success, {unavailable_count} unavailable, {error_count} errors")
    print(f"{'=' * 60}")
    
    # 9. Push signals to Supabase
    if sb:
        print("\nStep 5: Pushing signal results to Supabase...")
        try:
            pushed = push_signal_results(sb, results)
            print(f"  → Pushed {pushed} records to Supabase")
        except Exception as e:
            print(f"  ❌ Supabase push failed: {e}")
            traceback.print_exc()
        
        # 10. Cleanup — delete archive data older than 1 year
        print("\nStep 6: Cleaning up old archive data (>1 year)...")
        deleted = cleanup_old_archive(sb)
        print(f"  → Deleted {deleted} old rows")
        
        print("\nDone. ✅")
    else:
        print("\nNo Supabase credentials found. Dumping JSON to stdout:")
        print(json.dumps(results, default=str, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
