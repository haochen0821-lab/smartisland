from datetime import datetime
from app import db


class Combo(db.Model):
    """常買組合：可以是顧客自建，也可以是店家提供的範本（is_template）。"""
    __tablename__ = 'combos'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(256), default='')
    icon = db.Column(db.String(8), default='🛒')
    is_template = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('ComboItem', backref='combo', cascade='all, delete-orphan')

    @property
    def total_price(self):
        return sum(i.product.price * i.quantity for i in self.items if i.product)


class ComboItem(db.Model):
    __tablename__ = 'combo_items'

    id = db.Column(db.Integer, primary_key=True)
    combo_id = db.Column(db.Integer, db.ForeignKey('combos.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    product = db.relationship('Product')
