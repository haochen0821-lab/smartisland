from datetime import datetime
from app import db


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    icon = db.Column(db.String(8), default='')        # emoji
    sort_order = db.Column(db.Integer, default=0)

    products = db.relationship('Product', backref='category', cascade='all, delete-orphan')


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    name = db.Column(db.String(128), nullable=False)
    sku = db.Column(db.String(32), unique=True, nullable=False)
    price = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(16), default='個')
    icon = db.Column(db.String(8), default='')

    stock = db.Column(db.Integer, default=0)
    safety_stock = db.Column(db.Integer, default=10)

    # 是否依賴船班補給（雞蛋/鮮奶/葉菜=True；衛生紙/泡麵=可儲存=False）
    is_ferry_dependent = db.Column(db.Boolean, default=True)

    sort_order = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def signal(self, ferry_today_ok: bool, weather_alert: bool):
        """回傳 ('green'|'yellow'|'red', label)
        green  = 庫存 > safety_stock
        yellow = 庫存 ≤ safety_stock 但今日有船班可補（且天氣 OK）
        red    = 庫存 ≤ safety_stock 且（今日無船班 / 天氣警示影響補給）
        """
        if self.stock > self.safety_stock:
            return ('green', '充足')
        if self.is_ferry_dependent and weather_alert:
            return ('red', '天候警示·缺貨風險')
        if ferry_today_ok:
            return ('yellow', '將補')
        return ('red', '缺貨')
