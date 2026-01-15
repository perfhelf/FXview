import os
import yfinance as yf
import pandas as pd
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
    'CNH': 'CNY=X',
    'MYR': 'USDMYR=X',
    'XAU': 'GC=F',
    'XAG': 'SI=F',
    'XCU': 'HG=F',
    'ZAR': 'USDZAR=X',
    'KRW': 'USDKRW=X',
    'BRL': 'USDBRL=X',
    'USD': 'DX-Y.NYB',
    # Stock Indices
    'HKD': 'USDHKD=X',  # For HK50 conversion
    'CN50': '2823.HK',  # iShares FTSE China A50 ETF (XIN9.FGI has no data)
    'HK50': '^HSI',
    'SG30': '^STI',
    'ASX200': '^AXJO',
    'CA60': '^GSPTSE',
    'NL25': '^AEX',
    'FRA40': '^FCHI',
    'GER40': '^GDAXI',
    'EUSTX50': '^STOXX50E',
    'IT40': 'FTSEMIB.MI',
    'SWI20': '^SSMI',
    'UK100': '^FTSE',
    'SPX500': '^GSPC',
    'NDQ100': '^NDX',
    'US2000': '^RUT',
    'US30': '^DJI',
    'JPN225': '^N225',
}

# ==========================================
# Pure Pandas Indicator Implementations
# ==========================================

def calc_ema(series, length):
    """Calculate Exponential Moving Average using pandas."""
    return series.ewm(span=length, adjust=False).mean()

def calc_rsi(series, length=14):
    """Calculate RSI using pure pandas."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_macd(series, fast=12, slow=26, signal=9):
    """Calculate MACD using pure pandas. Returns (macd_line, signal_line, histogram)."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

# ==========================================
# Logic: Synthetic Index Calculation
# ==========================================
def calc_synthetic_indices(data):
    def get_c(ticker):
        try:
            if isinstance(data.columns, pd.MultiIndex):
                return data['Close'][ticker]
            else:
                return data['Close']
        except KeyError:
            print(f"Warning: Data for {ticker} not found. Returning NaN.")
            return pd.Series(np.nan, index=data.index)

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
    cnh = get_c(SYMBOLS_MAP['CNH'])
    myr = get_c(SYMBOLS_MAP['MYR'])
    xau = get_c(SYMBOLS_MAP['XAU'])
    xag = get_c(SYMBOLS_MAP['XAG'])
    xcu = get_c(SYMBOLS_MAP['XCU'])
    zar = get_c(SYMBOLS_MAP['ZAR'])
    krw = get_c(SYMBOLS_MAP['KRW'])
    brl = get_c(SYMBOLS_MAP['BRL'])
    usd = get_c(SYMBOLS_MAP['USD'])
    # Stock Indices
    hkd = get_c(SYMBOLS_MAP['HKD'])
    cn50_raw = get_c(SYMBOLS_MAP['CN50'])
    hk50_raw = get_c(SYMBOLS_MAP['HK50'])
    sg30_raw = get_c(SYMBOLS_MAP['SG30'])
    asx200_raw = get_c(SYMBOLS_MAP['ASX200'])
    ca60_raw = get_c(SYMBOLS_MAP['CA60'])
    nl25_raw = get_c(SYMBOLS_MAP['NL25'])
    fra40_raw = get_c(SYMBOLS_MAP['FRA40'])
    ger40_raw = get_c(SYMBOLS_MAP['GER40'])
    eustx50_raw = get_c(SYMBOLS_MAP['EUSTX50'])
    it40_raw = get_c(SYMBOLS_MAP['IT40'])
    swi20_raw = get_c(SYMBOLS_MAP['SWI20'])
    uk100_raw = get_c(SYMBOLS_MAP['UK100'])
    spx500_raw = get_c(SYMBOLS_MAP['SPX500'])
    ndq100_raw = get_c(SYMBOLS_MAP['NDQ100'])
    us2000_raw = get_c(SYMBOLS_MAP['US2000'])
    us30_raw = get_c(SYMBOLS_MAP['US30'])
    jpn225_raw = get_c(SYMBOLS_MAP['JPN225'])

    indices = {}
    # Currency Indices (existing)
    indices['AUD'] = aud/0.66047 + (cad*aud)/0.90476 + (aud/eur)/0.61763 + (aud/gbp)/0.53138 + (aud*jpy)/94.23133
    indices['CAD'] = (1/cad)/0.72965 + (1/(cad*aud))/1.1055 + (1/(eur*cad))/0.68211 + (1/(gbp*cad))/0.58657 + (jpy/cad)/104.165
    indices['CHF'] = (1/chf)/1.12406 + (cad/chf)/1.54202 + (1/(eur*chf))/1.05058 + (1/(chf*gbp))/0.90315 + (jpy/chf)/160.83167
    indices['JPY'] = (1/jpy)/0.00703 + (1/(jpy*aud))/0.01063 + (cad/jpy)/0.00963 + (1/(jpy*gbp))/0.00566 + (1/(jpy*eur))/0.00656
    indices['EUR'] = eur/1.06973 + (eur/aud)/1.62021 + (eur*cad)/1.46625 + (eur/gbp)/0.85959 + (eur*jpy)/152.95167
    indices['GBP'] = gbp/1.24401 + (gbp/aud)/1.88737 + (gbp*cad)/1.70749 + (gbp/eur)/1.16423 + (gbp*jpy)/178.228
    indices['USD'] = usd
    indices['NZD'] = nzd/0.60851 + (cad*nzd)/0.83363 + (nzd/eur)/0.56898 + (nzd/gbp)/0.48991 + (jpy*nzd)/86.76033
    indices['SGD'] = (1/sgd)/0.74527 + (cad/sgd)/1.02258 + (1/(eur*sgd))/0.69684 + (1/(sgd*gbp))/0.59898 + (jpy/sgd)/106.60933
    indices['MXN'] = (1/mxn)/0.05273 + (cad/mxn)/0.07218 + (1/(eur*mxn))/0.0492 + (1/(mxn*gbp))/0.04234 + (jpy/mxn)/7.52667
    indices['SEK'] = (1/sek)/0.09512 + (cad/sek)/0.13038 + (1/(eur*sek))/0.08885 + (1/(sek*gbp))/0.07644 + (jpy/sek)/13.58497
    indices['NOK'] = (1/nok)/0.09603 + (cad/nok)/0.13154 + (1/(eur*nok))/0.08968 + (1/(nok*gbp))/0.07723 + (jpy/nok)/13.68007
    indices['CNH'] = (1/cnh)/0.13793 + (eur/cnh)/0.14759 + (gbp/cnh)/0.17159 + (jpy/cnh)/19.72414 + (aud/cnh)/0.09103
    indices['MYR'] = (1/myr)/0.22371 + (eur/myr)/0.23937 + (gbp/myr)/0.27740 + (jpy/myr)/31.99552 + (aud/myr)/0.14765
    indices['XAU'] = xau/4629 + (xau/eur)/3973 + (xau/gbp)/3444 + (xau*jpy)/734159 + (xau/aud)/6929
    indices['XAG'] = xag/85.23 + (xag/eur)/73.16 + (xag/gbp)/63.41 + (xag*jpy)/13517 + (xag/aud)/127.59
    indices['XCU'] = xcu/6.05 + (xcu/eur)/5.19 + (xcu/gbp)/4.50 + (xcu*jpy)/959.5 + (xcu/aud)/9.06
    indices['ZAR'] = (1/zar)/0.06109 + (eur/zar)/0.07116 + (gbp/zar)/0.08210 + (jpy/zar)/9.688 + (aud/zar)/0.04080
    indices['KRW'] = (1/krw)/0.000682 + (eur/krw)/0.000794 + (gbp/krw)/0.000916 + (jpy/krw)/0.10818 + (aud/krw)/0.000455
    indices['BRL'] = (1/brl)/0.1858 + (eur/brl)/0.2165 + (gbp/brl)/0.2498 + (jpy/brl)/29.47 + (aud/brl)/0.1241
    
    # Stock Indices (new) - TAIXI multi-currency approach
    # CN50 (USD priced from Yahoo XIN9.FGI)
    indices['CN50'] = cn50_raw/13830 + (cn50_raw/eur)/14798 + (cn50_raw/gbp)/17560 + (cn50_raw*jpy)/1977690 + (cn50_raw/aud)/20954
    # HK50 (HKD priced)
    indices['HK50'] = (hk50_raw/hkd)/2594 + (hk50_raw/hkd/eur)/2776 + (hk50_raw/hkd/gbp)/3294 + (hk50_raw/hkd*jpy)/370922 + (hk50_raw/hkd/aud)/3930
    # SG30 (SGD priced)
    indices['SG30'] = (sg30_raw/sgd)/296 + (sg30_raw/sgd/eur)/317 + (sg30_raw/sgd/gbp)/376 + (sg30_raw/sgd*jpy)/42328 + (sg30_raw/sgd/aud)/448
    # ASX200 (AUD priced)
    indices['ASX200'] = (asx200_raw*aud)/5511 + (asx200_raw*aud/eur)/5897 + (asx200_raw*aud/gbp)/6999 + (asx200_raw*aud*jpy)/788073 + asx200_raw/8350
    # CA60 (CAD priced)
    indices['CA60'] = (ca60_raw/cad)/18613 + (ca60_raw/cad/eur)/19916 + (ca60_raw/cad/gbp)/23638 + (ca60_raw/cad*jpy)/2661659 + (ca60_raw/cad/aud)/28201
    # NL25 (EUR priced)
    indices['NL25'] = (nl25_raw*eur)/984 + nl25_raw/920 + (nl25_raw*eur/gbp)/1250 + (nl25_raw*eur*jpy)/140712 + (nl25_raw*eur/aud)/1491
    # FRA40 (EUR priced)
    indices['FRA40'] = (fra40_raw*eur)/8507 + fra40_raw/7950 + (fra40_raw*eur/gbp)/10804 + (fra40_raw*eur*jpy)/1216499 + (fra40_raw*eur/aud)/12889
    # GER40 (EUR priced)
    indices['GER40'] = (ger40_raw*eur)/22256 + ger40_raw/20800 + (ger40_raw*eur/gbp)/28265 + (ger40_raw*eur*jpy)/3182608 + (ger40_raw*eur/aud)/33721
    # EUSTX50 (EUR priced)
    indices['EUSTX50'] = (eustx50_raw*eur)/5511 + eustx50_raw/5150 + (eustx50_raw*eur/gbp)/6999 + (eustx50_raw*eur*jpy)/788073 + (eustx50_raw*eur/aud)/8350
    # IT40 (EUR priced)
    indices['IT40'] = (it40_raw*eur)/38520 + it40_raw/36000 + (it40_raw*eur/gbp)/48920 + (it40_raw*eur*jpy)/5508360 + (it40_raw*eur/aud)/58364
    # SWI20 (CHF priced)
    indices['SWI20'] = (swi20_raw/chf)/13483 + (swi20_raw/chf/eur)/14427 + (swi20_raw/chf/gbp)/17123 + (swi20_raw/chf*jpy)/1928049 + (swi20_raw/chf/aud)/20428
    # UK100 (GBP priced)
    indices['UK100'] = (uk100_raw*gbp)/10605 + (uk100_raw*gbp/eur)/11347 + uk100_raw/8350 + (uk100_raw*gbp*jpy)/1516515 + (uk100_raw*gbp/aud)/16068
    # SPX500 (USD priced)
    indices['SPX500'] = spx500_raw/5950 + (spx500_raw/eur)/6367 + (spx500_raw/gbp)/7557 + (spx500_raw*jpy)/850850 + (spx500_raw/aud)/9015
    # NDQ100 (USD priced)
    indices['NDQ100'] = ndq100_raw/21000 + (ndq100_raw/eur)/22470 + (ndq100_raw/gbp)/26670 + (ndq100_raw*jpy)/3003000 + (ndq100_raw/aud)/31818
    # US2000 (USD priced)
    indices['US2000'] = us2000_raw/2250 + (us2000_raw/eur)/2408 + (us2000_raw/gbp)/2858 + (us2000_raw*jpy)/321750 + (us2000_raw/aud)/3409
    # US30 (USD priced)
    indices['US30'] = us30_raw/43000 + (us30_raw/eur)/46010 + (us30_raw/gbp)/54610 + (us30_raw*jpy)/6149000 + (us30_raw/aud)/65152
    # JPN225 (JPY priced)
    indices['JPN225'] = (jpn225_raw/jpy)/269 + (jpn225_raw/jpy/eur)/288 + (jpn225_raw/jpy/gbp)/342 + jpn225_raw/38500 + (jpn225_raw/jpy/aud)/408

    return pd.DataFrame(indices)

# ==========================================
# Logic: Indicators & V24D
# ==========================================

def calc_sma_slope_v2(series, length):
    """SMA-smoothed slope (Kunhou Pivot V23 logic)."""
    pct_change = series.pct_change() * 100
    return pct_change.rolling(window=length).mean()

def calc_rsi_votes(series, n_votes):
    rsi = calc_rsi(series, length=14)
    if rsi is None or len(rsi) == 0: return False, False
    
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
        if up_count >= n_votes: long_sig = True
        elif down_count >= n_votes: short_sig = True
        
    return long_sig, short_sig

def calc_macd_signal(series):
    macd_line, signal_line, _ = calc_macd(series, fast=12, slow=26, signal=9)
    if macd_line is None or len(macd_line) == 0: return False, False
    
    m_val = macd_line.iloc[-1]
    s_val = signal_line.iloc[-1]
    
    long_sig, short_sig = False, False
    
    if pd.isna(m_val) or pd.isna(s_val):
        return True, True
    
    if m_val == 0 or s_val == 0:
        long_sig, short_sig = True, True
    else:
        if m_val > 0 and s_val > 0: long_sig = True
        elif m_val < 0 and s_val < 0: short_sig = True
        else:
             long_sig, short_sig = True, True
             
    return long_sig, short_sig

def calc_adx_signal(high, low, close, length=14):
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
    
    if len(plus_di) < 38: return False, False
    
    p_mas = [plus_di.rolling(window=l).mean().iloc[-1] for l in lengths]
    m_mas = [minus_di.rolling(window=l).mean().iloc[-1] for l in lengths]
    
    if any(np.isnan(p_mas)) or any(np.isnan(m_mas)): return False, False
    
    total_long_votes = 0
    total_short_votes = 0
    
    p_ma1 = p_mas[0]; m_ma1 = m_mas[0]
    p_ma2 = p_mas[1]; m_ma2 = m_mas[1]
    p_ma3 = p_mas[2]; m_ma3 = m_mas[2]
    
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
# Wave 1 (First Wave / 一浪) Indicator Functions
# ==========================================

def calc_rsi_fw_day(series):
    """RSI First Wave for Daily - uses 6 SMA periods, threshold >= 2."""
    rsi = calc_rsi(series, length=14)
    if rsi is None or len(rsi) < 370: return False, False
    
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

def calc_rsi_fw_week(series):
    """RSI First Wave for Weekly - uses 3 SMA periods, threshold >= 1."""
    rsi = calc_rsi(series, length=14)
    if rsi is None or len(rsi) < 38: return False, False
    
    mas = [16, 25, 37]
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
    
    return up_count >= 1, down_count >= 1

def calc_macd_fw(series):
    """MACD First Wave - returns (dif, dea, up_count, down_count)."""
    macd_line, signal_line, histogram = calc_macd(series, fast=12, slow=26, signal=9)
    if macd_line is None or len(macd_line) < 38: return 0, 0, 0, 0
    
    dif = macd_line.iloc[-1]
    dea = signal_line.iloc[-1]
    
    if pd.isna(dif) or pd.isna(dea): return 0, 0, 0, 0
    
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

def calc_adx_fw(high, low, close, length=14):
    """ADX First Wave - returns 8 values for position/slope analysis."""
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
    
    if len(plus_di) < 38: return 0, 0, 0, 0, 0, 0, 0, 0
    
    # Calculate SMAs
    p_mas = [plus_di.rolling(window=l).mean() for l in [16, 25, 37]]
    m_mas = [minus_di.rolling(window=l).mean() for l in [16, 25, 37]]
    
    p_ma_vals = [ma.iloc[-1] for ma in p_mas]
    m_ma_vals = [ma.iloc[-1] for ma in m_mas]
    
    if any(pd.isna(p_ma_vals)) or any(pd.isna(m_ma_vals)): return 0, 0, 0, 0, 0, 0, 0, 0
    
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
    
    # Position counts (how many times each p_ma is below/above each m_ma)
    p_below_count = sum(1 for p in p_ma_vals for m in m_ma_vals if p < m)
    p_above_count = sum(1 for p in p_ma_vals for m in m_ma_vals if p > m)
    m_below_count = sum(1 for m in m_ma_vals for p in p_ma_vals if m < p)
    m_above_count = sum(1 for m in m_ma_vals for p in p_ma_vals if m > p)
    
    return p_up_count, p_down_count, m_up_count, m_down_count, p_below_count, p_above_count, m_below_count, m_above_count

def calc_fw_week_signals(w_close, w_high, w_low):
    """Calculate Weekly First Wave signals."""
    # RSI Week
    rsi_l, rsi_s = calc_rsi_fw_week(w_close)
    
    # MACD Week
    dif, dea, up, down = calc_macd_fw(w_close)
    both_below = dif < 0 and dea < 0
    both_above = dif > 0 and dea > 0
    cross_zero = (dif > 0 and dea < 0) or (dif < 0 and dea > 0) or dif == 0 or dea == 0
    
    macd_l, macd_s, macd_w = False, False, False
    if both_below and up >= 3:
        macd_l = True
    elif both_above and down >= 3:
        macd_s = True
    elif cross_zero and up >= 3:
        macd_l = True
    elif cross_zero and down >= 3:
        macd_s = True
    elif both_above and up >= 3:
        macd_w = True
    elif both_below and down >= 3:
        macd_w = True
    
    # ADX Week
    p_up, p_down, m_up, m_down, p_b, p_a, m_b, m_a = calc_adx_fw(w_high, w_low, w_close, 14)
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
    
    return rsi_l, rsi_s, macd_l, macd_s, macd_w, adx_l, adx_s, adx_b, adx_w

def calc_fw_aggregation(d_close, d_high, d_low, w_rsi_l, w_rsi_s, w_macd_l, w_macd_s, w_macd_w, w_adx_l, w_adx_s, w_adx_b, w_adx_w):
    """First Wave Commander aggregation logic."""
    # 1. RSI Day
    rsi_d_l, rsi_d_s = calc_rsi_fw_day(d_close)
    rsi_w_l, rsi_w_s = w_rsi_l, w_rsi_s
    
    rsi_d_both = rsi_d_l and rsi_d_s
    rsi_w_both = rsi_w_l and rsi_w_s
    
    rsi_gen_l, rsi_gen_s, rsi_gen_wait = False, False, False
    d_only_l = rsi_d_l and not rsi_d_s
    d_only_s = rsi_d_s and not rsi_d_l
    w_only_l = rsi_w_l and not rsi_w_s
    w_only_s = rsi_w_s and not rsi_w_l
    
    if d_only_l and w_only_l: rsi_gen_l = True
    elif d_only_s and w_only_s: rsi_gen_s = True
    elif rsi_d_both and w_only_l: rsi_gen_l = True
    elif rsi_d_both and w_only_s: rsi_gen_s = True
    elif d_only_l and rsi_w_both: rsi_gen_l = True
    elif d_only_s and rsi_w_both: rsi_gen_s = True
    elif d_only_l and w_only_s: rsi_gen_wait = True
    elif d_only_s and w_only_l: rsi_gen_wait = True
    elif rsi_d_both and rsi_w_both: rsi_gen_l, rsi_gen_s = True, True
    
    # 2. MACD Day
    dif_d, dea_d, up_d, down_d = calc_macd_fw(d_close)
    macd_d_l = up_d >= 3
    macd_d_s = down_d >= 3
    macd_d_wait = not macd_d_l and not macd_d_s
    
    macd_w_l, macd_w_s, macd_w_wait = w_macd_l, w_macd_s, w_macd_w
    
    macd_gen_l, macd_gen_s, macd_gen_b, macd_gen_wait = False, False, False, False
    if macd_w_wait:
        macd_gen_wait = True
    elif macd_d_l and macd_w_l: macd_gen_l = True
    elif macd_d_s and macd_w_s: macd_gen_s = True
    elif macd_d_l and macd_w_s: macd_gen_b = True
    elif macd_d_s and macd_w_l: macd_gen_b = True
    elif macd_d_wait and macd_w_l: macd_gen_l = True
    elif macd_d_wait and macd_w_s: macd_gen_s = True
    
    # 3. ADX Day
    p_up_d, p_down_d, m_up_d, m_down_d, p_below_d, p_above_d, m_below_d, m_above_d = calc_adx_fw(d_high, d_low, d_close, 14)
    adx_d_l, adx_d_s, adx_d_b, adx_d_wait = False, False, False, False
    
    if p_up_d >= 1 and p_below_d >= 6: adx_d_l = True
    elif m_up_d >= 1 and m_below_d >= 6: adx_d_s = True
    elif p_up_d >= 1 and m_up_d >= 2: adx_d_b = True
    elif p_down_d >= 1 and m_down_d >= 2: adx_d_b = True
    elif p_up_d >= 1 and p_above_d >= 6: adx_d_wait = True
    elif m_up_d >= 2 and m_above_d >= 6: adx_d_wait = True
    
    adx_w_l, adx_w_s, adx_w_b, adx_w_wait = w_adx_l, w_adx_s, w_adx_b, w_adx_w
    
    adx_gen_l, adx_gen_s, adx_gen_b, adx_gen_wait = False, False, False, False
    if adx_d_wait or adx_w_wait: adx_gen_wait = True
    elif adx_d_l and adx_w_l: adx_gen_l = True
    elif adx_d_s and adx_w_s: adx_gen_s = True
    elif adx_d_l and adx_w_s: adx_gen_b = True
    elif adx_d_s and adx_w_l: adx_gen_b = True
    elif adx_d_b and adx_w_l: adx_gen_l = True
    elif adx_d_b and adx_w_s: adx_gen_s = True
    elif adx_d_l and adx_w_b: adx_gen_l = True
    elif adx_d_s and adx_w_b: adx_gen_s = True
    elif adx_d_b and adx_w_b: adx_gen_b = True
    
    # 4. Commander
    fw_l, fw_s = False, False
    if rsi_gen_wait or macd_gen_wait or adx_gen_wait:
        fw_l, fw_s = False, False
    else:
        # Long condition
        rsi_supp_l = rsi_gen_l or (rsi_gen_l and rsi_gen_s)
        if rsi_supp_l and macd_gen_l and (adx_gen_l or adx_gen_b):
            fw_l = True
        
        # Short condition
        rsi_supp_s = rsi_gen_s or (rsi_gen_l and rsi_gen_s)
        if rsi_supp_s and macd_gen_s and (adx_gen_s or adx_gen_b):
            fw_s = True
    
    # Return status: 1=Long, -1=Short, 2=Both, 0=Wait
    if fw_l and fw_s: return 2, [rsi_d_l, rsi_d_s], [rsi_w_l, rsi_w_s], [macd_d_l, macd_d_s], [macd_w_l, macd_w_s], [adx_d_l, adx_d_s], [adx_w_l, adx_w_s]
    if fw_l: return 1, [rsi_d_l, rsi_d_s], [rsi_w_l, rsi_w_s], [macd_d_l, macd_d_s], [macd_w_l, macd_w_s], [adx_d_l, adx_d_s], [adx_w_l, adx_w_s]
    if fw_s: return -1, [rsi_d_l, rsi_d_s], [rsi_w_l, rsi_w_s], [macd_d_l, macd_d_s], [macd_w_l, macd_w_s], [adx_d_l, adx_d_s], [adx_w_l, adx_w_s]
    return 0, [rsi_d_l, rsi_d_s], [rsi_w_l, rsi_w_s], [macd_d_l, macd_d_s], [macd_w_l, macd_w_s], [adx_d_l, adx_d_s], [adx_w_l, adx_w_s]


# ==========================================
# Main Execution
# ==========================================
def main():
    print("Fetching data from Yahoo Finance...")
    tickers = list(SYMBOLS_MAP.values())
    raw_data = yf.download(tickers, period="2y", interval="1d", progress=False)
    
    if 'Close' not in raw_data:
        print("Error: No Close data found.")
        return

    print("Calculating synthetic indices...")
    df_syn = calc_synthetic_indices(raw_data)
    
    def get_col(col_name, ticker):
        try:
            if isinstance(raw_data.columns, pd.MultiIndex):
                return raw_data[col_name][ticker]
            else:
                return raw_data[col_name]
        except KeyError:
            print(f"Warning: {col_name} Data for {ticker} not found. Returning NaN.")
            return pd.Series(np.nan, index=raw_data.index)

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
        cnh = series_getter(SYMBOLS_MAP['CNH'])
        myr = series_getter(SYMBOLS_MAP['MYR'])
        xau = series_getter(SYMBOLS_MAP['XAU'])
        xag = series_getter(SYMBOLS_MAP['XAG'])
        xcu = series_getter(SYMBOLS_MAP['XCU'])
        zar = series_getter(SYMBOLS_MAP['ZAR'])
        krw = series_getter(SYMBOLS_MAP['KRW'])
        brl = series_getter(SYMBOLS_MAP['BRL'])
        usd = series_getter(SYMBOLS_MAP['USD'])
        # Stock Indices
        hkd = series_getter(SYMBOLS_MAP['HKD'])
        cn50_raw = series_getter(SYMBOLS_MAP['CN50'])
        hk50_raw = series_getter(SYMBOLS_MAP['HK50'])
        sg30_raw = series_getter(SYMBOLS_MAP['SG30'])
        asx200_raw = series_getter(SYMBOLS_MAP['ASX200'])
        ca60_raw = series_getter(SYMBOLS_MAP['CA60'])
        nl25_raw = series_getter(SYMBOLS_MAP['NL25'])
        fra40_raw = series_getter(SYMBOLS_MAP['FRA40'])
        ger40_raw = series_getter(SYMBOLS_MAP['GER40'])
        eustx50_raw = series_getter(SYMBOLS_MAP['EUSTX50'])
        it40_raw = series_getter(SYMBOLS_MAP['IT40'])
        swi20_raw = series_getter(SYMBOLS_MAP['SWI20'])
        uk100_raw = series_getter(SYMBOLS_MAP['UK100'])
        spx500_raw = series_getter(SYMBOLS_MAP['SPX500'])
        ndq100_raw = series_getter(SYMBOLS_MAP['NDQ100'])
        us2000_raw = series_getter(SYMBOLS_MAP['US2000'])
        us30_raw = series_getter(SYMBOLS_MAP['US30'])
        jpn225_raw = series_getter(SYMBOLS_MAP['JPN225'])
        
        res = {}
        # Currency Indices
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
        res['CNH'] = (1/cnh)/0.13793 + (eur/cnh)/0.14759 + (gbp/cnh)/0.17159 + (jpy/cnh)/19.72414 + (aud/cnh)/0.09103
        res['MYR'] = (1/myr)/0.22371 + (eur/myr)/0.23937 + (gbp/myr)/0.27740 + (jpy/myr)/31.99552 + (aud/myr)/0.14765
        res['XAU'] = xau/4629 + (xau/eur)/3973 + (xau/gbp)/3444 + (xau*jpy)/734159 + (xau/aud)/6929
        res['XAG'] = xag/85.23 + (xag/eur)/73.16 + (xag/gbp)/63.41 + (xag*jpy)/13517 + (xag/aud)/127.59
        res['XCU'] = xcu/6.05 + (xcu/eur)/5.19 + (xcu/gbp)/4.50 + (xcu*jpy)/959.5 + (xcu/aud)/9.06
        res['ZAR'] = (1/zar)/0.06109 + (eur/zar)/0.07116 + (gbp/zar)/0.08210 + (jpy/zar)/9.688 + (aud/zar)/0.04080
        res['KRW'] = (1/krw)/0.000682 + (eur/krw)/0.000794 + (gbp/krw)/0.000916 + (jpy/krw)/0.10818 + (aud/krw)/0.000455
        res['BRL'] = (1/brl)/0.1858 + (eur/brl)/0.2165 + (gbp/brl)/0.2498 + (jpy/brl)/29.47 + (aud/brl)/0.1241
        # Stock Indices
        res['CN50'] = cn50_raw/13830 + (cn50_raw/eur)/14798 + (cn50_raw/gbp)/17560 + (cn50_raw*jpy)/1977690 + (cn50_raw/aud)/20954
        res['HK50'] = (hk50_raw/hkd)/2594 + (hk50_raw/hkd/eur)/2776 + (hk50_raw/hkd/gbp)/3294 + (hk50_raw/hkd*jpy)/370922 + (hk50_raw/hkd/aud)/3930
        res['SG30'] = (sg30_raw/sgd)/296 + (sg30_raw/sgd/eur)/317 + (sg30_raw/sgd/gbp)/376 + (sg30_raw/sgd*jpy)/42328 + (sg30_raw/sgd/aud)/448
        res['ASX200'] = (asx200_raw*aud)/5511 + (asx200_raw*aud/eur)/5897 + (asx200_raw*aud/gbp)/6999 + (asx200_raw*aud*jpy)/788073 + asx200_raw/8350
        res['CA60'] = (ca60_raw/cad)/18613 + (ca60_raw/cad/eur)/19916 + (ca60_raw/cad/gbp)/23638 + (ca60_raw/cad*jpy)/2661659 + (ca60_raw/cad/aud)/28201
        res['NL25'] = (nl25_raw*eur)/984 + nl25_raw/920 + (nl25_raw*eur/gbp)/1250 + (nl25_raw*eur*jpy)/140712 + (nl25_raw*eur/aud)/1491
        res['FRA40'] = (fra40_raw*eur)/8507 + fra40_raw/7950 + (fra40_raw*eur/gbp)/10804 + (fra40_raw*eur*jpy)/1216499 + (fra40_raw*eur/aud)/12889
        res['GER40'] = (ger40_raw*eur)/22256 + ger40_raw/20800 + (ger40_raw*eur/gbp)/28265 + (ger40_raw*eur*jpy)/3182608 + (ger40_raw*eur/aud)/33721
        res['EUSTX50'] = (eustx50_raw*eur)/5511 + eustx50_raw/5150 + (eustx50_raw*eur/gbp)/6999 + (eustx50_raw*eur*jpy)/788073 + (eustx50_raw*eur/aud)/8350
        res['IT40'] = (it40_raw*eur)/38520 + it40_raw/36000 + (it40_raw*eur/gbp)/48920 + (it40_raw*eur*jpy)/5508360 + (it40_raw*eur/aud)/58364
        res['SWI20'] = (swi20_raw/chf)/13483 + (swi20_raw/chf/eur)/14427 + (swi20_raw/chf/gbp)/17123 + (swi20_raw/chf*jpy)/1928049 + (swi20_raw/chf/aud)/20428
        res['UK100'] = (uk100_raw*gbp)/10605 + (uk100_raw*gbp/eur)/11347 + uk100_raw/8350 + (uk100_raw*gbp*jpy)/1516515 + (uk100_raw*gbp/aud)/16068
        res['SPX500'] = spx500_raw/5950 + (spx500_raw/eur)/6367 + (spx500_raw/gbp)/7557 + (spx500_raw*jpy)/850850 + (spx500_raw/aud)/9015
        res['NDQ100'] = ndq100_raw/21000 + (ndq100_raw/eur)/22470 + (ndq100_raw/gbp)/26670 + (ndq100_raw*jpy)/3003000 + (ndq100_raw/aud)/31818
        res['US2000'] = us2000_raw/2250 + (us2000_raw/eur)/2408 + (us2000_raw/gbp)/2858 + (us2000_raw*jpy)/321750 + (us2000_raw/aud)/3409
        res['US30'] = us30_raw/43000 + (us30_raw/eur)/46010 + (us30_raw/gbp)/54610 + (us30_raw*jpy)/6149000 + (us30_raw/aud)/65152
        res['JPN225'] = (jpn225_raw/jpy)/269 + (jpn225_raw/jpy/eur)/288 + (jpn225_raw/jpy/gbp)/342 + jpn225_raw/38500 + (jpn225_raw/jpy/aud)/408
        return pd.DataFrame(res)

    df_high = apply_formula(lambda t: get_col('High', t))
    df_low = apply_formula(lambda t: get_col('Low', t))
    
    results = {}
    
    for symbol in df_syn.columns:
        print(f"Processing {symbol}...")
        
        s_close = df_syn[symbol].dropna()
        s_high = df_high[symbol].dropna()
        s_low = df_low[symbol].dropna()
        
        idx = s_close.index.intersection(s_high.index).intersection(s_low.index)
        s_close = s_close.loc[idx]
        s_high = s_high.loc[idx]
        s_low = s_low.loc[idx]
        
        # Dynamic minimum length check
        # Commodities and Emerging currencies might have shorter history in Yahoo
        min_len = 200
        if symbol in ['XAU', 'XAG', 'XCU', 'ZAR', 'KRW', 'BRL',
                       'CN50', 'HK50', 'SG30', 'ASX200', 'CA60', 'NL25', 'FRA40', 'GER40',
                       'EUSTX50', 'IT40', 'SWI20', 'UK100', 'SPX500', 'NDQ100', 'US2000', 'US30', 'JPN225']:
            min_len = 50

        if len(s_close) < min_len:
            print(f"Not enough data for {symbol} (Has {len(s_close)}, Need {min_len})")
            continue

        # EMA Slopes (Daily) - Calculate for all three periods: short(20), mid(50), long(90)
        def calc_slopes_for_period(close_series, slope_len):
            return [
                calc_sma_slope_v2(calc_ema(close_series, 20), slope_len).iloc[-1],
                calc_sma_slope_v2(calc_ema(close_series, 50), slope_len).iloc[-1],
                calc_sma_slope_v2(calc_ema(close_series, 100), slope_len).iloc[-1],
                calc_sma_slope_v2(calc_ema(close_series, 200), slope_len).iloc[-1],
            ]
        
        # Daily slopes for each period
        ema_d_short = calc_slopes_for_period(s_close, 20)
        ema_d_mid = calc_slopes_for_period(s_close, 50)
        ema_d_long = calc_slopes_for_period(s_close, 90)
        
        # V24D Filters (Daily)
        rsi_l, rsi_s = calc_rsi_votes(s_close, 3)
        macd_l, macd_s = calc_macd_signal(s_close)
        adx_l, adx_s = calc_adx_signal(s_high, s_low, s_close, 14)
        
        # Weekly Data
        w_close = s_close.resample('W-FRI').last()
        w_high = s_high.resample('W-FRI').max()
        w_low = s_low.resample('W-FRI').min()
        
        if len(w_close) < 90:
             ema_w_short = [0, 0, 0, 0]
             ema_w_mid = [0, 0, 0, 0]
             ema_w_long = [0, 0, 0, 0]
             wrsi_l=False; wrsi_s=False; wmacd_l=False; wmacd_s=False; wadx_l=False; wadx_s=False
             # Wave 1 Weekly - defaults when insufficient data
             fw_wrsi_l=False; fw_wrsi_s=False
             fw_wmacd_l=False; fw_wmacd_s=False; fw_wmacd_w=False
             fw_wadx_l=False; fw_wadx_s=False; fw_wadx_b=False; fw_wadx_w=False
        else:
             ema_w_short = calc_slopes_for_period(w_close, 20)
             ema_w_mid = calc_slopes_for_period(w_close, 50)
             ema_w_long = calc_slopes_for_period(w_close, 90)
             
             wrsi_l, wrsi_s = calc_rsi_votes(w_close, 3)
             wmacd_l, wmacd_s = calc_macd_signal(w_close)
             wadx_l, wadx_s = calc_adx_signal(w_high, w_low, w_close, 14)
             
             # Wave 1 Weekly signals
             fw_wrsi_l, fw_wrsi_s, fw_wmacd_l, fw_wmacd_s, fw_wmacd_w, fw_wadx_l, fw_wadx_s, fw_wadx_b, fw_wadx_w = calc_fw_week_signals(w_close, w_high, w_low)

        # Monthly Data - removed from UI due to insufficient Yahoo Finance data

        # Aggregation Logic (Trend Following)
        rsi_gen_long = rsi_l and wrsi_l and not rsi_s and not wrsi_s
        rsi_gen_short = rsi_s and wrsi_s and not rsi_l and not wrsi_l
        rsi_gen_wait = not rsi_l and not rsi_s and not wrsi_l and not wrsi_s
        rsi_gen_both = not rsi_gen_long and not rsi_gen_short and not rsi_gen_wait
        
        macd_gen_long = macd_l and wmacd_l and not macd_s and not wmacd_s
        macd_gen_short = macd_s and wmacd_s and not macd_l and not wmacd_l
        macd_gen_both = not macd_gen_long and not macd_gen_short
        
        adx_gen_long = adx_l and wadx_l and not adx_s and not wadx_s
        adx_gen_short = adx_s and wadx_s and not adx_l and not wadx_l
        adx_gen_both = not adx_gen_long and not adx_gen_short
        
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
        
        # Wave 1 (First Wave) Aggregation
        fw_status, fw_rsi_d, fw_rsi_w, fw_macd_d, fw_macd_w, fw_adx_d, fw_adx_w = calc_fw_aggregation(
            s_close, s_high, s_low,
            fw_wrsi_l, fw_wrsi_s,
            fw_wmacd_l, fw_wmacd_s, fw_wmacd_w,
            fw_wadx_l, fw_wadx_s, fw_wadx_b, fw_wadx_w
        )
        
        payload = {
            "symbol": symbol,
            "last_update": datetime.utcnow().isoformat() + "Z", # Explicit UTC timestamp in payload
            "trend_status": trend_status,
            "fw_status": fw_status,
            "ema_slopes": {
                "short": {"d": ema_d_short, "w": ema_w_short},
                "mid": {"d": ema_d_mid, "w": ema_w_mid},
                "long": {"d": ema_d_long, "w": ema_w_long}
            },
            "signals": {
                "rsi": {"d": [rsi_l, rsi_s], "w": [wrsi_l, wrsi_s]},
                "macd": {"d": [macd_l, macd_s], "w": [wmacd_l, wmacd_s]},
                "adx": {"d": [adx_l, adx_s], "w": [wadx_l, wadx_s]}
            },
            "fw_signals": {
                "rsi": {"d": fw_rsi_d, "w": fw_rsi_w},
                "macd": {"d": fw_macd_d, "w": fw_macd_w},
                "adx": {"d": fw_adx_d, "w": fw_adx_w}
            }
        }
        
        results[symbol] = payload

    # JSON Push
    if SUPABASE_URL and SUPABASE_KEY:
        print("Pushing to Supabase...")
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        for sym, data in results.items():
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
            sb.table('godview_snapshot').upsert({
                'symbol': sym, 
                'data': clean_data,
                'updated_at': datetime.utcnow().isoformat() + "Z" # Explicit UTC for SQL column
            }).execute()
        print("Done.")
    else:
        print("No Supabase Credentials found. Dumping JSON.")
        print(json.dumps(results, default=str, indent=2))

if __name__ == "__main__":
    main()
