import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from research_collector import collect

app = Flask(__name__)
CORS(app)
SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))


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
    spend_str, spend_low, spend_high = '', 0, 0
    return {
        "id": f"tiktok-{ad_id}", "source": "TikTok Creative Center", "platforms": ["tiktok"],
        "advertiser": item.get("brand_name") or item.get("advertiser_name") or "TikTok Advertiser",
        "pageName": item.get("industry_name") or "Top Ad",
        "text": item.get("ad_title") or item.get("title") or item.get("description") or "",
        "title": item.get("product_name") or "",
        "image": video.get("cover") or video.get("cover_url") or item.get("cover") or "",
        "originalUrl": f"https://ads.tiktok.com/business/creativecenter/topads/{ad_id}/pc/en" if ad_id else "",
        "startDate": "", "active": None, "daysRunning": 0, "countries": [country],
        "spend": spend_str, "spendLow": spend_low, "spendHigh": spend_high,
        "impressionsLower": views, "impressionsUpper": views, "engagementScore": None,
        "performance": "testing", "likes": likes, "ctr": ctr, "displayFormat": "VIDEO",
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ads-scraper", "version": "2.0"})


@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.json or {}
    keyword = data.get("keyword", "").strip()[:100]
    country = data.get("country", "MA").upper()
    active_only = data.get("activeOnly", False)
    max_results = min(int(data.get("maxResults", 25)), 50)
    if not keyword or len(keyword) < 2:
        return jsonify({"error": "Keyword required"}), 400
    result = collect(keyword, country, data.get('brand', ''), max_results,
                     str(data.get('pageQuery', '')), active_only)
    return jsonify(result), (502 if result.get('error') else 200)


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
