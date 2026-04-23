"""離島實時情報公開頁：/realtime
獨立於首頁，可給訪客直接看 METAR / 馬祖海面 / 北部海面 / 外連。
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.utils.external import fetch_all as fetch_external, EXTERNAL_LINKS

info_bp = Blueprint('info', __name__)


@info_bp.route('/realtime')
def realtime():
    data = fetch_external()
    return render_template('info/realtime.html', external=data, links=EXTERNAL_LINKS)


@info_bp.route('/realtime/refresh', methods=['POST'])
def realtime_refresh():
    fetch_external(force=True)
    flash('已重新抓取離島實時情報', 'success')
    return redirect(url_for('info.realtime'))
