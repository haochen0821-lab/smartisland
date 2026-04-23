"""燈號計算：把「庫存 × 今日船班 × 天氣」濃縮成一個顏色 / 文案。"""
from datetime import date
from app.models import FerrySchedule, WeatherSnapshot


def today_ferry_status(today=None):
    """回傳今日船班是否「會帶來補給」(bool, 有效船班清單, 延誤/取消備註)"""
    today = today or date.today()
    rows = FerrySchedule.query.filter_by(schedule_date=today).all()
    arrived_or_coming = [r for r in rows if r.status in ('arrived', 'scheduled', 'delayed')
                         and r.cargo_pct > 0]
    has_supply = any(r.status == 'arrived' for r in rows) or any(
        r.status in ('scheduled', 'delayed') and r.cargo_pct >= 30 for r in rows
    )
    return has_supply, rows


def latest_weather():
    return WeatherSnapshot.query.order_by(WeatherSnapshot.observed_at.desc()).first()


def compute_context(today=None):
    """產生燈號計算需要的共用 context（避免每個商品重複查 DB）。"""
    has_supply, ferries = today_ferry_status(today)
    weather = latest_weather()
    weather_alert = bool(weather and weather.is_alert)
    return {
        'ferry_today_ok': has_supply,
        'weather_alert': weather_alert,
        'ferries': ferries,
        'weather': weather,
    }


def signal_summary(products, ctx=None):
    """回傳 {green: n, yellow: n, red: n}"""
    ctx = ctx or compute_context()
    counts = {'green': 0, 'yellow': 0, 'red': 0}
    for p in products:
        color, _ = p.signal(ctx['ferry_today_ok'], ctx['weather_alert'])
        counts[color] = counts.get(color, 0) + 1
    return counts
