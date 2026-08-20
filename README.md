# Stocks Chart Agent — Engine

Self-contained engine for the **Stocks Chart Agent**, which owns `/charts.html` on sedattrade.com.

The Chart Agent runs 10 chartist sub-experts in parallel and aggregates their LONG/NEUTRAL/SHORT verdicts per ticker.

## What it does

1. **For each of 10 chart experts**, score every ticker (LONG / NEUTRAL / SHORT)
   - Bulkowski (breakout patterns), Wyckoff (phases), Magee (200 SMA), Nison (candlesticks),
     Elliott (wave theory), O'Neil (CANSLIM/RS), Brandt (price structure),
     Brooks (trend channel), Raschke (ADX momentum), Schabacker (volume/OBV)
2. **Aggregate per (ticker, expert)** → matrix
3. **Aggregate per expert** → classifier breakdown (count of long / neut / short)
4. **Aggregate per ticker** → CHART CONSENSUS (X/10 where X = count of LONG)
5. **Write `/assets/chart_live.json`** for `/charts.html` to render

## Run

```bash
# Default (20 tickers from sources.py)
python3 main.py

# Custom tickers
python3 main.py --tickers=AAPL,MSFT,NVDA,TSLA,GOOGL

# Custom output paths
python3 main.py /path/to/chart_live.json /path/to/chart-agent-pack.json
```

Output:
- `/workspace/cf-deploy/assets/chart_live.json` — page data (~7-10KB)
- `/workspace/cf-deploy/assets/chart-agent-pack.json` — portable knowledge pack (~30-40KB, with all source code embedded)

## Architecture

```
main.py             → orchestrator: pull → classify → aggregate → write JSON
sources.py          → 10 expert registry + 20 tickers + consensus + verdicts
classifier.py       → per-expert LONG/NEUTRAL/SHORT classifier (demo + LLM stub)
build_pack.py       → builds the portable {agent}-pack.json
README.md           → this file
```

## Output JSON shape

```json
{
  "version": "v5.4.0-chartshub-owner-20260820",
  "tickers": ["AAPL", "NVDA", ...20],
  "experts": ["Bulkowski", "Wyckoff", ...10],
  "matrix": {
    "STOCK_VERDICT": {"AAPL": {"grade": "B", "label": "BUY"}, ...},
    "CHART_CONSENSUS": {"AAPL": {"count": 7, "label": "LONG"}, ...},
    "per_expert": {"Bulkowski": {"AAPL": "long", ...}, ...}
  },
  "classifier": {"Bulkowski": {"bull": 11, "neut": 6, "bear": 3}, ...},
  "last_run": {"started_at": "ISO", "finished_at": "ISO", "duration_s": 0.03, "tickers_scored": 20, "experts_run": 10, "build": "v5.4.0-...", "mode": "demo"},
  "pipeline_steps": {"step1_chart_agent": "ISO", "step2_verdict_agent": "synthesised by Stock Verdict Agent", "step3_siteowner": "ISO", "step4_user": "on refresh"}
}
```

## Upgrade to real mode

Currently `classify_demo()` uses a deterministic hash to mock expert votes.

To go real:
1. **Get OHLC data** — pull daily candles for each ticker (yfinance, Polygon, etc.)
2. **Compute per-expert indicators** — e.g. 200 SMA for Magee, OBV for Schabacker, ADX for Raschke
3. **Replace `classify_demo()`** with a real function:
   ```python
   def classify_real(ticker, expert, consensus):
       df = fetch_ohlc(ticker, days=200)
       if expert['key'] == 'magee':
           return 'long' if df['close'].iloc[-1] > df['close'].rolling(200).mean().iloc[-1] else 'short'
       if expert['key'] == 'schabacker':
           obv_slope = compute_obv_slope(df)
           return 'long' if obv_slope > 0 else 'short'
       # ... 8 more experts
   ```
4. **Run**: `python3 main.py` — output JSON has the same shape, page renders unchanged

## Backup

Pushed to `github.com/sedatoezdemir1979-dev/chart-engine` on every commit.

The full page data also lives in `cf-deploy/assets/chart_live.<HASH>.json` (offsite GH: `sedatoezdemir1979-dev/sedattrade-site`).

## Pipeline role

```
Stocks Chart Agent  →  /assets/chart_live.json  →  /charts.html
       ↓
  Stock Verdict Agent  (parent — synthesises final letter grade)
       ↓
  /verdict.html  (and /news.html gets the chart weight in the consensus)
```
