from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect  # ← NEW
import os
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()  # ← NEW

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'grades_new.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    os.makedirs(os.path.join(app.instance_path), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)  # ← NEW ✅

    from .routes import main
    app.register_blueprint(main)

    from app.models import User
    login_manager = LoginManager()
    login_manager.login_view = 'main.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    def datetimeformat(value, format='%b %-d %Y'):
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d')
            except Exception:
                return value
        return value.strftime(format)

    app.jinja_env.filters['datetimeformat'] = datetimeformat

    return app
