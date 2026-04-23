from datetime import datetime, date
from app import db


FERRY_STATUS = [
    ('scheduled', '預計'),
    ('arrived', '已靠港'),
    ('delayed', '延誤'),
    ('cancelled', '取消'),
]


class FerrySchedule(db.Model):
    __tablename__ = 'ferry_schedules'

    id = db.Column(db.Integer, primary_key=True)
    schedule_date = db.Column(db.Date, default=date.today, index=True)
    ferry_name = db.Column(db.String(64), nullable=False)   # 台馬之星 / 合富快輪 / 小三通貨輪
    port = db.Column(db.String(32), default='福澳港')
    scheduled_time = db.Column(db.String(8), default='')     # '06:40'
    actual_time = db.Column(db.String(8), default='')
    status = db.Column(db.String(16), default='scheduled')
    cargo_pct = db.Column(db.Integer, default=100)           # 載貨率（影響補給）
    note = db.Column(db.String(256), default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def status_label(self):
        return dict(FERRY_STATUS).get(self.status, self.status)
