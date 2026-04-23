import os
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db
from app.models import Product, Category, FerrySchedule, WeatherSnapshot
from app.utils.signal import compute_context
from app.utils.cwa import refresh_weather_to_db

main_bp = Blueprint('main', __name__)


def _latest_data_timestamp(weather, ferries, products):
    """取所有資料源中最新的更新時間（皆為 UTC）。"""
    candidates = []
    if weather and weather.observed_at:
        candidates.append(weather.observed_at)
    for f in ferries:
        if f.updated_at:
            candidates.append(f.updated_at)
    for p in products:
        if p.updated_at:
            candidates.append(p.updated_at)
    return max(candidates) if candidates else None


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

    last_updated = _latest_data_timestamp(ctx['weather'], today_ferries, products)

    return render_template(
        'home.html',
        grouped=grouped,
        ferries=today_ferries,
        weather=ctx['weather'],
        weather_alert=ctx['weather_alert'],
        last_updated=last_updated,
    )


@main_bp.route('/refresh', methods=['POST'])
def refresh():
    """首頁一鍵更新：拉一次 CWA 氣象（若有 key），然後 redirect 回首頁。"""
    payload = refresh_weather_to_db(db, WeatherSnapshot, api_key=os.getenv('CWA_API_KEY'))
    if payload is None:
        flash('已重整。氣象 API Key 未設定，僅顯示既有資料。', 'success')
    elif isinstance(payload, dict) and payload.get('error'):
        flash(f'CWA 拉取失敗：{payload["error"]}', 'error')
    else:
        flash('已從中央氣象署拉取最新天氣資料', 'success')
    return redirect(url_for('main.home'))
