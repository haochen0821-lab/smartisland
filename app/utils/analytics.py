"""店家備貨建議與熱門時段熱力圖。"""
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from app.models import Order, OrderItem, Product, ProductReservation


def restock_advice(top_n=10, target_days=3):
    """根據過去 7 天的訂單 + 預留量，估算每個依賴船班商品的「下批船建議補多少」。

    建議補 = max(0, target_days * avg_daily - current_stock + safety_stock)
    """
    cutoff = datetime.utcnow() - timedelta(days=7)

    # 過去 7 天每個 product_id 的銷售量
    sold = db.session.query(
        OrderItem.product_id,
        func.coalesce(func.sum(OrderItem.quantity), 0)
    ).join(Order, Order.id == OrderItem.order_id) \
     .filter(Order.created_at >= cutoff, Order.status != 'cancelled') \
     .group_by(OrderItem.product_id).all()
    sold_map = {pid: int(qty) for pid, qty in sold}

    # 過去 7 天的預留量
    reserved = db.session.query(
        ProductReservation.product_id,
        func.coalesce(func.sum(ProductReservation.quantity), 0)
    ).filter(ProductReservation.created_at >= cutoff,
             ProductReservation.status.in_(['requested', 'ready', 'picked'])
    ).group_by(ProductReservation.product_id).all()
    reserved_map = {pid: int(qty) for pid, qty in reserved}

    items = []
    for p in Product.query.filter_by(active=True).all():
        consumed_7d = sold_map.get(p.id, 0) + reserved_map.get(p.id, 0)
        avg_daily = consumed_7d / 7.0
        suggested = max(0, int(round(target_days * avg_daily - p.stock + p.safety_stock)))
        if suggested > 0 or consumed_7d > 0:
            items.append({
                'product': p,
                'consumed_7d': consumed_7d,
                'avg_daily': round(avg_daily, 1),
                'suggested': suggested,
            })

    items.sort(key=lambda x: (x['suggested'], x['consumed_7d']), reverse=True)
    return items[:top_n]


WEEKDAY_NAMES = ['一', '二', '三', '四', '五', '六', '日']


def order_heatmap(days=30):
    """過去 N 天，按 (weekday, hour bucket) 統計訂單數。
    回傳 dict: { weekday(0-6): { hour_bucket: count } }, 與每個 bucket 的中文標籤。
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = db.session.query(Order.created_at).filter(
        Order.created_at >= cutoff,
        Order.status != 'cancelled',
    ).all()

    buckets = ['06-09', '09-12', '12-15', '15-18', '18-21', '21-24', '00-06']
    grid = defaultdict(lambda: defaultdict(int))

    def hour_to_bucket(h):
        if h < 6:  return '00-06'
        if h < 9:  return '06-09'
        if h < 12: return '09-12'
        if h < 15: return '12-15'
        if h < 18: return '15-18'
        if h < 21: return '18-21'
        return '21-24'

    for (created_at,) in rows:
        wd = (created_at.weekday())  # 0=Mon
        b = hour_to_bucket(created_at.hour)
        grid[wd][b] += 1

    # 找出最大值用於 shading
    max_val = 0
    for wd in range(7):
        for b in buckets:
            max_val = max(max_val, grid[wd][b])

    matrix = []
    for wd in range(7):
        row = {'name': f'週{WEEKDAY_NAMES[wd]}', 'cells': []}
        for b in buckets:
            v = grid[wd][b]
            ratio = (v / max_val) if max_val else 0
            row['cells'].append({'val': v, 'ratio': ratio, 'bucket': b})
        matrix.append(row)
    return {'buckets': buckets, 'matrix': matrix, 'max': max_val}
