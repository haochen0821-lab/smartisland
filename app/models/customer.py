from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


CUSTOMER_ROLES = [
    ('innkeeper', '民宿/餐飲業者'),
    ('resident', '在地居民'),
    ('tourist', '遊客'),
    ('other', '其他'),
]


class Customer(UserMixin, db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(128), default='')
    phone = db.Column(db.String(32), default='')
    full_name = db.Column(db.String(64), default='')
    role = db.Column(db.String(32), default='resident', nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    combos = db.relationship('Combo', backref='customer', cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='customer', cascade='all, delete-orphan')

    def get_id(self):
        return f'customer:{self.id}'

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def role_label(self):
        return dict(CUSTOMER_ROLES).get(self.role, self.role)
