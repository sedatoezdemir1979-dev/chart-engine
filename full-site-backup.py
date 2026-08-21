#!/usr/bin/env python3
"""
full-site-backup.py — Create a full-site backup ZIP and update the manifest.

Run from /workspace:
  python3 full-site-backup.py

Outputs:
  - /workspace/sedattrade-state-YYYYMMDD-HHMM-v5.4.11.zip
  - Copies to /tmp/ and /root/sedattrade-backups/
  - Updates /workspace/cf-deploy/assets/backups-manifest.json
  - Updates /workspace/cf-deploy/assets/files-manifest.json

Then deploy:
  bash /workspace/cf-deploy/deploy-no-test.sh
"""
import os
import sys
import json
import time
import hashlib
import shutil
import zipfile
import fnmatch
import glob
from datetime import datetime, timezone
from pathlib import Path

CF_DEPLOY = Path('/workspace/cf-deploy')
ASSETS = CF_DEPLOY / 'assets'
BACKUP_DIR = ASSETS / 'backups'
BACKUP_DIR.mkdir(exist_ok=True)
DEST = Path('/workspace')


def log(msg):
    print(f'[{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}] {msg}', flush=True)


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_files_manifest():
    """List every file in /workspace/cf-deploy that should be backed up."""
    files = []
    for p in sorted(CF_DEPLOY.iterdir()):
        if p.is_file() and p.name not in ['.git', '.wrangler']:
            files.append({
                'path': p.name,
                'url': '/' + p.name,
                'size': p.stat().st_size,
            })
    # All assets (excluding backups dir to avoid recursion)
    for p in sorted(ASSETS.iterdir()):
        if p.is_file() and p.name != 'backups-manifest.json':
            files.append({
                'path': f'assets/{p.name}',
                'url': f'/assets/{p.name}',
                'size': p.stat().st_size,
            })
    return files


def make_backup_zip():
    """Create a ZIP of the full site (everything needed to restore)."""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')
    version = 'v5.4.11'  # Update this when needed
    zip_name = f'sedattrade-state-{timestamp}-{version}.zip'
    zip_path = DEST / zip_name
    log(f'Creating {zip_path}…')

    # Files to include in the ZIP
    include_paths = [
        CF_DEPLOY,  # the full cf-deploy/ (with .git excluded)
        Path('/workspace/news-engine'),
        Path('/workspace/chart-engine'),
        Path('/workspace/chart-daily-pipeline.py'),
        Path('/workspace/fetch_real_candles.py'),
        Path('/workspace/restructure_charts.py'),
        Path('/workspace/fix_charts_v5.4.6.py'),
        Path('/workspace/unify_nav.py'),
        Path('/workspace/remove_js_gate.py'),
        Path('/workspace/remove_chart_library.py'),
    ]
    # Exclude patterns
    exclude_patterns = [
        '.git/', '.wrangler/', 'node_modules/', 'screenshots/',
        'visual-baselines/', 'imgs/', '__pycache__/', 'docs/',
        'scrubber-*.png', 'verify-*.png', 'matrix-*.png',
        'stop-flicker.html', '_tmp*', '.home/', '*.tar', '*.zip',
        'cf-deploy/.locked/', 'cf-deploy/.mavis/', 'cf-deploy/.mavis-skills/',
        'cf-deploy/.backups/', 'cf-deploy/_tmp*',
    ]

    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
        for path in include_paths:
            if not path.exists():
                continue
            if path.is_file():
                zf.write(path, path.relative_to(DEST))
                file_count += 1
                total_bytes += path.stat().st_size
                continue
            for root, dirs, files in os.walk(path):
                # Prune excluded dirs
                dirs[:] = [d for d in dirs if not any(p in f'{root}/{d}/' for p in exclude_patterns)]
                for f in files:
                    fp = Path(root) / f
                    rel = fp.relative_to(DEST)
                    rel_str = str(rel)
                    if any(excl.rstrip('/') in rel_str for excl in exclude_patterns):
                        continue
                    zf.write(fp, rel)
                    file_count += 1
                    total_bytes += fp.stat().st_size
    log(f'  {file_count} files, {total_bytes/1024/1024:.1f}MB raw, {zip_path.stat().st_size/1024/1024:.1f}MB zip')
    return zip_path, file_count, total_bytes


def copy_to_locations(zip_path):
    """Copy the ZIP to 3 backup locations."""
    for dest in [Path('/tmp'), Path('/root/sedattrade-backups')]:
        dest.mkdir(parents=True, exist_ok=True)
        dest_path = dest / zip_path.name
        shutil.copy2(zip_path, dest_path)
        log(f'  Copied to {dest_path}')


def update_backups_manifest(zip_path, file_count, total_bytes, version):
    """Update the static backups-manifest.json so the /backups page shows it."""
    raw = zip_path.read_bytes()
    manifest_path = ASSETS / 'backups-manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {'backups': [], 'snapshots': []}
    # Avoid duplicates
    manifest['backups'] = [b for b in manifest.get('backups', []) if b.get('filename') != zip_path.name]
    manifest['backups'].append({
        'id': zip_path.stem,
        'filename': zip_path.name,
        'size_bytes': len(raw),
        'sha256': sha256(raw),
        'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'version': version,
        'description': f'Full site backup: {file_count} files ({total_bytes/1024/1024:.1f}MB raw)',
        'file_count': file_count,
        'url': f'/assets/backups/{zip_path.name}',
    })
    manifest['last_updated'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    manifest['total_backups'] = len(manifest['backups'])
    manifest['total_size_bytes'] = sum(b.get('size_bytes', 0) for b in manifest['backups'])
    manifest_path.write_text(json.dumps(manifest, indent=2))
    log(f'  Updated {manifest_path}')

    # Also copy the actual ZIP into assets/backups/ for CF to serve
    target = BACKUP_DIR / zip_path.name
    shutil.copy2(zip_path, target)
    log(f'  Copied to {target}')


def update_files_manifest():
    """Update files-manifest.json so snapshots can be created."""
    files = build_files_manifest()
    manifest = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'total_files': len(files),
        'total_size_bytes': sum(f['size'] for f in files),
        'files': files,
    }
    (ASSETS / 'files-manifest.json').write_text(json.dumps(manifest, indent=2))
    log(f'  Updated files-manifest.json ({len(files)} files)')


def main():
    log('=== Full-site backup ===')
    zip_path, file_count, total_bytes = make_backup_zip()
    copy_to_locations(zip_path)
    update_backups_manifest(zip_path, file_count, total_bytes, 'v5.4.11')
    update_files_manifest()
    log('=== Done. Deploy with: bash /workspace/cf-deploy/deploy-no-test.sh ===')


if __name__ == '__main__':
    main()
