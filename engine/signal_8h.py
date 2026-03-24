"""
鲲侯 FXview — 8H Signal Engine (signal_8h.py)
=============================================
Calculates trend-following (趋势跟随) and first-wave (第一浪) signals
on 8H timeframe for 53 EIGHTCAP instruments.

Architecture:
  1. Fetch 1H OHLC data from Yahoo Finance
  2. Synthesize 8H candles (UTC 00-08, 08-16, 16-24)
  3. Compute RSI / MACD / ADX soldiers → Commander aggregation
  4. Push static results to Supabase `signal_8h` table

Schedule: 2x/day via GitHub Actions (UTC 00:00 and 12:00)
"""

import os
import sys
import json
import traceback
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client, Client

# ==========================================
# Configuration
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

# ==========================================
# EIGHTCAP → Yahoo Finance Ticker Mapping
# ==========================================
# Key = EIGHTCAP symbol (without exchange prefix)
# Value = Yahoo ticker OR "SYNTHETIC" tag for computed pairs

# --- Direct Yahoo Tickers ---
YAHOO_TICKERS = {
    # === 黄金板块 (direct) ===
    'XAUUSD': 'GC=F',
    'XAGUSD': 'SI=F',
    'USOUSD': 'CL=F',      # WTI Crude Oil Futures
    'XCUUSD': 'HG=F',      # Copper Futures
    # === 主力期货 (Stock Indices) ===
    'ASX200': '^AXJO',
    'CAN60':  '^GSPTSE',
    'CN50':   '2823.HK',   # iShares FTSE China A50 ETF
    'FRA40':  '^FCHI',
    'EUSTX50': '^STOXX50E',
    'HK50':   '^HSI',
    'GER40':  '^GDAXI',
    'JPN225': '^N225',
    'NDQ100': '^NDX',
    'NTH25':  '^AEX',      # Netherlands 25 (NL25)
    'ITA40':  'FTSEMIB.MI',
    'SWI20':  '^SSMI',
    'SPX500': '^GSPC',
    'UK100':  '^FTSE',
    'US2000': '^RUT',
    'US30':   '^DJI',
    # === 澳纽监视板块 ===
    'AUDNZD': 'AUDNZD=X',
    'AUDCAD': 'AUDCAD=X',
    'AUDUSD': 'AUDUSD=X',
    'NZDCAD': 'NZDCAD=X',
    'NZDUSD': 'NZDUSD=X',
    # === 美元区 ===
    'USDJPY': 'USDJPY=X',
    'USDCAD': 'USDCAD=X',
    'USDBRL': 'USDBRL=X',
    # === 欧元区监视 ===
    'EURAUD': 'EURAUD=X',
    'EURCAD': 'EURCAD=X',
    'EURGBP': 'EURGBP=X',
    'EURNZD': 'EURNZD=X',
    'EURUSD': 'EURUSD=X',
    # === 英镑区监视 ===
    'GBPAUD': 'GBPAUD=X',
    'GBPCAD': 'GBPCAD=X',
    'GBPNZD': 'GBPNZD=X',
    'GBPUSD': 'GBPUSD=X',
    # === 日元监视板块 ===
    'AUDJPY': 'AUDJPY=X',
    'CADJPY': 'CADJPY=X',
    'CHFJPY': 'CHFJPY=X',
    'EURJPY': 'EURJPY=X',
    'GBPJPY': 'GBPJPY=X',
    'NZDJPY': 'NZDJPY=X',
    # === 瑞郎监视板块 ===
    'AUDCHF': 'AUDCHF=X',
    'CADCHF': 'CADCHF=X',
    'EURCHF': 'EURCHF=X',
    'GBPCHF': 'GBPCHF=X',
    'NZDCHF': 'NZDCHF=X',
    'USDCHF': 'USDCHF=X',
}

# --- Synthetic Pairs (computed from base tickers) ---
# Format: { symbol: (numerator_ticker, denominator_ticker, operation) }
# operation: 'divide' = num/den, 'multiply' = num*den
SYNTHETIC_PAIRS = {
    'XAUAUD': ('GC=F', 'AUDUSD=X', 'divide'),    # Gold/AUD = GC=F / AUDUSD
    'XAUEUR': ('GC=F', 'EURUSD=X', 'divide'),     # Gold/EUR = GC=F / EURUSD
    'XAUGBP': ('GC=F', 'GBPUSD=X', 'divide'),     # Gold/GBP = GC=F / GBPUSD
    'XAUJPY': ('GC=F', 'USDJPY=X', 'multiply'),   # Gold/JPY = GC=F × USDJPY
    'XAGEUR': ('SI=F', 'EURUSD=X', 'divide'),      # Silver/EUR = SI=F / EURUSD
    'XAGJPY': ('SI=F', 'USDJPY=X', 'multiply'),    # Silver/JPY = SI=F × USDJPY
}

# Collect all unique Yahoo tickers needed for download
def get_all_yahoo_tickers():
    """Get unique set of Yahoo tickers to download."""
    tickers = set(YAHOO_TICKERS.values())
    for _, (num_t, den_t, _) in SYNTHETIC_PAIRS.items():
        tickers.add(num_t)
        tickers.add(den_t)
    return sorted(list(tickers))

# ==========================================
# 1H → 8H Candle Synthesis
# ==========================================

def synthesize_8h_candles(df_1h):
    """
    Synthesize 8H candles from 1H OHLC data.
    
    Alignment: UTC 00-08, 08-16, 16-24
    
    Args:
        df_1h: DataFrame with DatetimeIndex (UTC) and columns: Open, High, Low, Close, Volume
    
    Returns:
        DataFrame with 8H OHLC candles
    """
    if df_1h is None or df_1h.empty:
        return pd.DataFrame()
    
    # Ensure UTC timezone
    if df_1h.index.tz is not None:
        df_1h = df_1h.tz_convert('UTC')
    
    # Assign 8H bucket: floor to nearest 8-hour boundary
    df_1h = df_1h.copy()
    df_1h['bucket'] = df_1h.index.floor('8h')
    
    # Aggregate OHLC
    ohlc = df_1h.groupby('bucket').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
    }).dropna()
    
    # Only keep complete 8H candles (need at least 6 of 8 hours to be meaningful)
    counts = df_1h.groupby('bucket').size()
    ohlc = ohlc[counts >= 4]  # relaxed: weekends/holidays may have gaps
    
    ohlc.index.name = 'Date'
    return ohlc


def get_1h_ohlc(ticker, raw_data):
    """
    Extract 1H OHLC for a single ticker from the batch download.
    
    Args:
        ticker: Yahoo ticker string
        raw_data: Multi-level DataFrame from yf.download()
    
    Returns:
        DataFrame with Open, High, Low, Close columns
    """
    try:
        if isinstance(raw_data.columns, pd.MultiIndex):
            df = pd.DataFrame({
                'Open': raw_data['Open'][ticker],
                'High': raw_data['High'][ticker],
                'Low': raw_data['Low'][ticker],
                'Close': raw_data['Close'][ticker],
            })
        else:
            df = raw_data[['Open', 'High', 'Low', 'Close']].copy()
        return df.dropna()
    except (KeyError, TypeError):
        return pd.DataFrame()


def compute_synthetic_ohlc(num_df, den_df, operation):
    """
    Compute synthetic OHLC from two instruments.
    
    For divide: OHLC = num / den
    For multiply: OHLC = num * den
    
    Note: High/Low of synthetic pair is approximated since true tick-level
    data isn't available. We use the max/min of all four combinations.
    """
    # Align on common index
    idx = num_df.index.intersection(den_df.index)
    if len(idx) == 0:
        return pd.DataFrame()
    
    num = num_df.loc[idx]
    den = den_df.loc[idx]
    
    if operation == 'divide':
        # Synthetic Open/Close
        s_open = num['Open'] / den['Open']
        s_close = num['Close'] / den['Close']
        # Approximate High/Low: max/min of OHLC combinations
        combos = [
            num['High'] / den['Low'],   # max numerator / min denominator
            num['High'] / den['High'],
            num['Low'] / den['Low'],
            num['Low'] / den['High'],   # min numerator / max denominator
        ]
        s_high = pd.concat(combos, axis=1).max(axis=1)
        s_low = pd.concat(combos, axis=1).min(axis=1)
    else:  # multiply
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
    
    # 1. Determine all tickers needed
    all_tickers = get_all_yahoo_tickers()
    print(f"\nStep 1: Downloading 1H data for {len(all_tickers)} Yahoo tickers...")
    
    # 2. Download 1H data (max 730 days for 1h interval on Yahoo)
    # yfinance 1h: max period is "730d", but for stability use 90d
    raw_data = yf.download(
        all_tickers,
        period="60d",
        interval="1h",
        progress=False,
        group_by='ticker' if len(all_tickers) > 1 else None,
    )
    
    if raw_data.empty:
        print("ERROR: No data returned from Yahoo Finance!")
        return
    
    print(f"  → Downloaded {len(raw_data)} rows")
    
    # 3. Process each symbol
    results = {}
    success_count = 0
    skip_count = 0
    error_count = 0
    
    all_symbols = list(YAHOO_TICKERS.keys()) + list(SYNTHETIC_PAIRS.keys())
    print(f"\nStep 2: Processing {len(all_symbols)} symbols on 8H timeframe...")
    
    for symbol in all_symbols:
        try:
            # Get 1H OHLC
            if symbol in YAHOO_TICKERS:
                ticker = YAHOO_TICKERS[symbol]
                df_1h = get_1h_ohlc(ticker, raw_data)
            else:
                # Synthetic pair
                num_ticker, den_ticker, operation = SYNTHETIC_PAIRS[symbol]
                num_1h = get_1h_ohlc(num_ticker, raw_data)
                den_1h = get_1h_ohlc(den_ticker, raw_data)
                
                if num_1h.empty or den_1h.empty:
                    print(f"  ⚠️  {symbol}: Missing component data for synthetic pair")
                    skip_count += 1
                    continue
                
                df_1h = compute_synthetic_ohlc(num_1h, den_1h, operation)
            
            if df_1h.empty:
                print(f"  ⚠️  {symbol}: No 1H data available")
                skip_count += 1
                continue
            
            # Synthesize 8H candles
            df_8h = synthesize_8h_candles(df_1h)
            
            if len(df_8h) < 50:
                print(f"  ⚠️  {symbol}: Not enough 8H candles ({len(df_8h)} < 50)")
                skip_count += 1
                continue
            
            s_close = df_8h['Close']
            s_high = df_8h['High']
            s_low = df_8h['Low']
            
            # Trend Following
            rsi_l, rsi_s = calc_rsi_votes(s_close, 3)
            macd_l, macd_s = calc_macd_signal(s_close)
            adx_l, adx_s = calc_adx_signal(s_high, s_low, s_close, 14)
            
            trend_status = calc_trend_aggregation(rsi_l, rsi_s, macd_l, macd_s, adx_l, adx_s)
            
            # First Wave
            fw_status = calc_fw_aggregation(s_close, s_high, s_low)
            
            payload = {
                "symbol": symbol,
                "trend": status_to_label(trend_status),
                "first_wave": status_to_label(fw_status),
                "trend_status": trend_status,
                "fw_status": fw_status,
                "candles_count": len(df_8h),
                "last_update": datetime.utcnow().isoformat() + "Z",
            }
            
            results[symbol] = payload
            success_count += 1
            print(f"  ✅ {symbol}: 趋势={payload['trend']}, 一浪={payload['first_wave']} ({len(df_8h)} candles)")
            
        except Exception as e:
            print(f"  ❌ {symbol}: Error - {e}")
            traceback.print_exc()
            error_count += 1
    
    # 4. Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {success_count} success, {skip_count} skipped, {error_count} errors")
    print(f"{'=' * 60}")
    
    # 5. Push to Supabase
    if SUPABASE_URL and SUPABASE_KEY:
        print("\nStep 3: Pushing results to Supabase...")
        try:
            sb = create_client(SUPABASE_URL, SUPABASE_KEY)
            
            for sym, data in results.items():
                def clean_nan(obj):
                    if isinstance(obj, (float, np.floating)):
                        if np.isnan(obj) or np.isinf(obj):
                            return 0.0
                        return float(obj)
                    if isinstance(obj, (int, np.integer)):
                        return int(obj)
                    if isinstance(obj, dict):
                        return {k: clean_nan(v) for k, v in obj.items()}
                    if isinstance(obj, list):
                        return [clean_nan(i) for i in obj]
                    if isinstance(obj, bool):
                        return obj
                    return obj
                
                clean_data = clean_nan(data)
                sb.table('signal_8h').upsert({
                    'symbol': sym,
                    'data': clean_data,
                    'updated_at': datetime.utcnow().isoformat() + "Z"
                }).execute()
            
            print(f"  → Pushed {len(results)} records to Supabase")
            print("Done. ✅")
        except Exception as e:
            print(f"  ❌ Supabase push failed: {e}")
            traceback.print_exc()
    else:
        print("\nNo Supabase credentials found. Dumping JSON to stdout:")
        print(json.dumps(results, default=str, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
