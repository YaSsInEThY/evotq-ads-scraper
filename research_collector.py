"""Collect one isolated search; never read another run's output file."""
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def as_list(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    return value if isinstance(value, list) else []


def normalize(item, country, brand='', query=''):
    ad_id = str(item.get('ad_id') or item.get('sku', '').replace('facebook-ad-', ''))
    if not ad_id or not ad_id.isdigit():
        return None
    start = item.get('first_shown_at') or ''
    days = max(0, int(item.get('days_shown') or 0))
    images = as_list(item.get('image_urls_json'))
    videos = as_list(item.get('video_urls_json'))
    return {
        'id': f'meta-facebook-ad-{ad_id}', 'source': 'Meta Ad Library',
        'brand': brand, 'searchQuery': query,
        'platforms': [str(p).lower() for p in as_list(item.get('platforms_json'))],
        'advertiser': item.get('advertiser_name') or '',
        'pageId': str(item.get('advertiser_page_id') or ''),
        'text': item.get('body') or '', 'title': item.get('link_title') or item.get('title') or '',
        'originalUrl': f'https://www.facebook.com/ads/library/?id={ad_id}',
        'image': item.get('image_url') or (images[0] if images else ''),
        'videoUrl': videos[0] if videos else '',
        'startDate': start, 'daysRunning': days, 'active': item.get('is_active'),
        'countries': [country], 'spend': '', 'spendLow': 0, 'spendHigh': 0,
        'ctaText': item.get('cta_text') or '', 'linkUrl': item.get('link_url') or '',
        'advertiserLikes': item.get('advertiser_likes') or 0,
        'displayFormat': item.get('display_format') or 'IMAGE',
        'lastSeen': datetime.now(timezone.utc).isoformat(),
    }


def collect(query, country, brand='', max_results=50, page_id='', active_only=False, timeout=90):
    region_map = {
        'MA': 'MA', 'FR': 'FR', 'BE': 'BE', 'SA': 'SA',
        'AE': 'AE', 'DZ': 'DZ', 'TN': 'TN', 'CA': 'CA',
        'GB': 'GB', 'US': 'US', 'ALL': 'ALL',
    }
    country = region_map.get(str(country).upper(), 'ALL')
    with tempfile.TemporaryDirectory(prefix='evotq-research-') as temporary:
        output = Path(temporary) / 'ads.json'
        cmd = [sys.executable, str(ROOT / 'playwright_scraper.py'),
               '--region', country, '--max-results', str(max_results), '--format', 'json',
               '--active-status', 'active' if active_only else 'all', '--out', str(output), '--retries', '0']
        cmd.extend(['--page-id', page_id] if page_id.isdigit() else ['--query', query])
        try:
            run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        except subprocess.TimeoutExpired:
            return {'ads': [], 'status': 'timeout', 'error': 'Public library search timed out.'}
        if run.returncode == 4:
            return {'ads': [], 'status': 'empty'}
        if run.returncode not in (0, 6):
            return {'ads': [], 'status': 'failed', 'error': f'Scraper exited with code {run.returncode}; no old output was ingested.'}
        if not output.exists():
            return {'ads': [], 'status': 'failed', 'error': 'This run produced no fresh output.'}
        raw = json.loads(output.read_text(encoding='utf-8'))
        items = raw if isinstance(raw, list) else raw.get('data', [])
        ads = [ad for item in items if isinstance(item, dict) for ad in [normalize(item, country, brand, query)] if ad]
        return {'ads': ads, 'status': 'partial' if run.returncode == 6 else 'ok'}
