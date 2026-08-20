"""
build_pack.py — Build a portable knowledge pack for the Chart Agent.

The pack is a self-contained JSON that includes:
  - All source code (sources.py, classifier.py, main.py, build_pack.py, README.md)
  - The last output JSON (chart_live.json)
  - The data shape contract
  - The run config + deploy instructions
  - A rebuild recipe for an LLM to re-derive everything

The pack lives at /assets/chart-agent-pack.<HASH>.json on the deployed site,
so anyone (including an LLM) can read it and understand the full Chart Agent.
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def read_file(path: str) -> str:
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return f"# (file not found: {path})"


def file_hash(path: str) -> str:
    try:
        return hashlib.md5(open(path, 'rb').read()).hexdigest()[:8]
    except FileNotFoundError:
        return 'absent'


def build_pack(last_output: dict) -> dict:
    """Build the full knowledge pack. Returns a JSON-serializable dict."""
    here = os.path.dirname(os.path.abspath(__file__))

    sources_code = read_file(os.path.join(here, 'sources.py'))
    classifier_code = read_file(os.path.join(here, 'classifier.py'))
    main_code = read_file(os.path.join(here, 'main.py'))
    build_pack_code = read_file(os.path.join(here, 'build_pack.py'))
    readme = read_file(os.path.join(here, 'README.md'))

    sources_hash = file_hash(os.path.join(here, 'sources.py'))
    classifier_hash = file_hash(os.path.join(here, 'classifier.py'))

    pack = {
        'pack_meta': {
            'agent': 'Stocks Chart Agent',
            'pack_version': '1.0.0',
            'built_at': datetime.now(timezone.utc).isoformat(),
            'source_files': {
                'sources.py':    {'hash': sources_hash,    'size_bytes': len(sources_code)},
                'classifier.py': {'hash': classifier_hash, 'size_bytes': len(classifier_code)},
                'main.py':       {'hash': file_hash(os.path.join(here, 'main.py')),    'size_bytes': len(main_code)},
                'build_pack.py': {'hash': file_hash(os.path.join(here, 'build_pack.py')), 'size_bytes': len(build_pack_code)},
                'README.md':     {'hash': file_hash(os.path.join(here, 'README.md')),   'size_bytes': len(readme)}
            }
        },
        'agent': {
            'name': 'Stocks Chart Agent',
            'role': 'Chart sub-expert aggregator (10 chartists)',
            'parent_agent': 'Stock Verdict Agent',
            'tier': 'Tier-2 (Specialist)',
            'method': '10 chartist methodologies (Bulkowski, Wyckoff, Magee, Nison, Elliott, O\'Neil, Brandt, Brooks, Raschke, Schabacker). Each expert votes LONG / NEUTRAL / SHORT per ticker. CHART CONSENSUS = count of LONG (X/10).'
        },
        'knowledge_base': {
            'experts': last_output.get('experts', []),
            'matrix_latest': last_output.get('matrix', {}),
            'classifier_latest': last_output.get('classifier', {})
        },
        'data_shape_contract': {
            'output_json': {
                'version': 'string — pack version',
                'tickers': 'list[string] — 20 tickers',
                'experts': 'list[string] — 10 expert names',
                'matrix': {
                    'STOCK_VERDICT': 'dict[ticker, {grade, label} | null]',
                    'CHART_CONSENSUS': 'dict[ticker, {count, label}]',
                    'per_expert': 'dict[expert_name, dict[ticker, "long"|"flat"|"short"]]'
                },
                'classifier': 'dict[expert_name, {bull, neut, bear}]',
                'last_run': 'dict with timing + counters',
                'pipeline_steps': 'dict with 4 timestamps'
            }
        },
        'files': {
            'sources.py':    sources_code,
            'classifier.py': classifier_code,
            'main.py':       main_code,
            'build_pack.py': build_pack_code,
            'README.md':     readme
        },
        'run_config': {
            'command': 'python3 main.py [--tickers=AAPL,MSFT,...]',
            'output_default': '/workspace/cf-deploy/assets/chart_live.json',
            'pack_default':   '/workspace/cf-deploy/assets/chart-agent-pack.json',
            'mode': 'demo (deterministic mock)',
            'real_mode_upgrade': 'Replace classify_demo() with a real OHLC reader + per-expert logic. The 10 expert definitions in sources.py already specify the methodology (Bulkowski patterns, Wyckoff phases, Magee 200 SMA, Nison candlesticks, Elliott waves, O\'Neil CANSLIM, Brandt price structure, Brooks trend channel, Raschke ADX, Schabacker volume).'
        },
        'deploy': {
            'page_path': '/charts.html',
            'data_path': '/assets/chart_live.json',
            'pack_path': '/assets/chart-agent-pack.json',
            'owner': 'Stocks Chart Agent',
            'cf_routes': ['www.sedattrade.com/charts.html', 'sedattrade.com/charts.html']
        },
        'last_run': last_output.get('last_run', {}),
        'caveats': [
            'Demo mode uses a deterministic hash. Same ticker + same expert → same signal.',
            'To upgrade to real: replace classifier.classify_demo with a function that reads OHLC + indicators per ticker.',
            'STOCK VERDICT comes from the parent Stock Verdict Agent, not from this agent.'
        ],
        'rebuild_recipe': (
            '1. Install Python 3.11+ on a clean machine.\n'
            '2. Copy sources.py, classifier.py, main.py, build_pack.py into a directory.\n'
            '3. Run: python3 main.py /path/to/chart_live.json /path/to/chart-agent-pack.json\n'
            '4. The output JSON is consumed by /charts.html.\n'
            '5. The pack JSON is the portable knowledge dump for LLMs to rebuild this agent.'
        ),
        'notes_for_llm_consuming_this_pack': (
            'You are reading the full self-contained definition of the Stocks Chart Agent. '
            'The 10 chartist methodologies are listed in sources.py. To re-derive the matrix, '
            'run main.py — it will call classifier.classify_demo() for each (ticker, expert) pair '
            'and aggregate into per_expert / per_ticker structures.'
        )
    }
    return pack
