import os
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from supabase import create_client, Client
import json
from datetime import datetime, timedelta

# ==========================================
# Configuration
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

SYMBOLS_MAP = {
    'AUD': 'AUDUSD=X',
    'EUR': 'EURUSD=X',
    'GBP': 'GBPUSD=X',
    'NZD': 'NZDUSD=X',
    'CAD': 'USDCAD=X',
    'CHF': 'USDCHF=X',
    'JPY': 'USDJPY=X',
    'MXN': 'USDMXN=X',
    'SGD': 'USDSGD=X',
    'SEK': 'USDSEK=X',
    'NOK': 'USDNOK=X',
    'USD': 'DX-Y.NYB' 
}

# ==========================================
# Logic: Synthetic Index Calculation
# ==========================================
def calc_synthetic_indices(data):
    # Extract Series (Close)
    # yfinance returns MultiIndex (Price, Ticker) or just (Price) if 1 ticker.
    # We assume 'Close' column.
    
    # Helper to get close price series safely
    def get_c(ticker):
        if isinstance(data.columns, pd.MultiIndex):
            return data['Close'][ticker]
        else:
            return data['Close']

    aud = get_c(SYMBOLS_MAP['AUD'])
    eur = get_c(SYMBOLS_MAP['EUR'])
    gbp = get_c(SYMBOLS_MAP['GBP'])
    nzd = get_c(SYMBOLS_MAP['NZD'])
    cad = get_c(SYMBOLS_MAP['CAD'])
    chf = get_c(SYMBOLS_MAP['CHF'])
    jpy = get_c(SYMBOLS_MAP['JPY'])
    mxn = get_c(SYMBOLS_MAP['MXN'])
    sgd = get_c(SYMBOLS_MAP['SGD'])
    sek = get_c(SYMBOLS_MAP['SEK'])
    nok = get_c(SYMBOLS_MAP['NOK'])
    usd = get_c(SYMBOLS_MAP['USD'])

    indices = {}

    # 1. AUD
    indices['AUD'] = aud/0.66047 + (cad*aud)/0.90476 + (aud/eur)/0.61763 + (aud/gbp)/0.53138 + (aud*jpy)/94.23133
    
    # 2. CAD
    indices['CAD'] = (1/cad)/0.72965 + (1/(cad*aud))/1.1055 + (1/(eur*cad))/0.68211 + (1/(gbp*cad))/0.58657 + (jpy/cad)/104.165

    # 3. CHF
    indices['CHF'] = (1/chf)/1.12406 + (cad/chf)/1.54202 + (1/(eur*chf))/1.05058 + (1/(chf*gbp))/0.90315 + (jpy/chf)/160.83167

    # 4. JPY
    indices['JPY'] = (1/jpy)/0.00703 + (1/(jpy*aud))/0.01063 + (cad/jpy)/0.00963 + (1/(jpy*gbp))/0.00566 + (1/(jpy*eur))/0.00656

    # 5. EUR
    indices['EUR'] = eur/1.06973 + (eur/aud)/1.62021 + (eur*cad)/1.46625 + (eur/gbp)/0.85959 + (eur*jpy)/152.95167

    # 6. GBP
    indices['GBP'] = gbp/1.24401 + (gbp/aud)/1.88737 + (gbp*cad)/1.70749 + (gbp/eur)/1.16423 + (gbp*jpy)/178.228

    # 7. USD (DXY directly)
    indices['USD'] = usd

    # 8. NZD
    indices['NZD'] = nzd/0.60851 + (cad*nzd)/0.83363 + (nzd/eur)/0.56898 + (nzd/gbp)/0.48991 + (jpy*nzd)/86.76033

    # 9. SGD
    indices['SGD'] = (1/sgd)/0.74527 + (cad/sgd)/1.02258 + (1/(eur*sgd))/0.69684 + (1/(sgd*gbp))/0.59898 + (jpy/sgd)/106.60933

    # 10. MXN
    indices['MXN'] = (1/mxn)/0.05273 + (cad/mxn)/0.07218 + (1/(eur*mxn))/0.0492 + (1/(mxn*gbp))/0.04234 + (jpy/mxn)/7.52667

    # 11. SEK
    indices['SEK'] = (1/sek)/0.09512 + (cad/sek)/0.13038 + (1/(eur*sek))/0.08885 + (1/(sek*gbp))/0.07644 + (jpy/sek)/13.58497

    # 12. NOK
    indices['NOK'] = (1/nok)/0.09603 + (cad/nok)/0.13154 + (1/(eur*nok))/0.08968 + (1/(nok*gbp))/0.07723 + (jpy/nok)/13.68007

    return pd.DataFrame(indices)

# ==========================================
# Logic: Indicators & V24D
# ==========================================

def calc_sma_slope_v2(series, length):
    """
    Calculates SMA-smoothed slope (Kunhou Pivot V23 logic).
    single_bar_slope = (src - src[1]) / src[1] * 100
    avg_slope = sma(single_bar_slope, length)
    """
    # Daily return percentage
    pct_change = series.pct_change() * 100
    # SMA of that return
    return pct_change.rolling(window=length).mean()

def calc_rsi_votes(series, n_votes):
    rsi = ta.rsi(series, length=14)
    if rsi is None: return 0
    
    mas = [16, 25, 37, 157, 248, 369]
    up_count = 0
    down_count = 0
    
    for length in mas:
        ma = rsi.rolling(window=length).mean()
        slope = ma.diff()
        # Use last value
        if len(slope) > 0:
            val = slope.iloc[-1]
            if pd.isna(val): continue
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
        # Simplified logic for high vote counts from pine
        if up_count >= n_votes: long_sig = True
        elif down_count >= n_votes: short_sig = True
        
    return long_sig, short_sig

def calc_macd_signal(series):
    # MACD 12, 26, 9
    macd = ta.macd(series, fast=12, slow=26, signal=9)
    # Columns: MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
    if macd is None or len(macd) == 0: return False, False
    
    curr = macd.iloc[-1]
    m_val = curr['MACD_12_26_9']
    s_val = curr['MACDs_12_26_9']
    
    long_sig, short_sig = False, False
    
    if m_val == 0 or s_val == 0:
        long_sig, short_sig = True, True
    else:
        if m_val > 0 and s_val > 0: long_sig = True
        elif m_val < 0 and s_val < 0: short_sig = True
        else:
             long_sig, short_sig = True, True
             
    return long_sig, short_sig

def calc_adx_signal(high, low, close, length=14):
    # Custom ADX logic from Pine
    # TR calculation
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(window=length).mean() # SMA logic from Pine
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    # Convert to Series for rolling
    plus_dm_s = pd.Series(plus_dm, index=high.index)
    minus_dm_s = pd.Series(minus_dm, index=high.index)
    
    plus_di = (plus_dm_s.rolling(window=length).mean() / atr) * 100
    minus_di = (minus_dm_s.rolling(window=length).mean() / atr) * 100
    
    # Fill nan
    plus_di = plus_di.fillna(0)
    minus_di = minus_di.fillna(0)
    
    # SMAs of DI
    lengths = [16, 25, 37]
    
    p_wins = 0
    m_wins = 0
    
    # We only need the last values for signal
    if len(plus_di) < 38: return False, False
    
    # Voting logic is complex intersection of MA crosses
    # For simplification in Python, we implement the strict logic:
    # "p1_wins" etc.
    
    # Calculate all MAs first
    p_mas = [plus_di.rolling(window=l).mean().iloc[-1] for l in lengths]
    m_mas = [minus_di.rolling(window=l).mean().iloc[-1] for l in lengths]
    
    # Check if any is nan
    if any(np.isnan(p_mas)) or any(np.isnan(m_mas)): return False, False
    
    total_long_votes = 0
    total_short_votes = 0
    
    # p1_wins
    p_ma1 = p_mas[0]; m_ma1 = m_mas[0]
    p_ma2 = p_mas[1]; m_ma2 = m_mas[1]
    p_ma3 = p_mas[2]; m_ma3 = m_mas[2]
    
    # Vote Logic from Pine
    # p1_wins = (p_ma1 > m_ma1) + (p_ma1 > m_ma2) + (p_ma1 > m_ma3)
    p1_wins = sum([p_ma1 > m for m in m_mas])
    p2_wins = sum([p_ma2 > m for m in m_mas])
    p3_wins = sum([p_ma3 > m for m in m_mas])
    
    if p1_wins >= 2: total_long_votes += 1
    if p2_wins >= 2: total_long_votes += 1
    if p3_wins >= 2: total_long_votes += 1
    
    m1_wins = sum([m_ma1 > p for p in p_mas])
    m2_wins = sum([m_ma2 > p for p in p_mas])
    m3_wins = sum([m_ma3 > p for p in p_mas])
    
    if m1_wins >= 2: total_short_votes += 1
    if m2_wins >= 2: total_short_votes += 1
    if m3_wins >= 2: total_short_votes += 1
    
    long_sig = total_long_votes >= 2
    short_sig = total_short_votes >= 2
    
    if long_sig and not short_sig: return True, False
    if short_sig and not long_sig: return False, True
    return True, True

# ==========================================
# Main Execution
# ==========================================
def main():
    print("Fetching data from Yahoo Finance...")
    tickers = list(SYMBOLS_MAP.values())
    raw_data = yf.download(tickers, period="2y", interval="1d", progress=False)
    
    # Handle data structure
    # If standard, raw_data['Close'] has columns
    if 'Close' not in raw_data:
        print("Error: No Close data found.")
        return

    # Calculate Synthetic Indices
    print("Calculating synthetic indices...")
    df_syn = calc_synthetic_indices(raw_data)
    
    # Needs High/Low/Close for ADX. 
    # Synthetic indices only have calculated 'Close'.
    # Approximation: use Close for H/L/C or just skip ADX?
    # GodView logic uses H/L/C for ADX.
    # We calculated synthetic 'Close'.
    # To strictly follow GodView, we should also calculate Synthetic High and Low.
    # But checking Pine Script: `f_v24_proxy_runner` uses `request.security(tkr, 'D', [close, high, low])`.
    # `tkr` is the formula.
    # A formula like `AUDUSD/0.66` applied to High/Low is tricky because High_syn != High_raw / const.
    # However, since we defined the formula on 'Close' value, usually for synthetic indices we assume Close=High=Low for simplicity, 
    # OR we apply the formula to High and Low separately. 
    # Given the complexity, we will apply the same formula to High and Low columns of the raw pairs to get Synthetic High/Low.
    
    def get_col(col_name, ticker):
        if isinstance(raw_data.columns, pd.MultiIndex):
            return raw_data[col_name][ticker]
        else:
            return raw_data[col_name]

    # Re-implement synthetic calc helper for generic series
    def apply_formula(series_getter):
        aud = series_getter(SYMBOLS_MAP['AUD'])
        eur = series_getter(SYMBOLS_MAP['EUR'])
        gbp = series_getter(SYMBOLS_MAP['GBP'])
        nzd = series_getter(SYMBOLS_MAP['NZD'])
        cad = series_getter(SYMBOLS_MAP['CAD'])
        chf = series_getter(SYMBOLS_MAP['CHF'])
        jpy = series_getter(SYMBOLS_MAP['JPY'])
        mxn = series_getter(SYMBOLS_MAP['MXN'])
        sgd = series_getter(SYMBOLS_MAP['SGD'])
        sek = series_getter(SYMBOLS_MAP['SEK'])
        nok = series_getter(SYMBOLS_MAP['NOK'])
        usd = series_getter(SYMBOLS_MAP['USD'])
        
        res = {}
        res['AUD'] = aud/0.66047 + (cad*aud)/0.90476 + (aud/eur)/0.61763 + (aud/gbp)/0.53138 + (aud*jpy)/94.23133
        res['CAD'] = (1/cad)/0.72965 + (1/(cad*aud))/1.1055 + (1/(eur*cad))/0.68211 + (1/(gbp*cad))/0.58657 + (jpy/cad)/104.165
        res['CHF'] = (1/chf)/1.12406 + (cad/chf)/1.54202 + (1/(eur*chf))/1.05058 + (1/(chf*gbp))/0.90315 + (jpy/chf)/160.83167
        res['JPY'] = (1/jpy)/0.00703 + (1/(jpy*aud))/0.01063 + (cad/jpy)/0.00963 + (1/(jpy*gbp))/0.00566 + (1/(jpy*eur))/0.00656
        res['EUR'] = eur/1.06973 + (eur/aud)/1.62021 + (eur*cad)/1.46625 + (eur/gbp)/0.85959 + (eur*jpy)/152.95167
        res['GBP'] = gbp/1.24401 + (gbp/aud)/1.88737 + (gbp*cad)/1.70749 + (gbp/eur)/1.16423 + (gbp*jpy)/178.228
        res['USD'] = usd
        res['NZD'] = nzd/0.60851 + (cad*nzd)/0.83363 + (nzd/eur)/0.56898 + (nzd/gbp)/0.48991 + (jpy*nzd)/86.76033
        res['SGD'] = (1/sgd)/0.74527 + (cad/sgd)/1.02258 + (1/(eur*sgd))/0.69684 + (1/(sgd*gbp))/0.59898 + (jpy/sgd)/106.60933
        res['MXN'] = (1/mxn)/0.05273 + (cad/mxn)/0.07218 + (1/(eur*mxn))/0.0492 + (1/(mxn*gbp))/0.04234 + (jpy/mxn)/7.52667
        res['SEK'] = (1/sek)/0.09512 + (cad/sek)/0.13038 + (1/(eur*sek))/0.08885 + (1/(sek*gbp))/0.07644 + (jpy/sek)/13.58497
        res['NOK'] = (1/nok)/0.09603 + (cad/nok)/0.13154 + (1/(eur*nok))/0.08968 + (1/(nok*gbp))/0.07723 + (jpy/nok)/13.68007
        return pd.DataFrame(res)

    df_high = apply_formula(lambda t: get_col('High', t))
    df_low = apply_formula(lambda t: get_col('Low', t))
    # Close is already df_syn
    
    results = {}
    
    for symbol in df_syn.columns:
        print(f"Processing {symbol}...")
        
        # 1. Daily Data
        s_close = df_syn[symbol].dropna()
        s_high = df_high[symbol].dropna()
        s_low = df_low[symbol].dropna()
        
        # Align
        idx = s_close.index.intersection(s_high.index).intersection(s_low.index)
        s_close = s_close.loc[idx]
        s_high = s_high.loc[idx]
        s_low = s_low.loc[idx]
        
        if len(s_close) < 200:
            print(f"Not enough data for {symbol}")
            continue

        # EMA Slopes (Daily)
        ema20d = calc_sma_slope_v2(ta.ema(s_close, 20), 50).iloc[-1]
        ema50d = calc_sma_slope_v2(ta.ema(s_close, 50), 50).iloc[-1]
        ema100d = calc_sma_slope_v2(ta.ema(s_close, 100), 50).iloc[-1]
        ema200d = calc_sma_slope_v2(ta.ema(s_close, 200), 50).iloc[-1]
        
        # V24D Filters (Daily)
        # RSI
        rsi_l, rsi_s = calc_rsi_votes(s_close, 3)
        # MACD
        macd_l, macd_s = calc_macd_signal(s_close)
        # ADX
        adx_l, adx_s = calc_adx_signal(s_high, s_low, s_close, 14)
        
        # 2. Weekly Data
        # Resample to Weekly
        w_close = s_close.resample('W-FRI').last()
        w_high = s_high.resample('W-FRI').max()
        w_low = s_low.resample('W-FRI').min()
        
        if len(w_close) < 50:
             # Default fallback
             ema20w = 0; ema50w = 0; ema100w = 0; ema200w = 0
             wrsi_l=False; wrsi_s=False; wmacd_l=False; wmacd_s=False; wadx_l=False; wadx_s=False
        else:
             ema20w = calc_sma_slope_v2(ta.ema(w_close, 20), 50).iloc[-1]
             ema50w = calc_sma_slope_v2(ta.ema(w_close, 50), 50).iloc[-1]
             ema100w = calc_sma_slope_v2(ta.ema(w_close, 100), 50).iloc[-1]
             ema200w = calc_sma_slope_v2(ta.ema(w_close, 200), 50).iloc[-1]
             
             wrsi_l, wrsi_s = calc_rsi_votes(w_close, 3)
             wmacd_l, wmacd_s = calc_macd_signal(w_close)
             wadx_l, wadx_s = calc_adx_signal(w_high, w_low, w_close, 14)

        # 3. Monthly Data
        m_close = s_close.resample('ME').last()
        
        if len(m_close) < 50:
             ema20m = 0; ema50m = 0; ema100m = 0; ema200m = 0
        else:
             ema20m = calc_sma_slope_v2(ta.ema(m_close, 20), 50).iloc[-1]
             ema50m = calc_sma_slope_v2(ta.ema(m_close, 50), 50).iloc[-1]
             ema100m = calc_sma_slope_v2(ta.ema(m_close, 100), 50).iloc[-1]
             ema200m = calc_sma_slope_v2(ta.ema(m_close, 200), 50).iloc[-1]

        # 4. Aggregation Logic (Trend Follow Only implemented for brevity, FW is similar)
        # Using simplified aggregation based on signals
        
        # General Status
        # RSI
        rsi_gen_long = rsi_l and wrsi_l and not rsi_s and not wrsi_s
        rsi_gen_short = rsi_s and wrsi_s and not rsi_l and not wrsi_l
        rsi_gen_wait = not rsi_l and not rsi_s and not wrsi_l and not wrsi_s
        rsi_gen_both = not rsi_gen_long and not rsi_gen_short and not rsi_gen_wait
        
        # MACD
        macd_gen_long = macd_l and wmacd_l and not macd_s and not wmacd_s
        macd_gen_short = macd_s and wmacd_s and not macd_l and not wmacd_l
        macd_gen_both = not macd_gen_long and not macd_gen_short
        
        # ADX
        adx_gen_long = adx_l and wadx_l and not adx_s and not wadx_s
        adx_gen_short = adx_s and wadx_s and not adx_l and not wadx_l
        adx_gen_both = not adx_gen_long and not adx_gen_short
        
        # Trend Status
        trend_long = False
        trend_short = False
        
        if not rsi_gen_wait:
            long_votes = (1 if rsi_gen_long else 0) + (1 if macd_gen_long else 0) + (1 if adx_gen_long else 0)
            short_votes = (1 if rsi_gen_short else 0) + (1 if macd_gen_short else 0) + (1 if adx_gen_short else 0)
            both_votes = (1 if rsi_gen_both else 0) + (1 if macd_gen_both else 0) + (1 if adx_gen_both else 0)
            
            if long_votes > 0 and short_votes > 0:
                pass 
            else:
                 if long_votes == 3 or (long_votes==2 and both_votes==1) or (long_votes==1 and both_votes==2) or both_votes==3:
                     trend_long = True
                 if short_votes == 3 or (short_votes==2 and both_votes==1) or (short_votes==1 and both_votes==2) or both_votes==3:
                     trend_short = True
        
        trend_status = 0
        if trend_long and trend_short: trend_status = 2
        elif trend_long: trend_status = 1
        elif trend_short: trend_status = -1
        
        # Payload
        payload = {
            "symbol": symbol,
            "trend_status": trend_status,
            "ema_slopes": {
                "d": [ema20d, ema50d, ema100d, ema200d],
                "w": [ema20w, ema50w, ema100w, ema200w],
                "m": [ema20m, ema50m, ema100m, ema200m]
            },
            "signals": {
                "rsi": {"d": [rsi_l, rsi_s], "w": [wrsi_l, wrsi_s]},
                "macd": {"d": [macd_l, macd_s], "w": [wmacd_l, wmacd_s]},
                "adx": {"d": [adx_l, adx_s], "w": [wadx_l, wadx_s]}
            }
        }
        
        results[symbol] = payload

    # JSON Push
    if SUPABASE_URL and SUPABASE_KEY:
        print("Pushing to Supabase...")
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        for sym, data in results.items():
            # Handle NaN for JSON compatibility
            def clean_nan(obj):
                if isinstance(obj, float):
                    if np.isnan(obj) or np.isinf(obj): return 0.0
                    return obj
                if isinstance(obj, dict):
                    return {k: clean_nan(v) for k,v in obj.items()}
                if isinstance(obj, list):
                    return [clean_nan(i) for i in obj]
                return obj

            clean_data = clean_nan(data)
            sb.table('godview_snapshot').upsert({'symbol': sym, 'data': clean_data}).execute()
        print("Done.")
    else:
        print("No Supabase Credentials found. Dumping JSON.")
        print(json.dumps(results, default=str, indent=2))

if __name__ == "__main__":
    main()
