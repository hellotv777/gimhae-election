from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)
CORS(app)

ELECTION_API_KEY = "Yecdr4367t2bWw2nuYcwvf8JHmRIUCaB9F9dGPW1gkC3MWoWMsHJxdhMqGKRTKEnxJHYq2kViQIqfDTnfoL+tw=="
TOUR_API_KEY     = "Yecdr4367t2bWw2nuYcwvf8JHmRIUCaB9F9dGPW1gkC3MWoWMsHJxdhMqGKRTKEnxJHYq2kViQIqfDTnfoL+tw=="
CULTURE_API_KEY  = "3834b2d5-0cd7-4783-8439-357d5483b276"

# 선관위 API - 정식후보자 / 예비후보자 두 엔드포인트 모두 시도
ELECTION_URL_CANDIDATE = "http://apis.data.go.kr/9760000/PofelcddInfoInqireService/getPoelpcddRegistSttusInfoInqire"
ELECTION_URL_PREVIEW   = "http://apis.data.go.kr/9760000/PofelcddInfoInqireService/getPrepareCddRegistSttusInfoInqire"
# data.nec.go.kr 자체 API
NEC_URL = "http://apis.data.go.kr/9760000/PofelcddInfoInqireService/getPoelpcddRegistSttusInfoInqire"

TOUR_URL    = "http://apis.data.go.kr/B551011/KorService1/searchFestival1"
CULTURE_URL = "http://apis.data.go.kr/B553077/api/open/musicsProduct/listMusicsProduct"

def xml_to_items(text):
    root = ET.fromstring(text)
    err = root.findtext(".//resultCode") or root.findtext(".//errCode") or ""
    if err and err not in ("00","0000","000","OK",""):
        msg = root.findtext(".//resultMsg") or root.findtext(".//errMsg") or "API오류"
        return [], 0, f"{err}:{msg}"
    items = []
    for item in root.iter("item"):
        obj = {c.tag:(c.text or "").strip() for c in item}
        if obj: items.append(obj)
    total = root.findtext(".//totalCount") or str(len(items))
    return items, int(total) if str(total).isdigit() else len(items), None

def json_to_items(data):
    hdr = data.get("response",{}).get("header",{})
    code = str(hdr.get("resultCode","00"))
    if code not in ("00","0000","000","OK",""):
        return [], 0, f'{code}:{hdr.get("resultMsg","")}'
    body  = data.get("response",{}).get("body",{})
    items = body.get("items") or {}
    if isinstance(items, dict): items = items.get("item",[])
    if isinstance(items, dict): items = [items]
    items = items or []
    return items, int(body.get("totalCount",len(items))), None

def parse_resp(resp):
    text = resp.text.strip()
    if text.startswith("<"):
        return xml_to_items(text)
    return json_to_items(resp.json())

@app.route("/")
def index():
    return jsonify({"status":"ok","endpoints":["/candidates","/festivals","/culture"]})

# ── 1. 선관위 후보자 (여러 방식 시도) ──────────────────
@app.route("/candidates")
def candidates():
    sg_typecode = request.args.get("sgTypecode","4")
    # 교육감은 sgTypecode=11, 도지사=3 (공식코드 재확인)
    # 김해시장=4, 도의원=5, 시의원=6, 도지사=3, 교육감=11
    wiwName = "" if sg_typecode in ["3","11"] else "김해시"
    sdName  = "경상남도"

    # sgId 후보군 — 2026 지방선거 가능한 ID 모두 시도
    sg_ids = ["20260603","20260000","20260001"]

    for sg_id in sg_ids:
        params = {
            "serviceKey": ELECTION_API_KEY,
            "sgId": sg_id,
            "sgTypecode": sg_typecode,
            "sdName": sdName,
            "wiwName": wiwName,
            "numOfRows": "100",
            "pageNo": "1",
        }
        try:
            resp = requests.get(ELECTION_URL_CANDIDATE, params=params, timeout=15)
            items, total, err = parse_resp(resp)
            if not err and len(items) > 0:
                return jsonify({"success":True,"sgId":sg_id,"total":total,"count":len(items),"items":items})
        except:
            pass

    # 방법2: wiwName 없이 전체 경남 조회
    try:
        params = {
            "serviceKey": ELECTION_API_KEY,
            "sgId": "20260603",
            "sgTypecode": sg_typecode,
            "sdName": sdName,
            "numOfRows": "100",
            "pageNo": "1",
        }
        resp = requests.get(ELECTION_URL_CANDIDATE, params=params, timeout=15)
        items, total, err = parse_resp(resp)
        if not err and len(items) > 0:
            # 김해시 필터링
            if wiwName:
                items = [i for i in items if "김해" in (i.get("wiwName","") or i.get("sggName",""))]
            return jsonify({"success":True,"sgId":"20260603","total":len(items),"count":len(items),"items":items,"note":"경남전체에서필터링"})
    except Exception as e:
        pass

    # 방법3: 원문 XML 반환으로 디버그
    try:
        params = {
            "serviceKey": ELECTION_API_KEY,
            "sgId": "20260603",
            "sgTypecode": sg_typecode,
            "sdName": sdName,
            "numOfRows": "10",
            "pageNo": "1",
        }
        resp = requests.get(ELECTION_URL_CANDIDATE, params=params, timeout=15)
        return jsonify({"success":False,"debug":True,"raw":resp.text[:1000],"status":resp.status_code})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}), 500

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
        "arrange": "A",
        "eventStartDate": start,
        "_type": "json",
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
