"""
sources.py — Chart expert registry for the Stocks Chart Agent

10 chartist sub-experts, each with their own methodology, bias, and signal logic.
Real version reads OHLC + indicators per ticker; demo version uses deterministic mock.
"""

# 10 chart experts (canonical names match the charts page UI)
EXPERTS = [
    {
        "key": "bulkowski",
        "name": "Bulkowski",
        "method": "Breakout / Pattern statistics",
        "type": "breakout",
        "bias": "bullish",
        "volatility": 0.7,
        "weight": 0.10,
        "desc": "Statistical patterns (cup & handle, head & shoulders, double top/bottom). Trade breakouts, measure target by pattern height."
    },
    {
        "key": "wyckoff",
        "name": "Wyckoff",
        "method": "Accumulation / Distribution phases",
        "type": "phase",
        "bias": "neutral",
        "volatility": 0.5,
        "weight": 0.12,
        "desc": "Volume + price action reveals accumulation, markup, distribution, markdown phases. Spring / upthrust are reversal signals."
    },
    {
        "key": "magee",
        "name": "Magee",
        "method": "200-day moving average",
        "type": "trend",
        "bias": "bullish",
        "volatility": 0.3,
        "weight": 0.10,
        "desc": "Long-term trend via 200 SMA. Above = long-term bull, below = bear. Don't fight the tape."
    },
    {
        "key": "nison",
        "name": "Nison",
        "method": "Japanese candlesticks",
        "type": "candles",
        "bias": "neutral",
        "volatility": 0.6,
        "weight": 0.10,
        "desc": "Candle patterns: doji, hammer, engulfing, dark cloud cover. Reversal signals at support / resistance."
    },
    {
        "key": "elliott",
        "name": "Elliott",
        "method": "Wave theory (1-2-3-4-5 / A-B-C)",
        "type": "wave",
        "bias": "neutral",
        "volatility": 0.7,
        "weight": 0.10,
        "desc": "5-wave impulse + 3-wave corrective structure. Wave 3 is strongest, wave 5 often shows divergence."
    },
    {
        "key": "oneil",
        "name": "O'Neil",
        "method": "CANSLIM / RS rating",
        "type": "momentum",
        "bias": "bullish",
        "volatility": 0.8,
        "weight": 0.10,
        "desc": "Relative strength, 20/50 SMA stack, volume on breakouts. Buy leaders on pullback to support."
    },
    {
        "key": "brandt",
        "name": "Brandt",
        "method": "Price structure + stop zone",
        "type": "structure",
        "bias": "neutral",
        "volatility": 0.5,
        "weight": 0.10,
        "desc": "Higher highs + higher lows structure. Tight stop below structure, target 3-5R."
    },
    {
        "key": "brooks",
        "name": "Brooks",
        "method": "Price action + trend channel",
        "type": "channel",
        "bias": "neutral",
        "volatility": 0.6,
        "weight": 0.10,
        "desc": "Always In Long / Short (AIL). Every market has a trend. Bo squeeze, breakout, channel."
    },
    {
        "key": "raschke",
        "name": "Raschke",
        "method": "ADX + momentum breakouts",
        "type": "momentum",
        "bias": "bullish",
        "volatility": 0.9,
        "weight": 0.09,
        "desc": "ADX > 30 = strong trend. 3-bar high/low breakout with ADX confirmation."
    },
    {
        "key": "schabacker",
        "name": "Schabacker",
        "method": "Volume + OBV divergence",
        "type": "volume",
        "bias": "neutral",
        "volatility": 0.4,
        "weight": 0.09,
        "desc": "OBV leads price. Volume precedes price. Watch for OBV divergence at swing points."
    }
]

# 20 tickers (mirror news engine)
TICKERS = [
    'AAPL', 'NVDA', 'JPM', 'KO', 'INTC', 'IBM', 'T', 'F', 'MSFT',
    'GOOGL', 'AMZN', 'META', 'TSLA', 'BRK-B', 'WMT', 'DIS', 'XOM',
    'NFLX', 'BA', 'AMD'
]

# Per-ticker chart-friendly consensus (X/10, where X is count of bullish experts)
CONSENSUS = {
    'AAPL': 7, 'NVDA': 8, 'JPM': 5, 'KO': 6, 'INTC': 3, 'IBM': 4,
    'T': 5, 'F': 2, 'MSFT': 9, 'GOOGL': 7, 'AMZN': 6, 'META': 3,
    'TSLA': 2, 'BRK-B': 6, 'WMT': 5, 'DIS': 4, 'XOM': 5, 'NFLX': 7,
    'BA': 4, 'AMD': 6
}

# Per-ticker Stock Verdict (synthesised by Stock Verdict Agent)
VERDICTS = {
    'AAPL': ('B', 'BUY'), 'NVDA': ('B', 'BUY'), 'JPM': ('C', 'HOLD'),
    'KO': ('B', 'BUY'), 'INTC': ('D', 'SELL'), 'IBM': ('C', 'HOLD'),
    'T': ('B', 'BUY'), 'F': ('D', 'SELL'), 'MSFT': ('A', 'STRONG_BUY'),
    'GOOGL': ('B', 'BUY'), 'AMZN': ('B', 'BUY'), 'META': ('C', 'HOLD'),
    'TSLA': ('D', 'SELL'), 'BRK-B': ('A', 'STRONG_BUY'),
    'WMT': ('B', 'BUY'), 'DIS': ('C', 'HOLD'), 'XOM': ('C', 'HOLD'),
    'NFLX': ('B', 'BUY'), 'BA': ('D', 'SELL'), 'AMD': ('B', 'BUY')
}
