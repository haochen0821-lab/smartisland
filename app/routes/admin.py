"""店家後台：登入、儀表板、商品/庫存、船班、訂單、顧客、店家、設定（含 PWA icon）。"""
import os
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, current_app, abort,
)
from flask_login import login_required, current_user, login_user, logout_user
from app import db
from app.models import (
    AdminUser, Customer, Product, Category, FerrySchedule, WeatherSnapshot,
    Combo, ComboItem, Order, OrderItem, SiteSetting, StoreInfo,
)
from app.models.ferry import FERRY_STATUS
from app.models.order import ORDER_STATUS
from app.utils.icons import validate_and_save, IconError
from app.utils.signal import compute_context, signal_summary
from app.utils.cwa import refresh_weather_to_db

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, AdminUser):
            flash('請先以管理員身分登入', 'error')
            return redirect(url_for('admin.login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


# -------------------- 登入 --------------------
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = AdminUser.query.filter_by(username=request.form.get('username', '').strip()).first()
        if u and u.check_password(request.form.get('password', '')) and u.is_active:
            login_user(u, remember=True)
            return redirect(request.args.get('next') or url_for('admin.dashboard'))
        flash('帳號或密碼錯誤', 'error')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
@admin_required
def logout():
    logout_user()
    return redirect(url_for('admin.login'))


# -------------------- 儀表板 --------------------
@admin_bp.route('/')
@admin_required
def dashboard():
    ctx = compute_context()
    products = Product.query.filter_by(active=True).all()
    summary = signal_summary(products, ctx)

    today = date.today()
    today_ferries = FerrySchedule.query.filter_by(schedule_date=today).all()
    pending_orders = Order.query.filter_by(status='pending').count()
    ready_orders = Order.query.filter_by(status='ready').count()
    customers = Customer.query.count()

    week_start = today - timedelta(days=6)
    week_orders = Order.query.filter(
        db.func.date(Order.created_at) >= week_start
    ).order_by(Order.created_at.desc()).limit(20).all()

    low_stock = [p for p in products if p.stock <= p.safety_stock][:10]

    return render_template(
        'admin/dashboard.html',
        summary=summary,
        weather=ctx['weather'],
        weather_alert=ctx['weather_alert'],
        ferries=today_ferries,
        pending_orders=pending_orders,
        ready_orders=ready_orders,
        customers=customers,
        week_orders=week_orders,
        low_stock=low_stock,
    )


# -------------------- 商品 / 庫存 --------------------
@admin_bp.route('/products')
@admin_required
def products():
    cats = Category.query.order_by(Category.sort_order).all()
    rows = Product.query.order_by(Product.sort_order).all()
    return render_template('admin/products.html', products=rows, categories=cats)


@admin_bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def product_new():
    cats = Category.query.order_by(Category.sort_order).all()
    if request.method == 'POST':
        p = Product(
            category_id=int(request.form.get('category_id') or 0) or None,
            name=request.form.get('name', '').strip(),
            sku=request.form.get('sku', '').strip(),
            price=int(request.form.get('price') or 0),
            unit=request.form.get('unit', '').strip() or '個',
            icon=request.form.get('icon', '').strip(),
            stock=int(request.form.get('stock') or 0),
            safety_stock=int(request.form.get('safety_stock') or 10),
            is_ferry_dependent=bool(request.form.get('is_ferry_dependent')),
            sort_order=int(request.form.get('sort_order') or 0),
            active=True,
        )
        db.session.add(p)
        db.session.commit()
        flash('已新增商品', 'success')
        return redirect(url_for('admin.products'))
    return render_template('admin/product_edit.html', product=None, categories=cats)


@admin_bp.route('/products/<int:pid>/edit', methods=['GET', 'POST'])
@admin_required
def product_edit(pid):
    p = Product.query.get_or_404(pid)
    cats = Category.query.order_by(Category.sort_order).all()
    if request.method == 'POST':
        p.category_id = int(request.form.get('category_id') or 0) or None
        p.name = request.form.get('name', '').strip()
        p.sku = request.form.get('sku', '').strip()
        p.price = int(request.form.get('price') or 0)
        p.unit = request.form.get('unit', '').strip() or '個'
        p.icon = request.form.get('icon', '').strip()
        p.stock = int(request.form.get('stock') or 0)
        p.safety_stock = int(request.form.get('safety_stock') or 10)
        p.is_ferry_dependent = bool(request.form.get('is_ferry_dependent'))
        p.sort_order = int(request.form.get('sort_order') or 0)
        p.active = bool(request.form.get('active'))
        db.session.commit()
        flash('已更新商品', 'success')
        return redirect(url_for('admin.products'))
    return render_template('admin/product_edit.html', product=p, categories=cats)


@admin_bp.route('/products/<int:pid>/restock', methods=['POST'])
@admin_required
def product_restock(pid):
    p = Product.query.get_or_404(pid)
    delta = int(request.form.get('delta') or 0)
    p.stock = max(0, p.stock + delta)
    db.session.commit()
    flash(f'已調整 {p.name} 庫存：{"+" if delta>=0 else ""}{delta}（目前 {p.stock}{p.unit}）', 'success')
    return redirect(url_for('admin.products'))


# -------------------- 船班 --------------------
@admin_bp.route('/ferries')
@admin_required
def ferries():
    today = date.today()
    rows = FerrySchedule.query.filter(
        FerrySchedule.schedule_date >= today - timedelta(days=2)
    ).order_by(FerrySchedule.schedule_date.desc(), FerrySchedule.scheduled_time).all()
    return render_template('admin/ferries.html', ferries=rows, statuses=FERRY_STATUS)


@admin_bp.route('/ferries/new', methods=['POST'])
@admin_required
def ferry_new():
    f = FerrySchedule(
        schedule_date=datetime.strptime(request.form.get('schedule_date') or date.today().isoformat(), '%Y-%m-%d').date(),
        ferry_name=request.form.get('ferry_name', '').strip() or '台馬之星',
        port=request.form.get('port', '').strip() or '福澳港',
        scheduled_time=request.form.get('scheduled_time', '').strip(),
        status=request.form.get('status', 'scheduled'),
        cargo_pct=int(request.form.get('cargo_pct') or 100),
        note=request.form.get('note', '').strip(),
    )
    db.session.add(f)
    db.session.commit()
    flash('已新增船班', 'success')
    return redirect(url_for('admin.ferries'))


@admin_bp.route('/ferries/<int:fid>/update', methods=['POST'])
@admin_required
def ferry_update(fid):
    f = FerrySchedule.query.get_or_404(fid)
    f.status = request.form.get('status', f.status)
    f.actual_time = request.form.get('actual_time', f.actual_time).strip()
    f.cargo_pct = int(request.form.get('cargo_pct') or f.cargo_pct)
    f.note = request.form.get('note', f.note).strip()
    db.session.commit()
    flash('已更新船班狀態', 'success')
    return redirect(url_for('admin.ferries'))


@admin_bp.route('/ferries/<int:fid>/delete', methods=['POST'])
@admin_required
def ferry_delete(fid):
    f = FerrySchedule.query.get_or_404(fid)
    db.session.delete(f)
    db.session.commit()
    flash('已刪除船班', 'success')
    return redirect(url_for('admin.ferries'))


# -------------------- 天氣 --------------------
@admin_bp.route('/weather', methods=['GET', 'POST'])
@admin_required
def weather():
    if request.method == 'POST':
        # 手動覆寫一筆
        snap = WeatherSnapshot(
            weather_desc=request.form.get('weather_desc', '').strip(),
            min_temp=int(request.form.get('min_temp') or 0),
            max_temp=int(request.form.get('max_temp') or 0),
            rain_prob=int(request.form.get('rain_prob') or 0),
            wind_level=int(request.form.get('wind_level') or 0),
            wave_height=float(request.form.get('wave_height') or 0),
            source='manual',
        )
        db.session.add(snap)
        db.session.commit()
        flash('已新增手動天氣紀錄', 'success')
        return redirect(url_for('admin.weather'))

    snaps = WeatherSnapshot.query.order_by(WeatherSnapshot.observed_at.desc()).limit(20).all()
    has_key = bool(os.getenv('CWA_API_KEY', '').strip())
    return render_template('admin/weather.html', snaps=snaps, has_key=has_key)


@admin_bp.route('/weather/refresh', methods=['POST'])
@admin_required
def weather_refresh():
    payload = refresh_weather_to_db(db, WeatherSnapshot, api_key=os.getenv('CWA_API_KEY'))
    if payload is None:
        flash('尚未設定 CWA_API_KEY；請到 .env 加上後重啟容器', 'error')
    elif isinstance(payload, dict) and payload.get('error'):
        flash(f'拉取失敗：{payload["error"]}', 'error')
    else:
        flash('已從中央氣象署拉取最新預報', 'success')
    return redirect(url_for('admin.weather'))


# -------------------- 訂單 --------------------
@admin_bp.route('/orders')
@admin_required
def orders():
    status = request.args.get('status', '')
    q = Order.query
    if status:
        q = q.filter_by(status=status)
    rows = q.order_by(Order.created_at.desc()).limit(200).all()
    return render_template('admin/orders.html', orders=rows, statuses=ORDER_STATUS, current=status)


@admin_bp.route('/orders/<order_no>/status', methods=['POST'])
@admin_required
def order_set_status(order_no):
    o = Order.query.filter_by(order_no=order_no).first_or_404()
    new_status = request.form.get('status', '')
    if new_status not in dict(ORDER_STATUS):
        flash('狀態錯誤', 'error')
        return redirect(url_for('admin.orders'))
    if new_status == 'picked' and o.status != 'picked':
        o.picked_at = datetime.utcnow()
        # 取貨時扣庫存
        for it in o.items:
            if it.product:
                it.product.stock = max(0, it.product.stock - it.quantity)
    o.status = new_status
    db.session.commit()
    flash(f'訂單 #{o.order_no} → {o.status_label}', 'success')
    return redirect(url_for('admin.orders'))


# -------------------- 顧客 --------------------
@admin_bp.route('/customers')
@admin_required
def customers():
    rows = Customer.query.order_by(Customer.created_at.desc()).all()
    return render_template('admin/customers.html', customers=rows)


# -------------------- 店家資訊 --------------------
@admin_bp.route('/store', methods=['GET', 'POST'])
@admin_required
def store():
    s = StoreInfo.current()
    if request.method == 'POST' and s:
        s.name = request.form.get('name', s.name)
        s.location = request.form.get('location', s.location)
        s.address = request.form.get('address', s.address)
        s.phone = request.form.get('phone', s.phone)
        s.port_name = request.form.get('port_name', s.port_name)
        s.cwa_location = request.form.get('cwa_location', s.cwa_location)
        s.open_hours = request.form.get('open_hours', s.open_hours)
        s.intro = request.form.get('intro', s.intro)
        db.session.commit()
        flash('已更新店家資訊', 'success')
        return redirect(url_for('admin.store'))
    return render_template('admin/store.html', store=s)


# -------------------- 設定（含 PWA icon） --------------------
SETTING_KEYS = [
    'site_name', 'site_short', 'site_tagline',
    'theme_color', 'background_color',
]


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        for k in SETTING_KEYS:
            if k in request.form:
                SiteSetting.set(k, request.form.get(k, '').strip())
        db.session.commit()
        flash('已更新網站設定', 'success')
        return redirect(url_for('admin.settings'))

    rows = {s.key: s.value for s in SiteSetting.query.all()}
    pwa_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'pwa')
    has_icon = os.path.exists(os.path.join(pwa_dir, 'icon-source.png'))
    return render_template('admin/settings.html', rows=rows, has_icon=has_icon)


@admin_bp.route('/settings/pwa-icon', methods=['POST'])
@admin_required
def upload_pwa_icon():
    f = request.files.get('icon')
    try:
        validate_and_save(f, current_app.config['UPLOAD_FOLDER'])
    except IconError as e:
        flash(f'圖示上傳失敗：{e}', 'error')
        return redirect(url_for('admin.settings'))

    cur = int(SiteSetting.get('pwa_icon_version', '1') or 1)
    SiteSetting.set('pwa_icon_version', str(cur + 1))
    db.session.commit()
    flash('PWA 圖示已更新（自動產出 192/512/180/32 並 bump 版本）', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/settings/password', methods=['POST'])
@admin_required
def change_password():
    old = request.form.get('old_password', '')
    new = request.form.get('new_password', '')
    if not current_user.check_password(old):
        flash('舊密碼錯誤', 'error')
    elif len(new) < 6:
        flash('新密碼至少 6 碼', 'error')
    else:
        current_user.set_password(new)
        db.session.commit()
        flash('密碼已更新', 'success')
    return redirect(url_for('admin.settings'))
