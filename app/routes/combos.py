from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import Combo, ComboItem, Product, Customer

combos_bp = Blueprint('combos', __name__)


def _require_customer():
    if not isinstance(current_user, Customer):
        abort(403)


@combos_bp.route('/')
@login_required
def list_combos():
    _require_customer()
    my = Combo.query.filter_by(customer_id=current_user.id).order_by(Combo.sort_order, Combo.id).all()
    templates = Combo.query.filter_by(is_template=True).order_by(Combo.sort_order, Combo.id).all()
    return render_template('combos/list.html', my=my, templates=templates)


@combos_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_combo():
    _require_customer()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('請輸入組合名稱', 'error')
            return redirect(url_for('combos.new_combo'))
        combo = Combo(
            customer_id=current_user.id,
            name=name,
            description=request.form.get('description', '').strip(),
            icon=request.form.get('icon', '🛒') or '🛒',
        )
        db.session.add(combo)
        db.session.flush()

        product_ids = request.form.getlist('product_id')
        quantities = request.form.getlist('quantity')
        for pid, qty in zip(product_ids, quantities):
            try:
                pid_int = int(pid)
                qty_int = max(1, int(qty))
            except ValueError:
                continue
            if not Product.query.get(pid_int):
                continue
            db.session.add(ComboItem(combo_id=combo.id, product_id=pid_int, quantity=qty_int))
        db.session.commit()
        flash('已建立組合', 'success')
        return redirect(url_for('combos.list_combos'))

    products = Product.query.filter_by(active=True).order_by(Product.sort_order).all()
    return render_template('combos/edit.html', combo=None, products=products)


@combos_bp.route('/<int:combo_id>/clone-template', methods=['POST'])
@login_required
def clone_template(combo_id):
    _require_customer()
    src = Combo.query.filter_by(id=combo_id, is_template=True).first_or_404()
    new = Combo(
        customer_id=current_user.id,
        name=src.name,
        description=src.description,
        icon=src.icon,
    )
    db.session.add(new)
    db.session.flush()
    for it in src.items:
        db.session.add(ComboItem(combo_id=new.id, product_id=it.product_id, quantity=it.quantity))
    db.session.commit()
    flash(f'已將「{src.name}」加入我的組合', 'success')
    return redirect(url_for('combos.list_combos'))


@combos_bp.route('/<int:combo_id>/delete', methods=['POST'])
@login_required
def delete_combo(combo_id):
    _require_customer()
    combo = Combo.query.filter_by(id=combo_id, customer_id=current_user.id).first_or_404()
    db.session.delete(combo)
    db.session.commit()
    flash('已刪除組合', 'success')
    return redirect(url_for('combos.list_combos'))
