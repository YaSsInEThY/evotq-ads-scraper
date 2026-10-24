"""Scheduled public Ad Library collection with query and brand provenance."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research_collector import collect

KEYWORDS = [{'keyword': 'compte Netflix Maroc', 'brand': 'Netflix', 'country': 'MA'},
 {'keyword': 'abonnement Netflix Maroc', 'brand': 'Netflix', 'country': 'MA'},
 {'keyword': 'Netflix 4K Maroc', 'brand': 'Netflix', 'country': 'MA'},
 {'keyword': 'Netflix premium Maroc', 'brand': 'Netflix', 'country': 'MA'},
 {'keyword': 'compte Spotify Maroc', 'brand': 'Spotify', 'country': 'MA'},
 {'keyword': 'abonnement Spotify Maroc', 'brand': 'Spotify', 'country': 'MA'},
 {'keyword': 'ChatGPT Maroc', 'brand': 'ChatGPT', 'country': 'MA'},
 {'keyword': 'compte ChatGPT Maroc', 'brand': 'ChatGPT', 'country': 'MA'},
 {'keyword': 'abonnement ChatGPT Maroc', 'brand': 'ChatGPT', 'country': 'MA'},
 {'keyword': 'Gemini Maroc', 'brand': 'Gemini', 'country': 'MA'},
 {'keyword': 'IPTV Maroc', 'brand': 'IPTV', 'country': 'MA'},
 {'keyword': 'abonnement IPTV Maroc', 'brand': 'IPTV', 'country': 'MA'},
 {'keyword': 'اشتراك نتفليكس المغرب', 'brand': 'Netflix', 'country': 'MA'},
 {'keyword': 'اشتراك سبوتيفاي المغرب', 'brand': 'Spotify', 'country': 'MA'},
 {'keyword': 'compte Netflix France', 'brand': 'Netflix', 'country': 'FR'},
 {'keyword': 'abonnement Netflix France', 'brand': 'Netflix', 'country': 'FR'},
 {'keyword': 'compte Spotify France', 'brand': 'Spotify', 'country': 'FR'},
 {'keyword': 'ChatGPT France', 'brand': 'ChatGPT', 'country': 'FR'},
 {'keyword': 'Netflix Saudi', 'brand': 'Netflix', 'country': 'SA'},
 {'keyword': 'IPTV Saudi', 'brand': 'IPTV', 'country': 'SA'},
 {'keyword': 'اشتراك نتفليكس السعودية', 'brand': 'Netflix', 'country': 'SA'}]

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
        result = collect(item['keyword'], item['country'], item['brand'])
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
