#!/usr/bin/env python3
"""
main.py — Stocks Chart Agent orchestrator

Pipeline:
  1. For each of 10 chart experts, score every ticker (LONG / NEUTRAL / SHORT)
  2. Aggregate per (ticker, expert) → matrix
  3. Aggregate per expert → classifier breakdown (count of long/neut/short)
  4. Aggregate per ticker → CHART CONSENSUS (X/10 where X = count of LONG)
  5. Write /assets/chart_live.json (for /charts.html page)

Demo mode: deterministic mock (no OHLC). Real mode: replace classify_demo() with real OHLC + expert logic.
"""

import json
import os
import sys
import time
import hashlib
import random
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources import EXPERTS, TICKERS, CONSENSUS, VERDICTS
from classifier import classify_demo, consensus_label, signal_to_char


def run_engine(tickers=None, consensus=None, verdicts=None) -> dict:
    """Run the full pipeline. Returns the JSON-ready dict."""
    if tickers is None:
        tickers = list(TICKERS)
    if consensus is None:
        consensus = dict(CONSENSUS)
    if verdicts is None:
        verdicts = dict(VERDICTS)
    # Fill defaults for tickers without CONSENSUS or VERDICTS
    for tk in tickers:
        if tk not in consensus:
            consensus[tk] = random.randint(3, 7)
        if tk not in verdicts:
            verdicts[tk] = None

    started_at = datetime.now(timezone.utc).isoformat()
    started_ts = time.time()

    per_expert_per_ticker = {}  # {expert_name: {ticker: sig}}
    per_ticker_count = {tk: {'long': 0, 'flat': 0, 'short': 0} for tk in tickers}

    for exp in EXPERTS:
        per_expert_per_ticker[exp['name']] = {}
        for tk in tickers:
            sig = classify_demo(tk, exp, consensus[tk])
            per_expert_per_ticker[exp['name']][tk] = sig
            per_ticker_count[tk][sig] += 1

    # CHART CONSENSUS per ticker (count of LONG)
    chart_consensus = {}
    for tk in tickers:
        n_long = per_ticker_count[tk]['long']
        chart_consensus[tk] = {'count': n_long, 'label': consensus_label(n_long)}

    # Classifier breakdown per expert (long / neut / short count)
    classifier = {}
    for exp in EXPERTS:
        bull = sum(1 for tk in tickers if per_expert_per_ticker[exp['name']][tk] == 'long')
        bear = sum(1 for tk in tickers if per_expert_per_ticker[exp['name']][tk] == 'short')
        neut = len(tickers) - bull - bear
        classifier[exp['name']] = {'bull': bull, 'neut': neut, 'bear': bear}

    # STOCK VERDICT (only for tickers with verdicts, '—' for the rest)
    stock_verdict = {}
    for tk in tickers:
        v = verdicts.get(tk)
        if v is not None:
            stock_verdict[tk] = {'grade': v[0], 'label': v[1]}
        else:
            stock_verdict[tk] = None

    finished_at = datetime.now(timezone.utc).isoformat()
    duration = round(time.time() - started_ts, 2)

    output = {
        'version': 'v5.4.0-chartshub-owner-20260820',
        'tickers': tickers,
        'experts': [e['name'] for e in EXPERTS],
        'matrix': {
            'STOCK_VERDICT': stock_verdict,
            'CHART_CONSENSUS': chart_consensus,
            'per_expert': per_expert_per_ticker
        },
        'classifier': classifier,
        'last_run': {
            'started_at': started_at,
            'finished_at': finished_at,
            'duration_s': duration,
            'tickers_scored': len(tickers),
            'experts_run': len(EXPERTS),
            'build': 'v5.4.0-chartshub-owner-20260820',
            'mode': 'demo'  # 'real' when wired to live OHLC
        },
        'pipeline_steps': {
            'step1_chart_agent': finished_at,
            'step2_verdict_agent': 'synthesised by Stock Verdict Agent',
            'step3_siteowner': finished_at,
            'step4_user': 'on refresh'
        }
    }
    return output


def parse_tickers_arg(arg: str) -> list:
    """Parse a comma-separated ticker string into a list of uppercase tickers."""
    return [t.strip().upper().replace('.', '-') for t in arg.split(',') if t.strip()]


def main():
    parser = argparse.ArgumentParser(description='Stocks Chart Agent — run the chart expert pipeline')
    parser.add_argument('output_path', nargs='?', default='/workspace/cf-deploy/assets/chart_live.json',
                        help='Path to write chart_live.json (page data)')
    parser.add_argument('pack_path', nargs='?', default='/workspace/cf-deploy/assets/chart-agent-pack.json',
                        help='Path to write chart-agent-pack.json (portable knowledge pack)')
    parser.add_argument('--tickers', type=str, default=None,
                        help='Comma-separated list of tickers (default: TICKERS from sources.py)')
    args = parser.parse_args()

    cli_tickers = parse_tickers_arg(args.tickers) if args.tickers else None

    if cli_tickers:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Stocks Chart Agent starting on {len(cli_tickers)} tickers: {cli_tickers}")
    else:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Stocks Chart Agent starting...")

    out = run_engine(tickers=cli_tickers)
    print(f"[{datetime.now(timezone.utc).isoformat()}] Done. Tickers: {out['last_run']['tickers_scored']}, Experts: {out['last_run']['experts_run']}, duration: {out['last_run']['duration_s']}s")

    os.makedirs(os.path.dirname(args.output_path) or '.', exist_ok=True)
    with open(args.output_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"[OK] Wrote {args.output_path} ({os.path.getsize(args.output_path)} bytes)")

    # Build portable knowledge pack
    from build_pack import build_pack
    pack = build_pack(out)
    os.makedirs(os.path.dirname(args.pack_path) or '.', exist_ok=True)
    with open(args.pack_path, 'w') as f:
        json.dump(pack, f, indent=2)
    print(f"[OK] Wrote {args.pack_path} ({os.path.getsize(args.pack_path)} bytes)")


if __name__ == '__main__':
    main()
