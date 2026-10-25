"""Scheduled public Ad Library collection with query and brand provenance."""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research_collector import collect

KEYWORDS = [
    # Netflix Morocco
    {'keyword': 'compte Netflix Maroc', 'brand': 'Netflix', 'country': 'MA'},
    {'keyword': 'abonnement Netflix Maroc', 'brand': 'Netflix', 'country': 'MA'},
    {'keyword': 'Netflix 4K Maroc', 'brand': 'Netflix', 'country': 'MA'},
    {'keyword': 'Netflix premium Maroc', 'brand': 'Netflix', 'country': 'MA'},
    {'keyword': 'vente compte Netflix', 'brand': 'Netflix', 'country': 'MA'},
    {'keyword': 'Netflix pas cher Maroc', 'brand': 'Netflix', 'country': 'MA'},

    # Spotify Morocco
    {'keyword': 'compte Spotify Maroc', 'brand': 'Spotify', 'country': 'MA'},
    {'keyword': 'abonnement Spotify Maroc', 'brand': 'Spotify', 'country': 'MA'},
    {'keyword': 'Spotify premium Maroc', 'brand': 'Spotify', 'country': 'MA'},
    {'keyword': 'vente compte Spotify', 'brand': 'Spotify', 'country': 'MA'},

    # ChatGPT Morocco
    {'keyword': 'ChatGPT Maroc', 'brand': 'ChatGPT', 'country': 'MA'},
    {'keyword': 'compte ChatGPT Maroc', 'brand': 'ChatGPT', 'country': 'MA'},
    {'keyword': 'abonnement ChatGPT Maroc', 'brand': 'ChatGPT', 'country': 'MA'},
    {'keyword': 'ChatGPT pas cher Maroc', 'brand': 'ChatGPT', 'country': 'MA'},

    # Gemini Morocco
    {'keyword': 'Gemini Maroc', 'brand': 'Gemini', 'country': 'MA'},
    {'keyword': 'abonnement Gemini Maroc', 'brand': 'Gemini', 'country': 'MA'},
    {'keyword': 'Google One Maroc', 'brand': 'Gemini', 'country': 'MA'},

    # IPTV Morocco
    {'keyword': 'IPTV Maroc', 'brand': 'IPTV', 'country': 'MA'},
    {'keyword': 'abonnement IPTV Maroc', 'brand': 'IPTV', 'country': 'MA'},
    {'keyword': 'IPTV abonnement Maroc', 'brand': 'IPTV', 'country': 'MA'},

    # Digital products Morocco (general)
    {'keyword': 'comptes digitaux Maroc', 'brand': 'Digital', 'country': 'MA'},
    {'keyword': 'Canva Pro Maroc', 'brand': 'Canva', 'country': 'MA'},
    {'keyword': 'اشتراك نتفليكس المغرب', 'brand': 'Netflix', 'country': 'MA'},
    {'keyword': 'اشتراكات رقمية المغرب', 'brand': 'Digital', 'country': 'MA'},

    # France
    {'keyword': 'compte Netflix France', 'brand': 'Netflix', 'country': 'FR'},
    {'keyword': 'abonnement Netflix France', 'brand': 'Netflix', 'country': 'FR'},
    {'keyword': 'Netflix moins cher France', 'brand': 'Netflix', 'country': 'FR'},
    {'keyword': 'compte Spotify France', 'brand': 'Spotify', 'country': 'FR'},
    {'keyword': 'ChatGPT France pas cher', 'brand': 'ChatGPT', 'country': 'FR'},
    {'keyword': 'IPTV France', 'brand': 'IPTV', 'country': 'FR'},

    # Belgium
    {'keyword': 'compte Netflix Belgique', 'brand': 'Netflix', 'country': 'BE'},
    {'keyword': 'Netflix Belgique pas cher', 'brand': 'Netflix', 'country': 'BE'},
    {'keyword': 'IPTV Belgique', 'brand': 'IPTV', 'country': 'BE'},

    # Canada
    {'keyword': 'compte Netflix Canada', 'brand': 'Netflix', 'country': 'CA'},
    {'keyword': 'Netflix Canada cheap', 'brand': 'Netflix', 'country': 'CA'},
    {'keyword': 'Spotify Canada cheap', 'brand': 'Spotify', 'country': 'CA'},
    {'keyword': 'ChatGPT Canada', 'brand': 'ChatGPT', 'country': 'CA'},
    {'keyword': 'IPTV Canada Arabic', 'brand': 'IPTV', 'country': 'CA'},
    {'keyword': 'IPTV Canada', 'brand': 'IPTV', 'country': 'CA'},
    {'keyword': 'Netflix account Canada', 'brand': 'Netflix', 'country': 'CA'},

    # Saudi Arabia
    {'keyword': 'Netflix Saudi', 'brand': 'Netflix', 'country': 'SA'},
    {'keyword': 'اشتراك نتفليكس السعودية', 'brand': 'Netflix', 'country': 'SA'},
    {'keyword': 'IPTV Saudi', 'brand': 'IPTV', 'country': 'SA'},
    {'keyword': 'Spotify Saudi', 'brand': 'Spotify', 'country': 'SA'},

    # Algeria
    {'keyword': 'compte Netflix Algerie', 'brand': 'Netflix', 'country': 'DZ'},
    {'keyword': 'Netflix Algérie pas cher', 'brand': 'Netflix', 'country': 'DZ'},
    {'keyword': 'IPTV Algerie', 'brand': 'IPTV', 'country': 'DZ'},
]

def save_to_database(ads, search_query, brand):
    saved = 0
    for offset in range(0, len(ads), 50):
        batch = ads[offset:offset + 50]
        response = requests.post(os.environ['INGEST_URL'],
            json={'ads': batch, 'searchQuery': search_query, 'brand': brand},
            headers={'x-ingest-key': os.environ['INGEST_KEY']}, timeout=45)
        if not response.ok:
            raise RuntimeError(f'Database rejected collection: HTTP {response.status_code}')
        count = response.json().get('saved', 0)
        if count != len(batch):
            raise RuntimeError(f'Database accepted only {count} of {len(batch)} records')
        saved += count
    return saved


def main():
    if not os.environ.get('INGEST_URL') or not os.environ.get('INGEST_KEY'):
        raise SystemExit('Missing INGEST_URL or INGEST_KEY. Nothing was scraped or saved.')
    summary = []
    for item in KEYWORDS:
        print(f"Collecting {item['keyword']} [{item['country']}]", flush=True)
        result = collect(item['keyword'], item['country'], item['brand'], max_results=50)
        # Public-library pages occasionally time out or return a transient block.
        # Retry once so one temporary failure does not leave a brand uncollected.
        if result.get('status') in ('failed', 'timeout'):
            print(f"Retrying {item['keyword']} after {result['status']}", flush=True)
            time.sleep(3)
            result = collect(item['keyword'], item['country'], item['brand'], max_results=50)
        saved = 0
        try:
            saved = save_to_database(result['ads'], item['keyword'], item['brand'])
        except (requests.RequestException, RuntimeError) as error:
            result = {**result, 'status': 'ingest_failed', 'error': type(error).__name__}
        row = {**item, 'status': result['status'], 'found': len(result['ads']), 'saved': saved, 'error': result.get('error', '')}
        summary.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report = {'at': datetime.now(timezone.utc).isoformat(), 'queries': summary, 'saved': sum(row['saved'] for row in summary)}
    Path('collection-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as out:
            out.write('## Collection results\n\n| Search | Country | Status | Saved |\n|---|---|---|---|\n')
            for row in summary:
                out.write(f"| {row['keyword']} | {row['country']} | {row['status']} | {row['saved']} |\n")
    print(f"Saved {report['saved']} observations. Empty searches are not filled with previous results.", flush=True)
    if any(row['status'] in ('failed', 'timeout', 'ingest_failed') for row in summary):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
