from datetime import datetime
from app import db


ORDER_STATUS = [
    ('pending', '待備貨'),
    ('ready', '已備齊·待取'),
    ('picked', '已取貨'),
    ('cancelled', '已取消'),
]


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(16), unique=True, nullable=False)   # A0421-XX
    qr_token = db.Column(db.String(64), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    combo_id = db.Column(db.Integer, db.ForeignKey('combos.id'), nullable=True)
    status = db.Column(db.String(16), default='pending')
    total_amount = db.Column(db.Integer, default=0)
    note = db.Column(db.String(256), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    picked_at = db.Column(db.DateTime, nullable=True)

    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')

    @property
    def status_label(self):
        return dict(ORDER_STATUS).get(self.status, self.status)

    @property
    def item_count(self):
        return sum(i.quantity for i in self.items)


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product_name = db.Column(db.String(128), default='')   # snapshot
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Integer, default=0)

    product = db.relationship('Product')
