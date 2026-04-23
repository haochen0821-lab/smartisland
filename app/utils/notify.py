"""通知中心：低庫存警告、預留逾時等。

目前只回傳 in-app alerts 給 dashboard 顯示；email/LINE hook 預留以下函式
(send_email)，未來在 .env 設定 SMTP 後可啟用。
"""
import os
import smtplib
from email.mime.text import MIMEText
from app.models import Product, ProductReservation


def low_stock_alerts(top_n=5):
    """回傳目前低於安全水位的依賴船班商品（最緊迫前 N 個）。"""
    rows = Product.query.filter_by(active=True, is_ferry_dependent=True).all()
    out = []
    for p in rows:
        if p.stock <= p.safety_stock:
            severity = 'high' if p.stock == 0 else ('mid' if p.stock <= p.safety_stock // 2 else 'low')
            out.append({'product': p, 'severity': severity})
    out.sort(key=lambda x: (x['product'].stock, -x['product'].safety_stock))
    return out[:top_n]


def open_reservation_count():
    return ProductReservation.query.filter(
        ProductReservation.status.in_(['requested', 'ready'])
    ).count()


def send_email(to, subject, body):
    """SMTP hook；若 .env 沒設 SMTP 相關變數，靜默失敗回傳 False。"""
    host = os.getenv('SMTP_HOST', '').strip()
    if not host:
        return False
    port = int(os.getenv('SMTP_PORT', '587'))
    user = os.getenv('SMTP_USER', '')
    pw = os.getenv('SMTP_PASS', '')
    sender = os.getenv('SMTP_SENDER', user or 'noreply@smartisland')
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to
    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.starttls()
            if user:
                s.login(user, pw)
            s.sendmail(sender, [to], msg.as_string())
        return True
    except Exception:
        return False
