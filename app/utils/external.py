"""離島實時情報：馬祖（連江縣）4 個鄉鎮預報 + 海面預報 + 外部連結。

策略：
- 馬祖 4 鄉鎮（南竿 / 北竿 / 東引 / 莒光）預報：CWA OpenData F-D0047-079
- 馬祖海面 / 台灣北部海面：CWA OpenData W-C0033-002
- 馬祖機場（南竿 RCFG / 北竿 RCMT）目前不對外公開 METAR；於頁面提供 CWA 機場觀測連結

所有 API 結果 cache 30 分鐘到 SiteSetting，避免每次請求都打外部。
未設 CWA_API_KEY 時 graceful fallback（顯示「請設定 API Key」+ 外連）。
"""
import os
import json
import re
import requests
from datetime import datetime, timedelta
from app import db
from app.models.settings import SiteSetting

CACHE_TTL_MIN = 30
CWA_API = 'https://opendata.cwa.gov.tw/api/v1/rest/datastore'

# 馬祖（連江縣）4 鄉鎮，依民宿主人的補給優先序排
MATSU_TOWNSHIPS = ['南竿鄉', '北竿鄉', '東引鄉', '莒光鄉']

EXTERNAL_LINKS = [
    {
        'name': '馬祖資訊網',
        'url': 'https://www.matsu.idv.tw/',
        'desc': '馬祖在地社群 / 即時氣象 / 船班討論',
        'icon': '🏝️',
    },
    {
        'name': 'CWA 馬祖海面預報',
        'url': 'https://www.cwa.gov.tw/V8/C/M/NSea.html',
        'desc': '中央氣象署「馬祖海面」官方預報頁',
        'icon': '🌊',
    },
    {
        'name': 'CWA 台灣北部海面預報',
        'url': 'https://www.cwa.gov.tw/V8/C/M/FSea.html',
        'desc': '影響台馬之星 / 合富快輪航行的主海域',
        'icon': '⚓',
    },
    {
        'name': 'CWA 機場觀測（南竿 / 北竿）',
        'url': 'https://www.cwa.gov.tw/V8/C/M/Airport.html',
        'desc': '南竿 RCFG / 北竿 RCMT 即時觀測（馬祖兩座機場不發布公開 METAR）',
        'icon': '✈️',
    },
]


# ---------------- cache helpers ----------------
def _cache_get(key):
    raw = SiteSetting.get(f'ext_cache_{key}', '')
    if not raw:
        return None
    try:
        d = json.loads(raw)
        ts = datetime.fromisoformat(d['_at'])
        if datetime.utcnow() - ts > timedelta(minutes=CACHE_TTL_MIN):
            return None
        return d
    except Exception:
        return None


def _cache_set(key, payload):
    payload = dict(payload)
    payload['_at'] = datetime.utcnow().isoformat()
    SiteSetting.set(f'ext_cache_{key}', json.dumps(payload, ensure_ascii=False)[:8000])
    db.session.commit()
    return payload


# ---------------- 鄉鎮預報 ----------------
def _first_value(element):
    times = element.get('Time') or element.get('time') or []
    if not times:
        return ''
    t = times[0]
    ev = t.get('ElementValue') or t.get('elementValue') or []
    if isinstance(ev, list) and ev and isinstance(ev[0], dict):
        # 取第一個值
        for k, v in ev[0].items():
            return str(v)
    if isinstance(ev, dict):
        for k, v in ev.items():
            return str(v)
    return ''


def fetch_township(name, force=False):
    """抓馬祖單一鄉鎮的最近一個時段預報。"""
    cache_key = f'twn_{name}'
    if not force:
        c = _cache_get(cache_key)
        if c:
            return c
    api_key = os.getenv('CWA_API_KEY', '').strip()
    if not api_key:
        return _cache_set(cache_key, {'name': name, 'error': 'no_api_key'})
    try:
        r = requests.get(
            f'{CWA_API}/F-D0047-079',
            params={
                'Authorization': api_key,
                'LocationName': name,
                'ElementName': 'Wx,PoP12h,MinT,MaxT,WeatherDescription,WindSpeed',
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        loc_root = data['records']['Locations'][0]
        loc = next(
            (l for l in loc_root['Location'] if l.get('LocationName') == name),
            loc_root['Location'][0],
        )
        elements = {el.get('ElementName'): el for el in loc.get('WeatherElement', [])}
        wx = _first_value(elements.get('天氣現象', {})) if elements.get('天氣現象') else ''
        desc = _first_value(elements.get('天氣預報綜合描述', {})) if elements.get('天氣預報綜合描述') else ''
        pop = _first_value(elements.get('12小時降雨機率', {})) if elements.get('12小時降雨機率') else ''
        min_t = _first_value(elements.get('最低溫度', {})) if elements.get('最低溫度') else ''
        max_t = _first_value(elements.get('最高溫度', {})) if elements.get('最高溫度') else ''
        wind = _first_value(elements.get('風速', {})) if elements.get('風速') else ''
        return _cache_set(cache_key, {
            'name': name,
            'weather': wx or desc[:40],
            'desc': desc,
            'rain_prob': pop,
            'min_temp': min_t,
            'max_temp': max_t,
            'wind': wind,
        })
    except Exception as e:
        return _cache_set(cache_key, {'name': name, 'error': str(e)})


def fetch_matsu_townships(force=False):
    return [fetch_township(t, force=force) for t in MATSU_TOWNSHIPS]


# ---------------- 海面預報 ----------------
def _summarize_marine_response(data, area_name):
    try:
        records = data.get('records') or {}
        loc_root = records.get('location') or records.get('locations') or []
        if not loc_root:
            return {'error': '回傳格式無 location'}
        if isinstance(loc_root, dict):
            loc_root = [loc_root]
        loc = next(
            (l for l in loc_root if l.get('locationName') == area_name or l.get('LocationName') == area_name),
            loc_root[0],
        )
        if 'location' in loc and isinstance(loc['location'], list) and loc['location']:
            loc = loc['location'][0]
        elements = loc.get('weatherElement') or loc.get('WeatherElement') or []
        out = []
        for el in elements[:8]:
            name = el.get('elementName') or el.get('ElementName')
            times = el.get('time') or el.get('Time') or []
            if not times:
                continue
            t = times[0]
            val = ''
            if isinstance(t.get('parameter'), dict):
                val = t['parameter'].get('parameterName', '')
            elif t.get('elementValue'):
                ev = t['elementValue']
                if isinstance(ev, list) and ev:
                    val = list(ev[0].values())[0] if isinstance(ev[0], dict) else str(ev[0])
                elif isinstance(ev, dict):
                    val = list(ev.values())[0]
                else:
                    val = str(ev)
            if name and val:
                out.append({'name': str(name), 'value': str(val)[:80]})
        return {'items': out}
    except Exception as e:
        return {'error': f'parse: {e}'}


def fetch_marine(area_name, dataset='W-C0033-002', force=False):
    cache_key = f'marine_{re.sub(r"[^A-Za-z0-9]", "_", area_name)}'
    if not force:
        c = _cache_get(cache_key)
        if c:
            return c
    api_key = os.getenv('CWA_API_KEY', '').strip()
    if not api_key:
        return _cache_set(cache_key, {
            'area': area_name, 'error': 'no_api_key',
            'note': '請於 .env 設 CWA_API_KEY 並重啟容器',
        })
    try:
        r = requests.get(
            f'{CWA_API}/{dataset}',
            params={'Authorization': api_key, 'locationName': area_name},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return _cache_set(cache_key, {'area': area_name, 'error': str(e)})
    summary = _summarize_marine_response(data, area_name)
    return _cache_set(cache_key, {'area': area_name, **summary})


def fetch_all(force=False):
    return {
        'townships': fetch_matsu_townships(force=force),
        'marine_matsu': fetch_marine('馬祖海面', force=force),
        'marine_north': fetch_marine('臺灣北部海面', force=force),
        'links': EXTERNAL_LINKS,
        'fetched_at': datetime.utcnow(),
    }
