from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)
CORS(app)

# ── API 키 ──────────────────────────────────────────────
ELECTION_API_KEY = "Yecdr4367t2bWw2nuYcwvf8JHmRIUCaB9F9dGPW1gkC3MWoWMsHJxdhMqGKRTKEnxJHYq2kViQIqfDTnfoL+tw=="
TOUR_API_KEY     = "Yecdr4367t2bWw2nuYcwvf8JHmRIUCaB9F9dGPW1gkC3MWoWMsHJxdhMqGKRTKEnxJHYq2kViQIqfDTnfoL+tw=="
CULTURE_API_KEY  = "3834b2d5-0cd7-4783-8439-357d5483b276"

# ── 엔드포인트 URL ───────────────────────────────────────
ELECTION_URL = "http://apis.data.go.kr/9760000/PofelcddInfoInqireService/getPoelpcddRegistSttusInfoInqire"
TOUR_URL     = "http://apis.data.go.kr/B551011/KorService1/searchFestival1"
CULTURE_URL  = "http://apis.data.go.kr/B553077/api/open/musicsProduct/listMusicsProduct"

# ────────────────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({
        "status": "ok",
        "message": "김해선거 + 문화행사 통합 API 프록시",
        "endpoints": ["/candidates", "/festivals", "/culture"]
    })

# ── 1. 선관위 후보자 ─────────────────────────────────────
@app.route("/candidates")
def candidates():
    sg_typecode = request.args.get("sgTypecode", "4")
    wiwName = "" if sg_typecode in ["2", "8"] else "김해시"
    params = {
        "serviceKey": ELECTION_API_KEY,
        "sgId": "20260603",
        "sgTypecode": sg_typecode,
        "sdName": "경상남도",
        "wiwName": wiwName,
        "numOfRows": "100",
        "pageNo": "1",
        "type": "json"
    }
    try:
        resp = requests.get(ELECTION_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict): items = [items]
        if items is None: items = []
        return jsonify({"success": True, "count": len(items), "items": items})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── 2. 한국관광공사 TourAPI 축제/행사 ────────────────────
@app.route("/festivals")
def festivals():
    area     = request.args.get("area", "")       # 지역코드
    keyword  = request.args.get("keyword", "")    # 검색어
    start    = request.args.get("start", "20260101")  # 시작일 YYYYMMDD
    end      = request.args.get("end", "20261231")    # 종료일 YYYYMMDD
    page     = request.args.get("page", "1")
    rows     = request.args.get("rows", "50")

    params = {
        "serviceKey": TOUR_API_KEY,
        "numOfRows": rows,
        "pageNo": page,
        "MobileOS": "ETC",
        "MobileApp": "CultureApp",
        "arrange": "A",
        "eventStartDate": start,
        "eventEndDate": end,
        "_type": "json"
    }
    if area:    params["areaCode"] = area
    if keyword: params["keyword"]  = keyword

    try:
        resp = requests.get(TOUR_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", {})
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict): items = [items]
        if items is None: items = []
        total = data.get("response", {}).get("body", {}).get("totalCount", 0)
        return jsonify({"success": True, "total": total, "count": len(items), "items": items})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── 3. 문체부 문화예술공연 ───────────────────────────────
@app.route("/culture")
def culture():
    page     = request.args.get("page", "1")
    rows     = request.args.get("rows", "50")
    keyword  = request.args.get("keyword", "")
    region   = request.args.get("region", "")
    start    = request.args.get("start", "")
    end      = request.args.get("end", "")

    params = {
        "serviceKey": CULTURE_API_KEY,
        "page": page,
        "rows": rows,
        "sortStdr": "1",
    }
    if keyword: params["keyword"]   = keyword
    if region:  params["sido"]      = region
    if start:   params["startDate"] = start
    if end:     params["endDate"]   = end

    try:
        resp = requests.get(CULTURE_URL, params=params, timeout=10)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "xml" in content_type or resp.text.strip().startswith("<"):
            root = ET.fromstring(resp.text)
            items = []
            for item in root.iter("item"):
                obj = {child.tag: child.text for child in item}
                items.append(obj)
            total = root.findtext(".//totalCount") or str(len(items))
            return jsonify({"success": True, "total": total, "count": len(items), "items": items})
        else:
            data = resp.json()
            items = data.get("response", {}).get("body", {}).get("items", {})
            if isinstance(items, dict): items = items.get("item", [])
            if isinstance(items, dict): items = [items]
            if items is None: items = []
            total = data.get("response", {}).get("body", {}).get("totalCount", len(items))
            return jsonify({"success": True, "total": total, "count": len(items), "items": items})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
