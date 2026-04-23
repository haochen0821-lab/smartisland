from datetime import datetime, timedelta
import secrets
from app import db


RESERVATION_STATUS = [
    ('requested', '已請求'),
    ('ready', '已備好'),
    ('picked', '已取貨'),
    ('expired', '逾時釋放'),
    ('cancelled', '已取消'),
]


def _gen_pickup_code():
    # 4 碼數字取貨碼，避開易混 0
    return ''.join(secrets.choice('123456789') for _ in range(4))


def _default_expiry():
    return datetime.utcnow() + timedelta(hours=24)


class ProductReservation(db.Model):
    __tablename__ = 'product_reservations'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False, default=_gen_pickup_code)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    guest_name = db.Column(db.String(64), default='')
    guest_phone_last4 = db.Column(db.String(4), default='')
    quantity = db.Column(db.Integer, default=1)
    status = db.Column(db.String(16), default='requested')
    note = db.Column(db.String(256), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, default=_default_expiry)
    ready_at = db.Column(db.DateTime, nullable=True)
    picked_at = db.Column(db.DateTime, nullable=True)

    product = db.relationship('Product')
    customer = db.relationship('Customer')

    @property
    def status_label(self):
        return dict(RESERVATION_STATUS).get(self.status, self.status)

    @property
    def display_owner(self):
        if self.customer:
            return self.customer.full_name or self.customer.username
        if self.guest_name:
            tail = f'（手機末 4：{self.guest_phone_last4}）' if self.guest_phone_last4 else ''
            return f'{self.guest_name}{tail}（訪客）'
        return '匿名'

    @property
    def is_open(self):
        return self.status in ('requested', 'ready')

    @classmethod
    def auto_expire(cls):
        """把所有過期且未領的請求標為 expired。回傳被處理的筆數。"""
        now = datetime.utcnow()
        rows = cls.query.filter(
            cls.status.in_(['requested', 'ready']),
            cls.expires_at < now,
        ).all()
        for r in rows:
            r.status = 'expired'
        if rows:
            db.session.commit()
        return len(rows)
