"""中央氣象署開放資料 API client。

使用「鄉鎮天氣預報-連江縣未來 1 週天氣預報」資料集 F-D0047-079。
若沒有設定 CWA_API_KEY，refresh_weather() 會回傳 None；呼叫端應該 fallback
到資料庫最後一筆 / 模擬資料，而不是讓服務掛掉。
"""
import os
import json
from datetime import datetime
import requests

API_BASE = 'https://opendata.cwa.gov.tw/api/v1/rest/datastore'
LIENCHIANG_DATASET = 'F-D0047-079'   # 連江縣 3 小時/週 預報
DEFAULT_LOCATION = '南竿鄉'


def _wind_scale_to_beaufort(scale_str):
    """中央氣象署回傳的「風力級數（蒲福風級）」字串轉整數，無法解析時 0"""
    try:
        return int(str(scale_str).strip())
    except Exception:
        return 0


def fetch_weather(location=DEFAULT_LOCATION, api_key=None):
    """呼叫 CWA API 拉取單一鄉鎮的最近預報。
    回傳 dict 或 None（金鑰缺失 / API 失敗）。
    """
    api_key = api_key or os.getenv('CWA_API_KEY', '').strip()
    if not api_key:
        return None

    url = f'{API_BASE}/{LIENCHIANG_DATASET}'
    params = {
        'Authorization': api_key,
        'LocationName': location,
        'ElementName': 'Wx,PoP12h,MinT,MaxT,WindSpeed,WS,T,UVI,WeatherDescription',
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {'error': str(e)}

    return _parse_first_window(data, location)


def _pick_element(elements, names):
    """從 WeatherElement 陣列裡找出第一個符合名字的 element。"""
    if isinstance(names, str):
        names = [names]
    for el in elements:
        if el.get('ElementName') in names:
            return el
    return None


def _first_value(element):
    if not element:
        return None
    times = element.get('Time', [])
    if not times:
        return None
    first = times[0]
    ev = first.get('ElementValue', [])
    if isinstance(ev, list) and ev:
        return ev[0]
    return None


def _parse_first_window(data, location_name):
    try:
        loc_root = data['records']['Locations'][0]
        loc = next((l for l in loc_root['Location'] if l.get('LocationName') == location_name),
                   loc_root['Location'][0])
        elements = loc.get('WeatherElement', [])
    except (KeyError, IndexError, TypeError):
        return {'error': '回傳格式異常'}

    wx = _first_value(_pick_element(elements, ['天氣現象', 'Wx']))
    desc = _first_value(_pick_element(elements, ['天氣預報綜合描述', 'WeatherDescription']))
    pop = _first_value(_pick_element(elements, ['12小時降雨機率', 'PoP12h']))
    min_t = _first_value(_pick_element(elements, ['最低溫度', 'MinT']))
    max_t = _first_value(_pick_element(elements, ['最高溫度', 'MaxT']))
    wind = _first_value(_pick_element(elements, ['風速', 'WindSpeed', 'WS']))

    def _to_int(v, default=0):
        try:
            return int(float(v))
        except Exception:
            return default

    return {
        'observed_at': datetime.utcnow().isoformat(),
        'weather_desc': (wx or {}).get('Weather') if isinstance(wx, dict) else (desc or {}).get('WeatherDescription', '') if isinstance(desc, dict) else '',
        'rain_prob': _to_int((pop or {}).get('ProbabilityOfPrecipitation') if isinstance(pop, dict) else 0),
        'min_temp': _to_int((min_t or {}).get('MinTemperature') if isinstance(min_t, dict) else 0),
        'max_temp': _to_int((max_t or {}).get('MaxTemperature') if isinstance(max_t, dict) else 0),
        'wind_level': _wind_scale_to_beaufort((wind or {}).get('BeaufortScale') if isinstance(wind, dict) else 0),
        'location': location_name,
        'source': 'cwa',
    }


def refresh_weather_to_db(db, WeatherSnapshot, location=DEFAULT_LOCATION, api_key=None):
    """拉取並寫入一筆 WeatherSnapshot；失敗時回傳 None 不破壞 DB。"""
    payload = fetch_weather(location=location, api_key=api_key)
    if payload is None:
        return None
    if payload.get('error'):
        return payload

    snap = WeatherSnapshot(
        observed_at=datetime.utcnow(),
        weather_desc=payload.get('weather_desc') or '',
        min_temp=payload.get('min_temp') or 0,
        max_temp=payload.get('max_temp') or 0,
        rain_prob=payload.get('rain_prob') or 0,
        wind_level=payload.get('wind_level') or 0,
        wave_height=0.0,
        source='cwa',
        raw=json.dumps(payload, ensure_ascii=False)[:4000],
    )
    db.session.add(snap)
    db.session.commit()
    return payload
