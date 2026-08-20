"""
classifier.py — Per-expert LONG/NEUTRAL/SHORT classifier for chart patterns.

Demo: deterministic mock (no live OHLC). Real: replace classify_demo() with a
function that reads OHLC + indicators for the ticker and returns 'long' / 'flat' / 'short'.
"""

def classify_demo(ticker: str, expert: dict, consensus: int) -> str:
    """
    Demo classifier: produces a deterministic signal per (ticker, expert).
    In real mode: read OHLC + indicators + expert-specific logic, return 'long'/'flat'/'short'.

    The logic: each expert has a `bias` ('bullish' / 'neutral' / 'bearish') and `volatility`
    (how often it flips). The ticker has a `consensus` (1-10, how many experts say long).
    We hash (ticker, expert.key) to get a stable per-pair score, then modulate by bias.
    """
    import hashlib
    h = int(hashlib.md5(f"{ticker}{expert['key']}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    # base score from consensus (0..1) plus per-expert noise
    score = (consensus - 5) / 5.0  # -1 .. 1
    # bias shifts the threshold for LONG vs SHORT
    if expert['bias'] == 'bullish':
        score += 0.15
    elif expert['bias'] == 'bearish':
        score -= 0.15
    # volatility = how easily the noise pushes across thresholds
    noise = (h - 0.5) * expert['volatility'] * 1.5
    final = score + noise
    if final > 0.3: return 'long'
    if final < -0.2: return 'short'
    return 'flat'


def consensus_label(n_long: int) -> str:
    """Map X/10 to a label for the CHART CONSENSUS row."""
    if n_long >= 8: return 'STRONG_LONG'
    if n_long >= 6: return 'LONG'
    if n_long <= 2: return 'STRONG_SHORT'
    if n_long <= 4: return 'SHORT'
    return 'NEUTRAL'


def signal_to_char(sig: str) -> str:
    """Map signal to a single char for the matrix cell."""
    return {'long': '+', 'flat': '0', 'short': '−'}.get(sig, '?')
