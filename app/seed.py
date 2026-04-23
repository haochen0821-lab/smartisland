"""啟動時 seed 範例資料：南竿介壽店、30 商品、3 顧客、5 組合範本、近期船班與天氣。"""
import os
import secrets
from datetime import date, datetime, timedelta
from app import db
from app.models import (
    AdminUser, Customer, SiteSetting, StoreInfo,
    Category, Product, FerrySchedule, WeatherSnapshot,
    Combo, ComboItem, Order, OrderItem,
)


DEFAULT_SETTINGS = {
    'site_name': 'Smart Island Hub｜智慧島嶼中心',
    'site_short': 'Smart Island',
    'site_tagline': '島民的安心定錨：讓天氣不再是生活的變數，而是購物的節奏。',
    'theme_color': '#1f6f8b',
    'background_color': '#eef6f8',
    'pwa_icon_version': '1',
}

DEFAULT_STORE = {
    'name': '南竿介壽智慧島嶼超商',
    'location': '南竿介壽',
    'address': '連江縣南竿鄉介壽村 X 號',
    'phone': '0836-22XXX',
    'port_name': '福澳港',
    'cwa_location': '南竿鄉',
    'open_hours': '06:30-22:30',
    'intro': '位於南竿介壽商圈的離島超商，串接福澳港物流與中央氣象署資料，讓島民出門前就知道貨架狀態。',
}

# (cat_slug, name, price, unit, icon, stock, safety, ferry_dep, sort)
PRODUCTS = [
    # 生鮮（依賴船班）
    ('fresh', '雞蛋（10 顆/盒）',  90, '盒', '🥚',  18, 10, True,  1),
    ('fresh', '鮮乳 936ml',        95, '瓶', '🥛',   6, 12, True,  2),
    ('fresh', '高麗菜（半顆）',     65, '袋', '🥬',   3,  8, True,  3),
    ('fresh', '青江菜',             45, '袋', '🥗',   4,  8, True,  4),
    ('fresh', '番茄（500g）',       55, '袋', '🍅',  10,  6, True,  5),
    ('fresh', '香蕉（一串）',       60, '串', '🍌',  12,  5, True,  6),
    ('fresh', '土雞胸肉',          120, '盒', '🍗',   2,  6, True,  7),
    ('fresh', '鮭魚切片',          180, '盒', '🐟',   1,  4, True,  8),
    # 早餐（部分依賴）
    ('breakfast', '吐司（白）',     45, '條', '🍞',  20,  8, True,   1),
    ('breakfast', '美式咖啡',       45, '杯', '☕',  50,  10, False,  2),
    ('breakfast', '飯糰',           45, '個', '🍙',   8, 12, True,   3),
    ('breakfast', '三明治',         55, '個', '🥪',   6, 10, True,   4),
    ('breakfast', '優酪乳',         35, '瓶', '🍶',  14, 10, True,   5),
    # 餐食 / 加熱
    ('hot', '便當（家常雞腿）',    100, '個', '🍱',  10, 15, True,   1),
    ('hot', '關東煮（綜合）',       80, '份', '🍢',   9,  6, False,  2),
    ('hot', '茶葉蛋',               12, '顆', '🥚',  40, 20, False,  3),
    ('hot', '微波義大利麵',         75, '盒', '🍝',   7,  8, True,   4),
    # 飲料
    ('drink', '寶特瓶水 600ml',     20, '瓶', '💧',  60, 30, False,  1),
    ('drink', '運動飲料',           30, '瓶', '🥤',  40, 20, False,  2),
    ('drink', '高山烏龍茶',         35, '瓶', '🍵',  35, 15, False,  3),
    ('drink', '黑咖啡罐',           28, '罐', '🥫',  28, 15, False,  4),
    # 民生用品（不依賴船班，可儲存）
    ('daily', '抽取式衛生紙',      129, '串', '🧻',  25, 10, False,  1),
    ('daily', '濕紙巾',             45, '包', '🧴',  18, 10, False,  2),
    ('daily', '電池 3 號 4 入',     85, '組', '🔋',  12,  6, False,  3),
    ('daily', '打火機',             20, '個', '🔥',  30, 10, False,  4),
    # 零食 / 補給
    ('snack', '餅乾（蘇打）',       38, '包', '🍪',  22, 12, False,  1),
    ('snack', '巧克力棒',           30, '條', '🍫',  18, 12, False,  2),
    ('snack', '泡麵（牛肉麵）',     45, '碗', '🍜',  35, 15, False,  3),
    ('snack', '能量棒',             45, '條', '🍫',  20, 10, False,  4),
    ('snack', '肉乾',               99, '包', '🥓',  10,  8, False,  5),
]

CATEGORIES = [
    ('生鮮蔬果', 'fresh',      '🥬', 1),
    ('早餐輕食', 'breakfast',  '🥪', 2),
    ('熱食便當', 'hot',        '🍱', 3),
    ('飲料',     'drink',      '🥤', 4),
    ('民生用品', 'daily',      '🧻', 5),
    ('零食補給', 'snack',      '🍪', 6),
]

CUSTOMERS = [
    # username, password, full_name, phone, role
    ('chen',  'demo1234', '陳大哥（民宿主人）', '0936-xxx-101', 'innkeeper'),
    ('aling', 'demo1234', '阿玲（在地居民）',   '0918-xxx-202', 'resident'),
    ('mike',  'demo1234', 'Mike（背包客）',     '0978-xxx-303', 'tourist'),
]

# 範本組合：(name, icon, desc, [(sku_keyword, qty), ...])
COMBO_TEMPLATES = [
    ('民宿早餐 6 人組', '🍳', '雞蛋、鮮乳、吐司、咖啡，一鍵備齊', [
        ('雞蛋（10 顆/盒）', 1), ('鮮乳 936ml', 2), ('吐司（白）', 1), ('美式咖啡', 6),
    ]),
    ('民宿備品週補', '🛏️', '衛生紙、瓶裝水、電池，每週一次', [
        ('抽取式衛生紙', 2), ('寶特瓶水 600ml', 24), ('電池 3 號 4 入', 1), ('濕紙巾', 2),
    ]),
    ('一個人的宵夜', '🌙', '泡麵、茶葉蛋、運動飲料', [
        ('泡麵（牛肉麵）', 1), ('茶葉蛋', 2), ('運動飲料', 1),
    ]),
    ('登山補給包', '⛰️', '能量棒、水、肉乾', [
        ('能量棒', 4), ('寶特瓶水 600ml', 3), ('肉乾', 1), ('巧克力棒', 2),
    ]),
    ('來島伴手禮', '🎁', '高山烏龍茶、餅乾、巧克力', [
        ('高山烏龍茶', 3), ('餅乾（蘇打）', 2), ('巧克力棒', 4),
    ]),
]


def _ensure_settings():
    changed = False
    for k, v in DEFAULT_SETTINGS.items():
        if not SiteSetting.query.filter_by(key=k).first():
            db.session.add(SiteSetting(key=k, value=v))
            changed = True
    return changed


def _ensure_admin():
    if AdminUser.query.count() == 0:
        a = AdminUser(
            username=os.getenv('ADMIN_USERNAME', 'admin'),
            role='super_admin',
            is_active=True,
        )
        a.set_password(os.getenv('ADMIN_PASSWORD', 'smartisland2026'))
        db.session.add(a)
        return True
    return False


def _ensure_store():
    if StoreInfo.query.count() == 0:
        db.session.add(StoreInfo(**DEFAULT_STORE))
        return True
    return False


def _ensure_categories_and_products():
    changed = False
    if Category.query.count() == 0:
        for name, slug, icon, order in CATEGORIES:
            db.session.add(Category(name=name, slug=slug, icon=icon, sort_order=order))
        db.session.flush()
        changed = True

    if Product.query.count() == 0:
        slug_map = {c.slug: c.id for c in Category.query.all()}
        sku_seq = 1001
        for slug, name, price, unit, icon, stock, safety, ferry_dep, order in PRODUCTS:
            db.session.add(Product(
                category_id=slug_map.get(slug),
                name=name, sku=f'SI{sku_seq}',
                price=price, unit=unit, icon=icon,
                stock=stock, safety_stock=safety,
                is_ferry_dependent=ferry_dep,
                sort_order=order, active=True,
            ))
            sku_seq += 1
        changed = True
    return changed


def _ensure_customers():
    if Customer.query.count() == 0:
        for username, pw, name, phone, role in CUSTOMERS:
            c = Customer(username=username, full_name=name, phone=phone, role=role)
            c.set_password(pw)
            db.session.add(c)
        return True
    return False


def _ensure_combo_templates():
    if Combo.query.filter_by(is_template=True).count() > 0:
        return False
    db.session.flush()
    products_by_name = {p.name: p for p in Product.query.all()}
    for sort_idx, (name, icon, desc, items) in enumerate(COMBO_TEMPLATES, start=1):
        combo = Combo(
            customer_id=None,
            name=name,
            description=desc,
            icon=icon,
            is_template=True,
            sort_order=sort_idx,
        )
        db.session.add(combo)
        db.session.flush()
        for pname, qty in items:
            p = products_by_name.get(pname)
            if not p:
                continue
            db.session.add(ComboItem(combo_id=combo.id, product_id=p.id, quantity=qty))
    return True


def _ensure_ferries():
    today = date.today()
    if FerrySchedule.query.filter_by(schedule_date=today).count() > 0:
        return False

    # 過去 6 天歷史
    for i in range(6, 0, -1):
        d = today - timedelta(days=i)
        db.session.add(FerrySchedule(
            schedule_date=d, ferry_name='台馬之星', port='福澳港',
            scheduled_time='21:00', actual_time='21:15',
            status='arrived', cargo_pct=100,
            note='夜航靠港，補給正常',
        ))
        if i % 2 == 0:
            db.session.add(FerrySchedule(
                schedule_date=d, ferry_name='合富快輪', port='福澳港',
                scheduled_time='06:40', actual_time='06:45',
                status='arrived', cargo_pct=80,
                note='貨櫃滿載',
            ))

    # 今日：合富已到，台馬之星延誤
    db.session.add(FerrySchedule(
        schedule_date=today, ferry_name='合富快輪', port='福澳港',
        scheduled_time='06:40', actual_time='06:42',
        status='arrived', cargo_pct=90,
        note='今日生鮮已上架',
    ))
    db.session.add(FerrySchedule(
        schedule_date=today, ferry_name='台馬之星', port='福澳港',
        scheduled_time='21:00', actual_time='',
        status='delayed', cargo_pct=70,
        note='受東北季風影響預計延誤 30 分',
    ))

    # 明日預定
    tomorrow = today + timedelta(days=1)
    db.session.add(FerrySchedule(
        schedule_date=tomorrow, ferry_name='合富快輪', port='福澳港',
        scheduled_time='06:40', actual_time='',
        status='scheduled', cargo_pct=100,
        note='',
    ))
    return True


def _ensure_weather_fallback():
    if WeatherSnapshot.query.count() > 0:
        return False
    # fallback 模擬資料（沒有 CWA Key 時看板/首頁仍有東西可顯示）
    snap = WeatherSnapshot(
        observed_at=datetime.utcnow(),
        weather_desc='多雲短暫陣雨',
        min_temp=18, max_temp=23,
        rain_prob=60,
        wind_level=5,
        wave_height=2.1,
        source='fallback',
        raw='seed:default',
    )
    db.session.add(snap)
    return True


def _ensure_demo_orders():
    if Order.query.count() > 0:
        return False
    chen = Customer.query.filter_by(username='chen').first()
    if not chen:
        return False
    breakfast = Combo.query.filter_by(name='民宿早餐 6 人組', is_template=True).first()
    if not breakfast:
        return False
    # 先給陳大哥 clone 一份到他自己
    my_breakfast = Combo(
        customer_id=chen.id, name=breakfast.name,
        description=breakfast.description, icon=breakfast.icon,
    )
    db.session.add(my_breakfast)
    db.session.flush()
    for it in breakfast.items:
        db.session.add(ComboItem(combo_id=my_breakfast.id, product_id=it.product_id, quantity=it.quantity))

    # 已完成訂單一筆（昨天）
    yesterday = datetime.utcnow() - timedelta(days=1)
    o = Order(
        order_no=f'{yesterday.strftime("%m%d")}-001',
        qr_token=secrets.token_urlsafe(16),
        customer_id=chen.id,
        combo_id=my_breakfast.id,
        status='picked',
        total_amount=0,
        created_at=yesterday,
        picked_at=yesterday + timedelta(minutes=15),
    )
    db.session.add(o)
    db.session.flush()
    total = 0
    for it in my_breakfast.items:
        if not it.product:
            continue
        db.session.add(OrderItem(
            order_id=o.id, product_id=it.product_id,
            product_name=it.product.name, quantity=it.quantity,
            unit_price=it.product.price,
        ))
        total += it.product.price * it.quantity
    o.total_amount = total
    return True


def seed_defaults():
    changed = False
    changed |= _ensure_settings()
    changed |= _ensure_admin()
    changed |= _ensure_store()
    changed |= _ensure_categories_and_products()
    changed |= _ensure_customers()
    if changed:
        db.session.commit()

    changed = False
    changed |= _ensure_combo_templates()
    changed |= _ensure_ferries()
    changed |= _ensure_weather_fallback()
    if changed:
        db.session.commit()

    if _ensure_demo_orders():
        db.session.commit()
