"""離島實時情報：南竿機場 METAR、馬祖海面預報、台灣北部海面預報。

策略：
- 南竿機場 (RCFG) METAR：aviationweather.gov 免費 API（無需 key）
- 海面預報：中央氣象署 OpenData（需要 CWA_API_KEY，缺 key 時 fallback 為「請點外連」）
- matsu.idv.tw：不 scrape，只給外連連結（社群站結構易變）

所有結果 cache 30 分鐘到 SiteSetting，避免每次請求都打外部。
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

EXTERNAL_LINKS = [
    {
        'name': '馬祖鄉土資訊網',
        'url': 'https://www.matsu.idv.tw/',
        'desc': '南竿機場能見度 / 雲高 / 地方氣象社群觀測（網友回報資訊）',
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
        'name': 'CWA 機場觀測',
        'url': 'https://www.cwa.gov.tw/V8/C/M/Airport.html',
        'desc': '南竿機場 RCFG 即時氣象觀測',
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


# ---------------- METAR ----------------
def _parse_metar(text):
    if not text or text.startswith('('):
        return {}
    parts = text.split()
    out = {'wind': None, 'visibility': None, 'cloud': [], 'temp': None}
    for p in parts[2:]:
        if re.fullmatch(r'\d{3,5}(?:G\d{2,3})?KT|VRB\d{2}KT', p) and out['wind'] is None:
            out['wind'] = p
        elif re.fullmatch(r'\d{4}', p) and out['visibility'] is None:
            out['visibility'] = p
        elif re.fullmatch(r'(SKC|FEW|SCT|BKN|OVC)\d{3}(CB|TCU)?', p):
            out['cloud'].append(p)
        elif re.fullmatch(r'M?\d{2}/M?\d{2}', p) and out['temp'] is None:
            out['temp'] = p
    return out


def _humanize_metar(raw, parsed):
    bits = []
    if parsed.get('visibility'):
        v = int(parsed['visibility'])
        bits.append(f'能見度 {v} m' if v < 9999 else '能見度 ≥10 km')
    if parsed.get('cloud'):
        cloud_zh = []
        cover_map = {'SKC': '晴空', 'FEW': '少雲', 'SCT': '疏雲', 'BKN': '多雲', 'OVC': '滿天雲'}
        for c in parsed['cloud'][:3]:
            cover = cover_map.get(c[:3], c[:3])
            try:
                feet = int(c[3:6]) * 100
                cloud_zh.append(f'{cover} {feet} ft')
            except ValueError:
                cloud_zh.append(c)
        bits.append('雲：' + '、'.join(cloud_zh))
    if parsed.get('wind'):
        w = parsed['wind']
        if w.startswith('VRB'):
            bits.append(f'風向不定 {w[3:5]} kt')
        else:
            bits.append(f'風 {w[:3]}° {w[3:5]} kt')
    if parsed.get('temp'):
        t = parsed['temp'].replace('M', '-')
        bits.append(f'溫/露 {t}°C')
    return ' ｜ '.join(bits) if bits else '無資料'


METAR_STATIONS = [
    ('RCMQ', '馬公機場（同為外島，最接近馬祖環境）'),
    ('RCSS', '松山機場（北海岸，影響船班的對岸天候）'),
]


def _fetch_one_metar(icao):
    """抓單一機場 raw METAR 字串；失敗回空字串。"""
    try:
        r = requests.get('https://aviationweather.gov/api/data/metar',
                         params={'ids': icao, 'format': 'raw'}, timeout=8)
        if r.status_code == 204:
            return ''
        if not r.ok:
            return ''
        return (r.text or '').strip()
    except Exception:
        return ''


def fetch_metar(force=False):
    """抓 RCMQ + RCSS METAR；南竿 RCFG 不發 METAR，於說明欄揭示。"""
    if not force:
        c = _cache_get('metar_panel')
        if c:
            return c
    stations_data = []
    for icao, desc in METAR_STATIONS:
        raw = _fetch_one_metar(icao)
        parsed = _parse_metar(raw) if raw else {}
        stations_data.append({
            'icao': icao, 'desc': desc,
            'raw': raw or '(暫無資料)',
            'human': _humanize_metar(raw, parsed) if raw else '暫無資料',
            'has_data': bool(raw),
        })
    payload = {
        'note': '南竿機場 (RCFG) 不發布公開 METAR；下方為最接近的兩座機場，可參考海象與雲層走向。完整觀測請點 CWA 連結。',
        'stations': stations_data,
    }
    return _cache_set('metar_panel', payload)


# ---------------- 海面預報 ----------------
def _summarize_marine_response(data, area_name):
    """CWA 海面 API 回傳結構：records.location[].weatherElement[].time[]
    抽出最近一個時段的主要欄位。"""
    try:
        records = data.get('records') or {}
        loc_root = records.get('location') or records.get('locations') or []
        if not loc_root:
            return {'error': '回傳格式無 location'}
        # 不同資料集 schema 略有差，盡量包進來
        if isinstance(loc_root, dict):
            loc_root = [loc_root]
        loc = next((l for l in loc_root if l.get('locationName') == area_name or l.get('LocationName') == area_name), loc_root[0])
        # 處理巢狀
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
        payload = {'area': area_name, 'error': 'no_api_key',
                   'note': '請於 .env 設 CWA_API_KEY 並重啟容器'}
        return _cache_set(cache_key, payload)
    try:
        r = requests.get(f'{CWA_API}/{dataset}',
                         params={'Authorization': api_key, 'locationName': area_name},
                         timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        payload = {'area': area_name, 'error': str(e)}
        return _cache_set(cache_key, payload)
    summary = _summarize_marine_response(data, area_name)
    payload = {'area': area_name, **summary}
    return _cache_set(cache_key, payload)


def fetch_all(force=False):
    return {
        'metar': fetch_metar(force=force),
        'marine_matsu': fetch_marine('馬祖海面', force=force),
        'marine_north': fetch_marine('臺灣北部海面', force=force),
        'links': EXTERNAL_LINKS,
        'fetched_at': datetime.utcnow(),
    }
