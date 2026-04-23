from datetime import date
from flask import Blueprint, render_template
from app.models import Product, Category, FerrySchedule
from app.utils.signal import compute_context
from app.utils.external import fetch_all as fetch_external

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    ctx = compute_context()
    categories = Category.query.order_by(Category.sort_order).all()
    products = Product.query.filter_by(active=True).order_by(Product.sort_order).all()

    grouped = []
    for cat in categories:
        items = []
        for p in products:
            if p.category_id == cat.id:
                color, label = p.signal(ctx['ferry_today_ok'], ctx['weather_alert'])
                items.append({'product': p, 'color': color, 'label': label})
        grouped.append({'category': cat, 'items': items})

    today_ferries = FerrySchedule.query.filter_by(schedule_date=date.today()).order_by(
        FerrySchedule.scheduled_time
    ).all()

    external = fetch_external()

    return render_template(
        'home.html',
        grouped=grouped,
        ferries=today_ferries,
        weather=ctx['weather'],
        weather_alert=ctx['weather_alert'],
        external=external,
    )
