"""個別商品電子紙模擬頁：/tag/<sku>。
給平板放在貨架旁，顯示一個品項的大字燈號。"""
from flask import Blueprint, render_template, abort
from app.models import Product
from app.utils.signal import compute_context

tag_bp = Blueprint('tag', __name__)


@tag_bp.route('/tag/<sku>')
def show(sku):
    p = Product.query.filter_by(sku=sku).first()
    if not p:
        abort(404)
    ctx = compute_context()
    color, label = p.signal(ctx['ferry_today_ok'], ctx['weather_alert'])
    return render_template('tag/show.html', product=p, color=color, label=label,
                           weather_alert=ctx['weather_alert'])
