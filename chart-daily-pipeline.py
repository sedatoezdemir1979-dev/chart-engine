#!/usr/bin/env python3
"""
chart-daily-pipeline.py — Daily chart data refresh (idempotent, retry-safe).

Steps:
  1. Fetch real 1Y daily candles from Yahoo Finance for 20 tickers
  2. Run chart-engine (10 experts × 20 tickers) → chart_live.json
  3. Hash-bust filenames and update charts.html refs
  4. Optional --deploy to push to live

Usage:
  python3 chart-daily-pipeline.py                  # run pipeline (writes files)
  python3 chart-daily-pipeline.py --deploy         # also run deploy-no-test.sh after
  python3 chart-daily-pipeline.py --dry-run       # just check Yahoo is reachable

Yahoo rate limits: ~1 req/sec sustained, ~30 req/min burst. With 20 tickers
plus 1 cookie + 1 crumb = 22 requests, runs in ~30s. We add 0.4s spacing
and exponential backoff on 429/Unauthorized responses.
"""
import subprocess, json, time, hashlib, glob, os, re, sys
from datetime import datetime, timezone

TICKERS = ['AAPL','NVDA','JPM','KO','INTC','IBM','T','F','MSFT','GOOGL','AMZN','META','TSLA','BRK-B','WMT','DIS','XOM','NFLX','BA','AMD']
COOKIE_JAR = '/tmp/cj_yahoo.txt'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
ASSETS_DIR = '/workspace/cf-deploy/assets'
HTTP_TIMEOUT = 20
INTER_REQ_SLEEP = 0.4  # 0.4s between requests = 2.5 req/s, well under Yahoo's limit


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}] {msg}", flush=True)


def curl_capture(cmd, retries=4):
    """Run curl command, retry with exponential backoff on rate limit / cookie errors."""
    for attempt in range(retries):
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.PIPE, timeout=HTTP_TIMEOUT).decode()
            if '"Unauthorized"' in out or '"Too Many Requests"' in out or '"rate limit"' in out.lower():
                wait = 5 * (attempt + 1)
                log(f"  Rate limited (attempt {attempt+1}/{retries}), sleeping {wait}s...")
                time.sleep(wait)
                continue
            return out
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b'').decode()[:200]
            if 'HTTP 429' in err or 'HTTP 401' in err:
                wait = 5 * (attempt + 1)
                log(f"  HTTP rate limit (attempt {attempt+1}/{retries}): {err[:80]}")
                time.sleep(wait)
                continue
            if attempt == retries - 1:
                raise
            time.sleep(2)
    return None


def fresh_cookies_and_crumb():
    """Get fresh cookies from Yahoo homepage + a matching crumb. Returns crumb string."""
    log("Refreshing Yahoo cookies + crumb...")
    subprocess.run(['curl','-sS','--max-time','15','-c',COOKIE_JAR,'-A',UA,'https://fc.yahoo.com/'],
                   check=True, capture_output=True)
    out = curl_capture(['curl','-sS','--max-time','15','-b',COOKIE_JAR,'-A',UA,
                        'https://query1.finance.yahoo.com/v1/test/getcrumb'])
    if not out or '"Unauthorized"' in out:
        log(f"  Crumb failed: {out[:200] if out else 'no output'}")
        return None
    crumb = out.strip()
    log(f"  Got crumb: {crumb[:20]}...")
    return crumb


def fetch_one(ticker, crumb, retries=3):
    """Fetch one ticker's 1Y daily OHLCV. Returns list of bars or None on fail."""
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d&crumb={crumb}'
    for attempt in range(retries):
        out = curl_capture(['curl','-sS','--max-time',str(HTTP_TIMEOUT),'-b',COOKIE_JAR,'-A',UA,url], retries=3)
        if not out: return None
        try:
            d = json.loads(out)
        except json.JSONDecodeError:
            return None
        r = d.get('chart',{}).get('result')
        if r:
            res = r[0]
            ts = res.get('timestamp', [])
            q = res.get('indicators',{}).get('quote',[{}])[0]
            bars = []
            for i in range(len(ts)):
                if q['open'][i] is None or q['close'][i] is None: continue
                bars.append({
                    'd': time.strftime('%Y-%m-%d', time.gmtime(ts[i])),
                    'o': round(float(q['open'][i]),2),
                    'h': round(float(q['high'][i]),2),
                    'l': round(float(q['low'][i]),2),
                    'c': round(float(q['close'][i]),2),
                    'v': int(q['volume'][i] or 0),
                })
            return bars
        if attempt < retries - 1:
            log(f"  {ticker}: no result, refreshing crumb (attempt {attempt+1})")
            crumb = fresh_cookies_and_crumb()
            if not crumb: return None
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d&crumb={crumb}'
    return None


def fetch_all_candles():
    """Fetch candles for all 20 tickers. Returns dict of ticker → bars."""
    log(f"Step 1/4: Fetch real Yahoo candles for {len(TICKERS)} tickers...")
    crumb = fresh_cookies_and_crumb()
    if not crumb:
        log("  FAIL: could not get initial crumb")
        return {}
    result = {}
    fails = []
    for t in TICKERS:
        bars = fetch_one(t, crumb)
        if bars:
            result[t] = bars
            log(f"  ✓ {t}: {len(bars)} bars, last close=${bars[-1]['c']}")
        else:
            fails.append(t)
            log(f"  ✗ {t}: fetch failed")
        time.sleep(INTER_REQ_SLEEP)
    log(f"  → {len(result)}/{len(TICKERS)} tickers fetched. Fails: {fails}")
    return result


def write_hashed(data, base_name):
    """Write JSON to hash-busted filename. Returns (path, hash)."""
    raw = json.dumps(data, separators=(',',':')).encode('utf-8')
    h = hashlib.md5(raw).hexdigest()[:8]
    out = f'{ASSETS_DIR}/{base_name}.{h}.json'
    with open(out, 'wb') as f:
        f.write(raw)
    for old in glob.glob(f'{ASSETS_DIR}/{base_name}.*.json'):
        if old != out: os.remove(old)
    return out, h


def run_chart_engine():
    """Run /workspace/chart-engine/main.py to score experts."""
    log("Step 2/4: Run chart-engine (10 experts × 20 tickers)...")
    r = subprocess.run(
        ['python3', '/workspace/chart-engine/main.py',
         f'{ASSETS_DIR}/chart_live.json',
         f'{ASSETS_DIR}/chart-agent-pack.json'],
        capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        log(f"  FAIL: chart-engine exited {r.returncode}")
        log(f"  STDERR: {r.stderr[:500]}")
        return None
    log(f"  chart-engine OK")
    for line in r.stdout.splitlines()[-3:]:
        log(f"  {line}")
    return f'{ASSETS_DIR}/chart_live.json'


def update_html_ref(new_hashes):
    """Update charts.html to reference the new hashed filenames."""
    log("Step 3/4: Update charts.html to use new asset hashes...")
    p = '/workspace/cf-deploy/charts.html'
    with open(p) as f: h = f.read()
    changes = []
    for pattern, new_name in [
        (r'chart_candles\.[a-f0-9]{8}\.json', f'chart_candles.{new_hashes["candles"]}.json'),
        (r'chart_live\.[a-f0-9]{8}\.json', f'chart_live.{new_hashes["live"]}.json'),
        (r'chart-agent-pack\.[a-f0-9]{8}\.json', f'chart-agent-pack.{new_hashes["pack"]}.json'),
    ]:
        new_h = re.sub(pattern, new_name, h)
        if new_h != h:
            changes.append(pattern)
            h = new_h
    with open(p, 'w') as f: f.write(h)
    log(f"  Updated: {changes}")


def main():
    args = sys.argv[1:]
    deploy = '--deploy' in args
    dry_run = '--dry-run' in args

    if dry_run:
        crumb = fresh_cookies_and_crumb()
        if crumb:
            log("Yahoo reachable, auth OK")
            return 0
        log("Yahoo not reachable / auth failed")
        return 1

    # Step 1: candles
    candles = fetch_all_candles()
    if len(candles) < 15:
        log(f"FAIL: only {len(candles)}/20 tickers fetched. Need at least 15.")
        return 1
    candle_path, candle_hash = write_hashed(candles, 'chart_candles')
    log(f"  Wrote {candle_path} ({os.path.getsize(candle_path)} bytes)")

    # Step 2: chart engine
    live_path = run_chart_engine()
    if not live_path or not os.path.exists(live_path):
        log("FAIL: chart-engine did not produce chart_live.json")
        return 1
    with open(live_path) as f: live = json.load(f)
    _, live_hash = write_hashed(live, 'chart_live')

    # Hash the pack
    pack_path = f'{ASSETS_DIR}/chart-agent-pack.json'
    pack_hash = None
    if os.path.exists(pack_path):
        with open(pack_path) as f: pack = json.load(f)
        _, pack_hash = write_hashed(pack, 'chart-agent-pack')

    new_hashes = {'candles': candle_hash, 'live': live_hash, 'pack': pack_hash}

    # Step 3: update HTML
    update_html_ref(new_hashes)

    log("")
    log(f"Daily pipeline done. New hashes: {new_hashes}")
    log(f"  {len(candles)} tickers × {len(next(iter(candles.values())))} bars")
    log(f"  chart_live: {live['last_run']['tickers_scored']} tickers × {live['last_run']['experts_run']} experts")

    # Step 4 (optional): deploy
    if deploy:
        log("Step 4/4: Deploying (deploy-no-test.sh)...")
        r = subprocess.run(['bash', '/workspace/cf-deploy/deploy-no-test.sh'],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            log(f"  Deploy FAILED: {r.stderr[:300]}")
            return 1
        log(f"  Deploy OK")
    else:
        log(f"  (Skipping deploy. Run with --deploy to push live.)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
