from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import Customer
from app.models.customer import CUSTOMER_ROLES

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'resident')
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not username or not password:
            flash('請輸入帳號與密碼', 'error')
        elif len(password) < 6:
            flash('密碼至少 6 碼', 'error')
        elif password != password2:
            flash('兩次密碼不一致', 'error')
        elif Customer.query.filter_by(username=username).first():
            flash('帳號已被使用', 'error')
        else:
            c = Customer(
                username=username,
                email=email,
                phone=phone,
                full_name=full_name or username,
                role=role,
            )
            c.set_password(password)
            db.session.add(c)
            db.session.commit()
            login_user(c)
            flash('註冊成功，歡迎加入 Smart Island Hub！', 'success')
            return redirect(url_for('main.home'))

    return render_template('auth/register.html', roles=CUSTOMER_ROLES)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        c = Customer.query.filter_by(username=username).first()
        if c and c.check_password(password) and c.is_active:
            login_user(c, remember=True)
            flash(f'歡迎回來，{c.full_name or c.username}！', 'success')
            return redirect(request.args.get('next') or url_for('main.home'))
        flash('帳號或密碼錯誤', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已登出', 'success')
    return redirect(url_for('main.home'))
