"""對外 API：給看板自動更新、未來給電子紙標籤用。"""
import os
from flask import Blueprint, jsonify, current_app
from app import db
from app.models import WeatherSnapshot
from app.utils.cwa import refresh_weather_to_db
from app.utils.signal import compute_context

api_bp = Blueprint('api', __name__)


@api_bp.route('/refresh-weather')
def refresh_weather():
    """手動觸發拉取最新氣象。看板/admin 都可以呼叫。"""
    payload = refresh_weather_to_db(db, WeatherSnapshot, api_key=os.getenv('CWA_API_KEY'))
    if payload is None:
        return jsonify({'ok': False, 'reason': 'no_api_key'}), 200
    if isinstance(payload, dict) and payload.get('error'):
        return jsonify({'ok': False, 'reason': payload['error']}), 200
    return jsonify({'ok': True, 'data': payload}), 200


@api_bp.route('/signals')
def signals():
    ctx = compute_context()
    weather = ctx['weather']
    return jsonify({
        'ferry_today_ok': ctx['ferry_today_ok'],
        'weather_alert': ctx['weather_alert'],
        'weather': {
            'desc': weather.weather_desc if weather else '',
            'wind_level': weather.wind_level if weather else 0,
            'wave_height': weather.wave_height if weather else 0,
            'rain_prob': weather.rain_prob if weather else 0,
            'min_temp': weather.min_temp if weather else 0,
            'max_temp': weather.max_temp if weather else 0,
            'source': weather.source if weather else 'none',
        },
    })
