import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))


def calc_spend(days):
    base = 10
    mult = 1 if days <= 7 else 2 if days <= 30 else 3 if days <= 90 else 4
    low = round(base * mult)
    high = round(base * mult * 2.5)
    return f"${low}–${high}/day est.", low, high


def normalize_fb(item, country):
    start = item.get("first_shown_at") or ""
    days = int(item.get("days_shown") or 0)
    if not days and start:
        try:
            days = max(0, (datetime.now() - datetime.strptime(start[:10], "%Y-%m-%d")).days)
        except (TypeError, ValueError):
            pass
    perf = "evergreen" if days > 180 else "scaling" if days > 90 else "profitable" if days > 30 else "working" if days > 7 else "testing"
    spend_str, spend_low, spend_high = calc_spend(days)
    platforms = json.loads(item.get("platforms_json") or '["facebook"]') if isinstance(item.get("platforms_json"), str) else ["facebook"]
    img_urls = json.loads(item.get("image_urls_json") or "[]") if isinstance(item.get("image_urls_json"), str) else []
    image = item.get("image_url") or (img_urls[0] if img_urls else "")
    ad_id = item.get("ad_id") or item.get("sku", "").replace("facebook-ad-", "")
    return {
        "id": f"meta-{item.get('sku') or ad_id}", "source": "Meta Ad Library",
        "platforms": [p.lower() for p in platforms],
        "advertiser": item.get("advertiser_name") or "Facebook Advertiser",
        "pageName": item.get("advertiser_name") or "", "pageId": str(item.get("advertiser_page_id") or ""),
        "text": item.get("body") or "", "title": item.get("title") or item.get("link_title") or "",
        "originalUrl": item.get("product_url") or f"https://www.facebook.com/ads/library/?id={ad_id}",
        "image": image, "snapshotUrl": image,
        "startDate": f"{start}T00:00:00Z" if start and "T" not in str(start) else str(start),
        "endDate": "", "active": item.get("is_active", True), "daysRunning": days,
        "countries": [country], "spend": spend_str, "spendLow": spend_low, "spendHigh": spend_high,
        "impressionsLower": 0, "impressionsUpper": 0, "engagementScore": None,
        "performance": perf, "ctaText": item.get("cta_text") or "", "linkUrl": item.get("link_url") or "",
        "advertiserLikes": item.get("advertiser_likes") or 0, "displayFormat": item.get("display_format") or "IMAGE",
    }


def find_tiktok_items(data, found=None):
    if found is None:
        found = []
    if not data or not isinstance(data, (dict, list)) or len(found) >= 20:
        return found
    if isinstance(data, dict):
        if ("adId" in data or "ad_id" in data) and ("videoInfo" in data or "cover" in data):
            found.append(data)
        for value in data.values():
            find_tiktok_items(value, found)
    else:
        for item in data:
            find_tiktok_items(item, found)
    return found


def normalize_tiktok(item, country):
    ad_id = str(item.get("adId") or item.get("ad_id") or item.get("id") or "")
    video = item.get("videoInfo") or {}
    likes = item.get("like_count") or item.get("likes") or 0
    views = item.get("impression") or item.get("impressions") or 0
    ctr = item.get("ctr") or item.get("ctr_score") or 0
    spend_str, spend_low, spend_high = calc_spend(45)
    return {
        "id": f"tiktok-{ad_id}", "source": "TikTok Creative Center", "platforms": ["tiktok"],
        "advertiser": item.get("brand_name") or item.get("advertiser_name") or "TikTok Advertiser",
        "pageName": item.get("industry_name") or "Top Ad",
        "text": item.get("ad_title") or item.get("title") or item.get("description") or "",
        "title": item.get("product_name") or "",
        "image": video.get("cover") or video.get("cover_url") or item.get("cover") or "",
        "originalUrl": f"https://ads.tiktok.com/business/creativecenter/topads/{ad_id}/pc/en" if ad_id else "",
        "startDate": "", "active": True, "daysRunning": 45, "countries": [country],
        "spend": spend_str, "spendLow": spend_low, "spendHigh": spend_high,
        "impressionsLower": views, "impressionsUpper": views, "engagementScore": None,
        "performance": "profitable", "likes": likes, "ctr": ctr, "displayFormat": "VIDEO",
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "fb-ads-scraper", "version": "2.0"})


@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.json or {}
    keyword = data.get("keyword", "").strip()[:100]
    country = data.get("country", "MA").upper()
    active_only = data.get("activeOnly", False)
    max_results = min(int(data.get("maxResults", 25)), 50)
    if not keyword or len(keyword) < 2:
        return jsonify({"error": "Keyword required"}), 400
    region_map = {"MA": "MA", "FR": "FR", "BE": "BE", "SA": "SA", "AE": "AE", "DZ": "DZ", "TN": "TN", "ALL": "ALL", "US": "US", "GB": "GB"}
    region = region_map.get(country, "MA")
    cmd = [sys.executable, "playwright_scraper.py", "--query", keyword, "--region", region, "--max-results", str(max_results), "--format", "json", "--active-status", "active" if active_only else "all"]
    try:
        subprocess.run(cmd, cwd=SCRAPER_DIR, capture_output=True, text=True, timeout=120)
        output_file = os.path.join(SCRAPER_DIR, "facebook_ads.json")
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as source:
                raw = json.load(source)
            items = raw if isinstance(raw, list) else raw.get("data", [])
            ads = [normalize_fb(item, country) for item in items]
            return jsonify({"ads": ads, "count": len(ads), "source": "playwright"})
        return jsonify({"error": "No output", "ads": [], "count": 0}), 200
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout", "ads": [], "count": 0}), 200
    except Exception as error:
        return jsonify({"error": str(error), "ads": [], "count": 0}), 200


@app.route("/scrape-tiktok", methods=["POST"])
def scrape_tiktok():
    data = request.json or {}
    keyword = data.get("keyword", "").strip()[:100]
    country = data.get("country", "MA").upper()
    if not keyword:
        return jsonify({"error": "Keyword required"}), 400
    country_code = country if country != "ALL" else "MA"
    url = f"https://www.tiktok.com/api/adv/creative_center/top_ads/list/?period=30&country_code={country_code}&keyword={urllib.parse.quote(keyword)}&sort_by=ctr&page=1&limit=20"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://ads.tiktok.com/", "Accept": "application/json"}
    try:
        upstream = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(upstream, timeout=15) as response:
            raw = json.loads(response.read())
        items = find_tiktok_items(raw)
        ads = [normalize_tiktok(item, country) for item in items]
        return jsonify({"ads": ads, "count": len(ads), "source": "tiktok"})
    except Exception as error:
        return jsonify({"error": str(error), "ads": [], "count": 0}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
