"""
Signal catalog / 品种供货清单.

This is the provider contract for 8H signals. If a symbol appears here, the
engine must either publish a fresh signal or publish an explicit unavailable
status so stale Supabase rows do not masquerade as current data.
Keep this aligned with frontend/lib/signal-8h/catalog.ts.
"""

# Direct Yahoo symbols. Key = EIGHTCAP display symbol, value = Yahoo ticker.
YAHOO_TICKERS = {
    # Metals / commodities
    'XAUUSD': 'GC=F',
    'XAGUSD': 'SI=F',
    'USOUSD': 'CL=F',
    'XCUUSD': 'HG=F',
    # Stock indices
    'ASX200': '^AXJO',
    'CAN60':  '^GSPTSE',
    'CN50':   '2823.HK',
    'FRA40':  '^FCHI',
    'EUSTX50': '^STOXX50E',
    'HK50':   '^HSI',
    'GER40':  '^GDAXI',
    'JPN225': '^N225',
    'NDQ100': '^NDX',
    'NTH25':  '^AEX',
    'ITA40':  'FTSEMIB.MI',
    'SWI20':  '^SSMI',
    'SPX500': '^GSPC',
    'UK100':  '^FTSE',
    'US2000': '^RUT',
    'US30':   '^DJI',
    # AUD / NZD watchlist
    'AUDNZD': 'AUDNZD=X',
    'AUDCAD': 'AUDCAD=X',
    'AUDUSD': 'AUDUSD=X',
    'NZDCAD': 'NZDCAD=X',
    'NZDUSD': 'NZDUSD=X',
    # USD block
    'USDJPY': 'USDJPY=X',
    'USDCAD': 'USDCAD=X',
    'USDBRL': 'USDBRL=X',
    # EUR block
    'EURAUD': 'EURAUD=X',
    'EURCAD': 'EURCAD=X',
    'EURGBP': 'EURGBP=X',
    'EURNZD': 'EURNZD=X',
    'EURUSD': 'EURUSD=X',
    # GBP block
    'GBPAUD': 'GBPAUD=X',
    'GBPCAD': 'GBPCAD=X',
    'GBPNZD': 'GBPNZD=X',
    'GBPUSD': 'GBPUSD=X',
    # JPY block
    'AUDJPY': 'AUDJPY=X',
    'CADJPY': 'CADJPY=X',
    'CHFJPY': 'CHFJPY=X',
    'EURJPY': 'EURJPY=X',
    'GBPJPY': 'GBPJPY=X',
    'NZDJPY': 'NZDJPY=X',
    # CHF block. CADCHF is direct, so missing CADCHF means Yahoo/archive
    # supply failed for this exact ticker, not a synthetic-pair math issue.
    'AUDCHF': 'AUDCHF=X',
    'CADCHF': 'CADCHF=X',
    'EURCHF': 'EURCHF=X',
    'GBPCHF': 'GBPCHF=X',
    'NZDCHF': 'NZDCHF=X',
    'USDCHF': 'USDCHF=X',
}

# Synthetic symbols Yahoo does not provide directly. Values are:
# (numerator_ticker, denominator_ticker, operation).
SYNTHETIC_PAIRS = {
    'XAUAUD': ('GC=F', 'AUDUSD=X', 'divide'),
    'XAUEUR': ('GC=F', 'EURUSD=X', 'divide'),
    'XAUGBP': ('GC=F', 'GBPUSD=X', 'divide'),
    'XAUJPY': ('GC=F', 'USDJPY=X', 'multiply'),
    'XAGEUR': ('SI=F', 'EURUSD=X', 'divide'),
    'XAGJPY': ('SI=F', 'USDJPY=X', 'multiply'),
}


def get_all_yahoo_tickers():
    """Return every Yahoo ticker needed by direct and synthetic symbols."""
    tickers = set(YAHOO_TICKERS.values())
    for _, (num_ticker, den_ticker, _) in SYNTHETIC_PAIRS.items():
        tickers.add(num_ticker)
        tickers.add(den_ticker)
    return sorted(tickers)


def get_all_signal_symbols():
    """Return symbols in stable provider order."""
    return list(YAHOO_TICKERS.keys()) + list(SYNTHETIC_PAIRS.keys())
