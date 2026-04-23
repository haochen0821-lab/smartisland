from datetime import date
from flask import Blueprint, render_template
from app.models import Product, Category, FerrySchedule, StoreInfo
from app.utils.signal import compute_context, signal_summary

board_bp = Blueprint('board', __name__)


@board_bp.route('/board')
def board():
    """店內看板：全螢幕無登入，給平板/電視顯示。"""
    ctx = compute_context()
    products = Product.query.filter_by(active=True).order_by(Product.sort_order).all()

    cats = Category.query.order_by(Category.sort_order).all()
    by_cat = []
    for cat in cats:
        items = []
        for p in products:
            if p.category_id == cat.id:
                color, label = p.signal(ctx['ferry_today_ok'], ctx['weather_alert'])
                items.append({'product': p, 'color': color, 'label': label})
        if items:
            by_cat.append({'category': cat, 'items': items})

    summary = signal_summary(products, ctx)
    ferries = FerrySchedule.query.filter_by(schedule_date=date.today()).order_by(
        FerrySchedule.scheduled_time
    ).all()
    store = StoreInfo.current()

    return render_template(
        'board.html',
        store=store,
        weather=ctx['weather'],
        weather_alert=ctx['weather_alert'],
        ferries=ferries,
        by_cat=by_cat,
        summary=summary,
    )
