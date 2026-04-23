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
    Combo, ComboItem, Order, OrderItem, SiteSetting, StoreInfo, ProductReservation,
)
from app.models.customer import CUSTOMER_ROLES
from app.models.ferry import FERRY_STATUS
from app.models.order import ORDER_STATUS
from app.models.reservation import RESERVATION_STATUS
from app.utils.icons import validate_and_save, IconError
from app.utils.signal import compute_context, signal_summary
from app.utils.cwa import refresh_weather_to_db
from app.utils.analytics import restock_advice, order_heatmap
from app.utils.notify import low_stock_alerts, open_reservation_count
from app.utils.external import fetch_all as fetch_external, EXTERNAL_LINKS
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, AdminUser):
            # DEMO_MODE：允許未登入直接以預設 admin 身分操作
            if current_app.config.get('DEMO_MODE'):
                u = AdminUser.query.filter_by(role='super_admin').first() or AdminUser.query.first()
                if u:
                    login_user(u, remember=True)
                    return f(*args, **kwargs)
            flash('請先以管理員身分登入', 'error')
            return redirect(url_for('admin.login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


@admin_bp.route('/demo-enter')
def demo_enter():
    """DEMO_MODE 專用快捷：點一下即以預設 admin 進入後台。"""
    if not current_app.config.get('DEMO_MODE'):
        flash('DEMO_MODE 未開啟', 'error')
        return redirect(url_for('main.home'))
    u = AdminUser.query.filter_by(role='super_admin').first() or AdminUser.query.first()
    if u:
        login_user(u, remember=True)
    return redirect(url_for('admin.dashboard'))


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

    ProductReservation.auto_expire()
    open_res = open_reservation_count()
    advice = restock_advice(top_n=8)
    heatmap = order_heatmap(days=30)
    alerts = low_stock_alerts(top_n=8)

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
        open_res=open_res,
        advice=advice,
        heatmap=heatmap,
        alerts=alerts,
    )


# -------------------- 商品 / 庫存 --------------------
@admin_bp.route('/products')
@admin_required
def products():
    cats = Category.query.order_by(Category.sort_order).all()
    rows = Product.query.order_by(Product.sort_order).all()
    return render_template('admin/products.html', products=rows, categories=cats)


def _save_product_photo(file_storage, sku):
    if not file_storage or not file_storage.filename:
        return None
    fn = secure_filename(file_storage.filename)
    ext = fn.rsplit('.', 1)[-1].lower() if '.' in fn else 'png'
    if ext not in ('png', 'jpg', 'jpeg', 'webp'):
        return None
    safe_name = f'{sku or "product"}.{ext}'
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, safe_name)
    file_storage.save(path)
    return safe_name


@admin_bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def product_new():
    cats = Category.query.order_by(Category.sort_order).all()
    if request.method == 'POST':
        sku = request.form.get('sku', '').strip()
        photo = _save_product_photo(request.files.get('photo'), sku)
        p = Product(
            category_id=int(request.form.get('category_id') or 0) or None,
            name=request.form.get('name', '').strip(),
            sku=sku,
            price=int(request.form.get('price') or 0),
            unit=request.form.get('unit', '').strip() or '個',
            icon=request.form.get('icon', '').strip(),
            stock=int(request.form.get('stock') or 0),
            safety_stock=int(request.form.get('safety_stock') or 10),
            is_ferry_dependent=bool(request.form.get('is_ferry_dependent')),
            sort_order=int(request.form.get('sort_order') or 0),
            photo=photo or '',
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
        new_photo = _save_product_photo(request.files.get('photo'), p.sku)
        if new_photo:
            p.photo = new_photo
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
    return render_template('admin/customers.html', customers=rows, roles=CUSTOMER_ROLES)


@admin_bp.route('/customers/new', methods=['POST'])
@admin_required
def customer_new():
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    if not username or len(password) < 6:
        flash('帳號與 6 碼以上的密碼必填', 'error')
        return redirect(url_for('admin.customers'))
    if Customer.query.filter_by(username=username).first():
        flash('帳號已存在', 'error')
        return redirect(url_for('admin.customers'))
    c = Customer(
        username=username,
        full_name=(request.form.get('full_name') or '').strip(),
        email=(request.form.get('email') or '').strip(),
        phone=(request.form.get('phone') or '').strip(),
        role=request.form.get('role') or 'resident',
    )
    c.set_password(password)
    db.session.add(c)
    db.session.commit()
    flash(f'已新增會員 {c.username}', 'success')
    return redirect(url_for('admin.customers'))


@admin_bp.route('/customers/<int:cid>/update', methods=['POST'])
@admin_required
def customer_update(cid):
    c = Customer.query.get_or_404(cid)
    c.full_name = (request.form.get('full_name') or c.full_name).strip()
    c.email = (request.form.get('email') or c.email).strip()
    c.phone = (request.form.get('phone') or c.phone).strip()
    c.role = request.form.get('role') or c.role
    db.session.commit()
    flash('已更新會員資料', 'success')
    return redirect(url_for('admin.customers'))


@admin_bp.route('/customers/<int:cid>/toggle', methods=['POST'])
@admin_required
def customer_toggle(cid):
    c = Customer.query.get_or_404(cid)
    c.is_active = not c.is_active
    db.session.commit()
    flash(f'已{"啟用" if c.is_active else "停用"} {c.username}', 'success')
    return redirect(url_for('admin.customers'))


@admin_bp.route('/customers/<int:cid>/reset-password', methods=['POST'])
@admin_required
def customer_reset_password(cid):
    c = Customer.query.get_or_404(cid)
    new_pw = request.form.get('new_password') or ''
    if len(new_pw) < 6:
        flash('密碼至少 6 碼', 'error')
        return redirect(url_for('admin.customers'))
    c.set_password(new_pw)
    db.session.commit()
    flash(f'已重設 {c.username} 的密碼', 'success')
    return redirect(url_for('admin.customers'))


@admin_bp.route('/customers/<int:cid>/delete', methods=['POST'])
@admin_required
def customer_delete(cid):
    c = Customer.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    flash('已刪除會員（連帶刪除其組合與訂單）', 'success')
    return redirect(url_for('admin.customers'))


# -------------------- 預留 --------------------
@admin_bp.route('/reservations')
@admin_required
def reservations():
    ProductReservation.auto_expire()
    status = request.args.get('status', 'open')
    q = ProductReservation.query
    if status == 'open':
        q = q.filter(ProductReservation.status.in_(['requested', 'ready']))
    elif status == 'all':
        pass
    else:
        q = q.filter_by(status=status)
    rows = q.order_by(ProductReservation.created_at.desc()).limit(200).all()
    return render_template('admin/reservations.html', rows=rows, statuses=RESERVATION_STATUS, current=status)


@admin_bp.route('/reservations/<int:rid>/status', methods=['POST'])
@admin_required
def reservation_set_status(rid):
    r = ProductReservation.query.get_or_404(rid)
    new_status = request.form.get('status', '')
    if new_status not in dict(RESERVATION_STATUS):
        flash('狀態錯誤', 'error')
        return redirect(url_for('admin.reservations'))
    if new_status == 'ready' and r.status != 'ready':
        r.ready_at = datetime.utcnow()
    if new_status == 'picked' and r.status != 'picked':
        r.picked_at = datetime.utcnow()
        # 取貨時扣庫存
        if r.product:
            r.product.stock = max(0, r.product.stock - r.quantity)
    r.status = new_status
    db.session.commit()
    flash(f'預留 #{r.code} → {r.status_label}', 'success')
    return redirect(url_for('admin.reservations'))


# -------------------- 資料來源 --------------------
@admin_bp.route('/sources')
@admin_required
def sources():
    weather = WeatherSnapshot.query.order_by(WeatherSnapshot.observed_at.desc()).first()
    latest_ferry = FerrySchedule.query.order_by(FerrySchedule.updated_at.desc()).first()
    latest_product = Product.query.order_by(Product.updated_at.desc()).first()
    latest_customer = Customer.query.order_by(Customer.created_at.desc()).first()
    latest_order = Order.query.order_by(Order.created_at.desc()).first()
    has_cwa = bool(os.getenv('CWA_API_KEY', '').strip())

    sources_info = [
        {
            'key': 'cwa', 'name': '中央氣象署 CWA',
            'desc': '鄉鎮天氣預報-連江縣 F-D0047-079（風、雨、溫度）',
            'connected': has_cwa,
            'last': weather.observed_at if weather else None,
            'note': f'最近一筆來自：{weather.source}' if weather else '尚無資料',
            'refresh_url': url_for('admin.weather_refresh'),
        },
        {
            'key': 'ferry', 'name': '船班排程',
            'desc': '人工維護（福澳港 + 台馬之星 / 合富快輪）',
            'connected': True,
            'last': latest_ferry.updated_at if latest_ferry else None,
            'note': '請於「船班」頁手動更新',
            'refresh_url': url_for('admin.ferries'),
        },
        {
            'key': 'product', 'name': '商品庫存',
            'desc': f'共 {Product.query.count()} 個商品',
            'connected': True,
            'last': latest_product.updated_at if latest_product else None,
            'note': '進貨後到「商品 / 庫存」頁調整',
            'refresh_url': url_for('admin.products'),
        },
        {
            'key': 'customer', 'name': '會員',
            'desc': f'共 {Customer.query.count()} 位註冊會員',
            'connected': True,
            'last': latest_customer.created_at if latest_customer else None,
            'note': '由會員自行註冊或後台新增',
            'refresh_url': url_for('admin.customers'),
        },
        {
            'key': 'order', 'name': '訂單',
            'desc': f'共 {Order.query.count()} 筆訂單',
            'connected': True,
            'last': latest_order.created_at if latest_order else None,
            'note': '顧客一鍵下單組合包後即生成',
            'refresh_url': url_for('admin.orders'),
        },
        {
            'key': 'reservation', 'name': '商品預留',
            'desc': f'進行中 {open_reservation_count()} 筆，24h 自動釋放',
            'connected': True,
            'last': None,
            'note': '顧客在首頁點燈號即可預留',
            'refresh_url': url_for('admin.reservations'),
        },
    ]
    return render_template('admin/sources.html', sources=sources_info, has_cwa=has_cwa)


@admin_bp.route('/external')
@admin_required
def external():
    """離島實時情報後台：顯示南竿機場 METAR、馬祖海面、台灣北部海面 + 外連。"""
    data = fetch_external()
    return render_template('admin/external.html', external=data, links=EXTERNAL_LINKS)


@admin_bp.route('/external/refresh', methods=['POST'])
@admin_required
def external_refresh():
    fetch_external(force=True)
    flash('已重新抓取離島實時情報', 'success')
    return redirect(url_for('admin.external'))


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
