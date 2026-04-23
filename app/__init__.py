import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    instance_dir = os.path.join(app.root_path, '..', 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.abspath(os.path.join(instance_dir, 'smartisland.db'))
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'pwa'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'products'), exist_ok=True)
    app.config['DEMO_MODE'] = os.getenv('DEMO_MODE', 'true').lower() == 'true'

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '請先登入'
    csrf.init_app(app)

    from app.models import AdminUser, Customer

    @login_manager.user_loader
    def load_user(user_id):
        # user_id 形如 "admin:1" / "customer:3"
        if not user_id or ':' not in user_id:
            return None
        kind, raw = user_id.split(':', 1)
        try:
            uid = int(raw)
        except ValueError:
            return None
        if kind == 'admin':
            return db.session.get(AdminUser, uid)
        if kind == 'customer':
            return db.session.get(Customer, uid)
        return None

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.combos import combos_bp
    from app.routes.orders import orders_bp
    from app.routes.board import board_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.pwa import pwa_bp
    from app.routes.reservations import reservations_bp
    from app.routes.tag import tag_bp
    from app.routes.info import info_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(combos_bp, url_prefix='/combos')
    app.register_blueprint(orders_bp, url_prefix='/orders')
    app.register_blueprint(reservations_bp, url_prefix='/reserve')
    app.register_blueprint(info_bp)
    app.register_blueprint(board_bp)
    app.register_blueprint(tag_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(pwa_bp)

    csrf.exempt(api_bp)

    with app.app_context():
        db.create_all()
        from app.utils.migrations import ensure_columns
        ensure_columns()
        from app.seed import seed_defaults
        seed_defaults()

    from app.context import inject_globals
    app.context_processor(inject_globals)

    @app.route('/healthz')
    def healthz():
        return {'status': 'ok'}, 200

    return app
