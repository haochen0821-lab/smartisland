"""商品預留：點燈號 → 跳數量 → 送預留請求。
- 已登入顧客：直接綁定
- 訪客：姓名 + 手機末 4 碼
- 24 小時自動釋放（每次列出時 sweep 一次）
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, abort
from flask_login import current_user
from app import db
from app.models import Product, Customer, ProductReservation

reservations_bp = Blueprint('reservations', __name__)


def _check_qty(p, qty):
    if qty < 1:
        return '數量至少 1'
    if qty > 999:
        return '數量過大'
    return None


@reservations_bp.route('/<int:product_id>', methods=['POST'])
def create(product_id):
    """來自首頁 modal 的 AJAX POST，回傳 JSON。"""
    p = Product.query.get_or_404(product_id)
    try:
        qty = int(request.form.get('quantity') or request.json.get('quantity', 0) if request.is_json else request.form.get('quantity', 0))
    except Exception:
        qty = 0
    err = _check_qty(p, qty)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    note = (request.form.get('note') or '').strip()
    res = ProductReservation(product_id=p.id, quantity=qty, note=note[:256])

    if isinstance(current_user, Customer):
        res.customer_id = current_user.id
    else:
        guest_name = (request.form.get('guest_name') or '').strip()
        phone_last4 = (request.form.get('guest_phone_last4') or '').strip()[-4:]
        if not guest_name or not phone_last4.isdigit() or len(phone_last4) != 4:
            return jsonify({'ok': False, 'error': '訪客需要姓名與手機末 4 碼數字'}), 400
        res.guest_name = guest_name[:64]
        res.guest_phone_last4 = phone_last4

    db.session.add(res)
    db.session.commit()
    return jsonify({
        'ok': True,
        'code': res.code,
        'product_name': p.name,
        'quantity': res.quantity,
        'expires_at': res.expires_at.strftime('%Y-%m-%d %H:%M'),
        'lookup_url': url_for('reservations.lookup', code=res.code),
    })


@reservations_bp.route('/lookup', methods=['GET', 'POST'])
def lookup():
    """訪客查詢自己的預留：取貨碼 + 手機末 4 碼。"""
    code_q = request.values.get('code', '').strip()
    phone_q = request.values.get('phone', '').strip()
    res = None
    if code_q:
        ProductReservation.auto_expire()
        q = ProductReservation.query.filter_by(code=code_q)
        if phone_q:
            q = q.filter_by(guest_phone_last4=phone_q[-4:])
        res = q.first()
    return render_template('reservations/lookup.html', res=res, code_q=code_q)


@reservations_bp.route('/mine')
def mine():
    """已登入顧客的預留清單。"""
    if not isinstance(current_user, Customer):
        flash('請先登入會員', 'error')
        return redirect(url_for('auth.login'))
    ProductReservation.auto_expire()
    rows = ProductReservation.query.filter_by(customer_id=current_user.id) \
        .order_by(ProductReservation.created_at.desc()).all()
    return render_template('reservations/mine.html', rows=rows)


@reservations_bp.route('/<int:res_id>/cancel', methods=['POST'])
def cancel(res_id):
    res = ProductReservation.query.get_or_404(res_id)
    if isinstance(current_user, Customer):
        if res.customer_id != current_user.id:
            abort(403)
    else:
        # 訪客需要傳 phone 驗證
        phone = (request.form.get('phone') or '')[-4:]
        if not res.guest_phone_last4 or phone != res.guest_phone_last4:
            abort(403)
    if res.status in ('requested', 'ready'):
        res.status = 'cancelled'
        db.session.commit()
        flash('已取消預留', 'success')
    return redirect(request.referrer or url_for('main.home'))
