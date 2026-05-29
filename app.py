from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import xml.etree.ElementTree as ET
import re

app = Flask(__name__)
CORS(app)

TOUR_API_KEY    = "Yecdr4367t2bWw2nuYcwvf8JHmRIUCaB9F9dGPW1gkC3MWoWMsHJxdhMqGKRTKEnxJHYq2kViQIqfDTnfoL+tw=="
CULTURE_API_KEY = "3834b2d5-0cd7-4783-8439-357d5483b276"
TOUR_URL        = "http://apis.data.go.kr/B551011/KorService1/searchFestival1"
CULTURE_URL     = "http://apis.data.go.kr/B553077/api/open/musicsProduct/listMusicsProduct"

ELECTION_ID = "0020260603"

# 선거종류코드 → info.nec.go.kr 메뉴ID 매핑
TYPE_MENU = {
    "3":  "PCCP02", # 시도지사
    "4":  "PCCP03", # 시장군수구청장
    "5":  "PCCP04", # 시도의원
    "6":  "PCCP05", # 시군구의원
    "11": "PCCP07", # 교육감
}
TYPE_NAMES = {
    "3":"경남도지사","4":"김해시장",
    "5":"경남도의원","6":"김해시의원","11":"경남교육감"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://info.nec.go.kr/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

def parse_resp(resp):
    text = resp.text.strip()
    if text.startswith("<"):
        root = ET.fromstring(text)
        err = root.findtext(".//resultCode") or ""
        if err and err not in ("00","0000","OK",""):
            msg = root.findtext(".//resultMsg") or ""
            return [], 0, f"{err}:{msg}"
        items = [{c.tag:(c.text or "").strip() for c in i} for i in root.iter("item")]
        items = [i for i in items if i]
        total = root.findtext(".//totalCount") or str(len(items))
        return items, int(total) if str(total).isdigit() else len(items), None
    data = resp.json()
    hdr  = data.get("response",{}).get("header",{})
    code = str(hdr.get("resultCode","00"))
    if code not in ("00","0000","OK",""):
        return [], 0, f'{code}:{hdr.get("resultMsg","")}'
    body  = data.get("response",{}).get("body",{})
    items = body.get("items") or {}
    if isinstance(items, dict): items = items.get("item",[])
    if isinstance(items, dict): items = [items]
    return items or [], int(body.get("totalCount", 0)), None

@app.route("/")
def index():
    return jsonify({"status":"ok","endpoints":["/candidates","/festivals","/culture"]})

# ── 1. 선관위 info.nec.go.kr 스크래핑 ─────────────────
@app.route("/candidates")
def candidates():
    sg_typecode = request.args.get("sgTypecode", "4")
    menu_id = TYPE_MENU.get(sg_typecode, "PCCP03")

    # info.nec.go.kr AJAX 엔드포인트
    url = f"https://info.nec.go.kr/electioninfo/electionInfo_report.xhtml"
    params = {
        "electionId": ELECTION_ID,
        "requestURI": f"/electioninfo/2026/cp/cpri{sg_typecode.zfill(2)}P.jsp",
        "topMenuId": "PC",
        "secondMenuId": menu_id,
    }

    # 방법1: info.nec.go.kr 후보자 목록 페이지 파싱
    try:
        # 경남/김해 후보자 데이터 직접 요청
        ajax_url = "https://info.nec.go.kr/electioninfo/electionInfo_report.xhtml"
        data_url = f"https://info.nec.go.kr/electioninfo/2026/cp/cpri{sg_typecode.zfill(2)}P.jsp"

        resp = requests.get(data_url, headers=HEADERS, timeout=15, params={
            "electionId": ELECTION_ID,
            "sdName": "경상남도",
            "wiwName": "" if sg_typecode in ["3","11"] else "김해시",
        })

        if resp.status_code == 200 and len(resp.text) > 500:
            items = parse_nec_html(resp.text, sg_typecode)
            if items:
                return jsonify({"success":True,"source":"info.nec.go.kr","count":len(items),"items":items})
    except Exception as e:
        pass

    # 방법2: info.nec.go.kr JSON API 시도
    try:
        json_url = "https://info.nec.go.kr/electioninfo/electionInfo_report.xhtml"
        resp = requests.post(json_url, headers={**HEADERS, "Content-Type":"application/x-www-form-urlencoded"},
            data={
                "electionId": ELECTION_ID,
                "requestURI": f"/electioninfo/2026/cp/cpri{sg_typecode.zfill(2)}P.jsp",
                "sdName": "경상남도",
                "wiwName": "" if sg_typecode in ["3","11"] else "김해시",
            }, timeout=15)
        if resp.status_code == 200 and "cddNm" in resp.text:
            return jsonify({"success":True,"source":"nec_post","raw_preview":resp.text[:500]})
    except:
        pass

    # 방법3: 공공데이터포털 최후 시도 (sgId 변형)
    ELECTION_API_KEY = "Yecdr4367t2bWw2nuYcwvf8JHmRIUCaB9F9dGPW1gkC3MWoWMsHJxdhMqGKRTKEnxJHYq2kViQIqfDTnfoL+tw=="
    BASE = "http://apis.data.go.kr/9760000/PofelcddInfoInqireService/getPoelpcddRegistSttusInfoInqire"
    for sg_id in ["20260603","20260000","2026"]:
        for ww in ["김해시", ""]:
            try:
                p = {
                    "serviceKey": ELECTION_API_KEY,
                    "sgId": sg_id, "sgTypecode": sg_typecode,
                    "sdName": "경상남도", "wiwName": ww,
                    "numOfRows": "100", "pageNo": "1",
                }
                r = requests.get(BASE, params=p, timeout=10)
                items, total, err = parse_resp(r)
                if not err and items:
                    return jsonify({"success":True,"source":f"data.go.kr/sgId={sg_id}","total":total,"count":len(items),"items":items})
            except:
                pass

    return jsonify({
        "success": False,
        "message": "공공데이터포털 API에 제9회 지방선거 데이터가 아직 미등재 상태입니다. info.nec.go.kr에서 직접 확인하세요.",
        "link": f"https://info.nec.go.kr/main/showIndexPage.xhtml?electionId={ELECTION_ID}"
    }), 404

def parse_nec_html(html, sg_typecode):
    """info.nec.go.kr HTML에서 후보자 정보 파싱"""
    items = []
    # 테이블 행 파싱
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        cells = [c for c in cells if c]
        if len(cells) >= 3 and not any(h in cells[0] for h in ['번호','선거구','성명']):
            item = {"raw_cells": cells}
            if len(cells) > 0: item["sggName"]    = cells[0]
            if len(cells) > 1: item["cddNm"]      = cells[1]
            if len(cells) > 2: item["polyNm"]     = cells[2]
            if len(cells) > 3: item["crmnlRcrdCn"] = cells[3]
            if len(cells) > 4: item["tpCn"]       = cells[4]
            if len(cells) > 5: item["mltrServCn"] = cells[5]
            items.append(item)
    return items

# ── 2. TourAPI 축제 ──────────────────────────────────
@app.route("/festivals")
def festivals():
    area    = request.args.get("area","")
    start   = request.args.get("start","20260101")
    end     = request.args.get("end","20261231")
    page    = request.args.get("page","1")
    rows    = request.args.get("rows","100")
    keyword = request.args.get("keyword","")
    params  = {
        "serviceKey": TOUR_API_KEY,
        "numOfRows": rows, "pageNo": page,
        "MobileOS": "ETC", "MobileApp": "FestivalApp",
        "arrange": "A", "eventStartDate": start, "_type": "json",
    }
    if area:    params["areaCode"] = area
    if keyword: params["keyword"]  = keyword
    try:
        resp = requests.get(TOUR_URL, params=params, timeout=15)
        resp.raise_for_status()
        items, total, err = parse_resp(resp)
        if err: return jsonify({"success":False,"error":err}), 500
        return jsonify({"success":True,"total":total,"count":len(items),"items":items})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}), 500

# ── 3. 문체부 문화예술공연 ───────────────────────────
@app.route("/culture")
def culture():
    page    = request.args.get("page","1")
    rows    = request.args.get("rows","50")
    keyword = request.args.get("keyword","")
    region  = request.args.get("region","")
    start   = request.args.get("start","")
    end     = request.args.get("end","")
    params  = {"serviceKey":CULTURE_API_KEY,"page":page,"rows":rows,"sortStdr":"1"}
    if keyword: params["keyword"]   = keyword
    if region:  params["sido"]      = region
    if start:   params["startDate"] = start
    if end:     params["endDate"]   = end
    try:
        resp = requests.get(CULTURE_URL, params=params, timeout=15)
        resp.raise_for_status()
        items, total, err = parse_resp(resp)
        if err: return jsonify({"success":False,"error":err}), 500
        return jsonify({"success":True,"total":total,"count":len(items),"items":items})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
