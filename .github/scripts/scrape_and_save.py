"""
GitHub Actions scraper script.
Runs playwright_scraper.py for each keyword, collects results,
then POSTs them to the Cloudflare Worker ingest endpoint.
"""

import subprocess
import json
import os
import sys
import requests
from datetime import datetime

INGEST_URL = os.environ.get('INGEST_URL', '')
INGEST_KEY = os.environ.get('INGEST_KEY', '')

KEYWORDS = [
    {'keyword': 'Netflix Maroc', 'country': 'MA'},
    {'keyword': 'Spotify Maroc', 'country': 'MA'},
    {'keyword': 'ChatGPT Maroc', 'country': 'MA'},
    {'keyword': 'IPTV Maroc', 'country': 'MA'},
    {'keyword': 'iPhone Maroc', 'country': 'MA'},
    {'keyword': 'Gemini Maroc', 'country': 'MA'},
    {'keyword': 'Netflix France', 'country': 'FR'},
    {'keyword': 'Spotify France', 'country': 'FR'},
    {'keyword': 'Netflix Saudi', 'country': 'SA'},
    {'keyword': 'IPTV Saudi', 'country': 'SA'},
    {'keyword': 'Netflix Algeria', 'country': 'DZ'},
    {'keyword': 'ChatGPT', 'country': 'MA'},
]

def calc_spend(days):
    base = 10
    mult = 1 if days <= 7 else 2 if days <= 30 else 3 if days <= 90 else 4
    low = round(base * mult)
    high = round(base * mult * 2.5)
    return f"${low}–${high}/day est.", low, high

def normalize(item, country):
    start = item.get('first_shown_at') or ''
    days = int(item.get('days_shown') or 0)
    if not days and start:
        try:
            days = max(0, (datetime.now() - datetime.strptime(start[:10], '%Y-%m-%d')).days)
        except:
            pass

    perf = ('evergreen' if days > 180 else 'scaling' if days > 90 else
            'profitable' if days > 30 else 'working' if days > 7 else 'testing')
    spend_str, spend_low, spend_high = calc_spend(days)

    try:
        platforms = json.loads(item.get('platforms_json') or '["facebook"]')
    except:
        platforms = ['facebook']

    try:
        img_urls = json.loads(item.get('image_urls_json') or '[]')
    except:
        img_urls = []

    image = item.get('image_url') or (img_urls[0] if img_urls else '')
    ad_id = item.get('ad_id') or item.get('sku', '').replace('facebook-ad-', '')

    return {
        'id': f"meta-{item.get('sku') or ad_id}",
        'source': 'Meta Ad Library',
        'platforms': [p.lower() for p in platforms],
        'advertiser': item.get('advertiser_name') or 'Facebook Advertiser',
        'pageName': item.get('advertiser_name') or '',
        'pageId': str(item.get('advertiser_page_id') or ''),
        'text': item.get('body') or '',
        'title': item.get('title') or item.get('link_title') or '',
        'originalUrl': item.get('product_url') or f"https://www.facebook.com/ads/library/?id={ad_id}",
        'image': image,
        'snapshotUrl': image,
        'startDate': f"{start}T00:00:00Z" if start and 'T' not in str(start) else str(start),
        'endDate': '',
        'active': item.get('is_active', True),
        'daysRunning': days,
        'countries': [country],
        'spend': spend_str,
        'spendLow': spend_low,
        'spendHigh': spend_high,
        'impressionsLower': 0,
        'impressionsUpper': 0,
        'engagementScore': None,
        'performance': perf,
        'ctaText': item.get('cta_text') or '',
        'linkUrl': item.get('link_url') or '',
        'advertiserLikes': item.get('advertiser_likes') or 0,
        'displayFormat': item.get('display_format') or 'IMAGE',
    }

def scrape_keyword(keyword, country, max_results=20):
    region_map = {
        'MA': 'MA', 'FR': 'FR', 'BE': 'BE', 'SA': 'SA',
        'AE': 'AE', 'DZ': 'DZ', 'TN': 'TN'
    }
    region = region_map.get(country, 'MA')

    cmd = [
        sys.executable, 'playwright_scraper.py',
        '--query', keyword,
        '--region', region,
        '--max-results', str(max_results),
        '--format', 'json',
        '--active-status', 'all',
    ]

    print(f"  Scraping: {keyword} ({country})")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        output_file = 'facebook_ads.json'
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            items = raw if isinstance(raw, list) else raw.get('data', [])
            ads = [normalize(item, country) for item in items]
            print(f"  Found {len(ads)} ads")
            return ads
        print(f"  No output file")
    except subprocess.TimeoutExpired:
        print(f"  Timeout")
    except Exception as e:
        print(f"  Error: {e}")
    return []

def save_to_database(ads):
    if not ads:
        return 0
    if not INGEST_URL or not INGEST_KEY:
        print("  WARNING: INGEST_URL or INGEST_KEY not set")
        return 0
    try:
        response = requests.post(
            INGEST_URL,
            json={'ads': ads},
            headers={
                'Content-Type': 'application/json',
                'x-ingest-key': INGEST_KEY,
            },
            timeout=30
        )
        if response.ok:
            data = response.json()
            saved = data.get('saved', len(ads))
            print(f"  Saved {saved} ads to database")
            return saved
        else:
            print(f"  Database error: {response.status_code} {response.text[:100]}")
    except Exception as e:
        print(f"  Database save failed: {e}")
    return 0

def main():
    print(f"Starting scrape at {datetime.now().isoformat()}")
    print(f"Keywords: {len(KEYWORDS)}")
    print(f"Ingest URL: {INGEST_URL[:40]}..." if INGEST_URL else "WARNING: No ingest URL")

    total_scraped = 0
    total_saved = 0
    all_ads = []

    for item in KEYWORDS:
        keyword = item['keyword']
        country = item['country']
        ads = scrape_keyword(keyword, country)
        all_ads.extend(ads)
        total_scraped += len(ads)

    # Deduplicate by ID
    seen = set()
    unique_ads = []
    for ad in all_ads:
        if ad['id'] not in seen:
            seen.add(ad['id'])
            unique_ads.append(ad)

    print(f"\nTotal scraped: {total_scraped}")
    print(f"Unique ads: {len(unique_ads)}")

    # Save in batches of 50
    for i in range(0, len(unique_ads), 50):
        batch = unique_ads[i:i+50]
        saved = save_to_database(batch)
        total_saved += saved

    print(f"Total saved to database: {total_saved}")
    print(f"Done at {datetime.now().isoformat()}")

if __name__ == '__main__':
    main()
