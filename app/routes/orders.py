import secrets
from io import BytesIO
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
from flask_login import login_required, current_user
import qrcode
from app import db
from app.models import Order, OrderItem, Combo, Product, Customer

orders_bp = Blueprint('orders', __name__)


def _require_customer():
    if not isinstance(current_user, Customer):
        abort(403)


def _new_order_no():
    today = date.today()
    seq = Order.query.filter(
        db.func.date(Order.created_at) == today
    ).count() + 1
    return f'{today.strftime("%m%d")}-{seq:03d}'


@orders_bp.route('/place/<int:combo_id>', methods=['POST'])
@login_required
def place_from_combo(combo_id):
    _require_customer()
    combo = Combo.query.get_or_404(combo_id)
    if combo.customer_id and combo.customer_id != current_user.id:
        abort(403)
    if not combo.items:
        flash('此組合尚未加入商品', 'error')
        return redirect(url_for('combos.list_combos'))

    order = Order(
        order_no=_new_order_no(),
        qr_token=secrets.token_urlsafe(16),
        customer_id=current_user.id,
        combo_id=combo.id,
        status='pending',
        total_amount=0,
    )
    db.session.add(order)
    db.session.flush()

    total = 0
    for it in combo.items:
        if not it.product:
            continue
        line = OrderItem(
            order_id=order.id,
            product_id=it.product_id,
            product_name=it.product.name,
            quantity=it.quantity,
            unit_price=it.product.price,
        )
        db.session.add(line)
        total += it.product.price * it.quantity
    order.total_amount = total
    db.session.commit()

    flash(f'已下單 #{order.order_no}，請至店內出示 QR Code 取貨', 'success')
    return redirect(url_for('orders.detail', order_no=order.order_no))


@orders_bp.route('/')
@login_required
def list_orders():
    _require_customer()
    rows = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders/list.html', orders=rows)


@orders_bp.route('/<order_no>')
@login_required
def detail(order_no):
    order = Order.query.filter_by(order_no=order_no).first_or_404()
    # 顧客只能看自己的；店家管理員另走 admin
    if isinstance(current_user, Customer) and order.customer_id != current_user.id:
        abort(403)
    return render_template('orders/detail.html', order=order)


@orders_bp.route('/<order_no>/qr.png')
@login_required
def qr(order_no):
    order = Order.query.filter_by(order_no=order_no).first_or_404()
    if isinstance(current_user, Customer) and order.customer_id != current_user.id:
        abort(403)
    img = qrcode.make(f'SIH:{order.order_no}:{order.qr_token}')
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')
