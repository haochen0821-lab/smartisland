from app import db


class StoreInfo(db.Model):
    """單列表：本系統服務的店面資訊。"""
    __tablename__ = 'store_info'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    location = db.Column(db.String(64), default='')           # 南竿介壽
    address = db.Column(db.String(256), default='')
    phone = db.Column(db.String(32), default='')
    port_name = db.Column(db.String(64), default='福澳港')
    cwa_location = db.Column(db.String(32), default='南竿鄉')   # 中央氣象署 locationName
    open_hours = db.Column(db.String(64), default='07:00-22:00')
    intro = db.Column(db.Text, default='')

    @classmethod
    def current(cls):
        return cls.query.first()
