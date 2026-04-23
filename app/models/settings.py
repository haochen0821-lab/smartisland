from datetime import datetime
from app import db


class SiteSetting(db.Model):
    __tablename__ = 'site_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.Text, default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=''):
        row = SiteSetting.query.filter_by(key=key).first()
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = SiteSetting.query.filter_by(key=key).first()
        if not row:
            row = SiteSetting(key=key, value=value)
            db.session.add(row)
        else:
            row.value = value
        return row
