from datetime import datetime
from app import db


class WeatherSnapshot(db.Model):
    __tablename__ = 'weather_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    observed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    weather_desc = db.Column(db.String(64), default='')      # 多雲短暫陣雨
    min_temp = db.Column(db.Integer, default=0)
    max_temp = db.Column(db.Integer, default=0)
    rain_prob = db.Column(db.Integer, default=0)             # 0-100
    wind_level = db.Column(db.Integer, default=0)            # 蒲福風級 0-12
    wave_height = db.Column(db.Float, default=0.0)           # 公尺
    source = db.Column(db.String(16), default='cwa')         # cwa / manual / fallback
    raw = db.Column(db.Text, default='')                     # 原始 JSON 摘要

    @property
    def is_alert(self):
        """是否影響船班補給的天候警示"""
        return self.wind_level >= 7 or self.wave_height >= 3.0

    @property
    def alert_reason(self):
        if self.wind_level >= 8:
            return f'風力 {self.wind_level} 級'
        if self.wave_height >= 3.0:
            return f'浪高 {self.wave_height:.1f} m'
        if self.wind_level >= 7:
            return f'風力 {self.wind_level} 級'
        return ''
