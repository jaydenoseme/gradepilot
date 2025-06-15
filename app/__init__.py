from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
import os
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()

# List of usernames with admin privileges
ADMIN_USERNAMES = ['jaydenokoeguale']

# Admin check helper function
def is_admin():
    return current_user.is_authenticated and current_user.username in ADMIN_USERNAMES

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'grades_new.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    os.makedirs(os.path.join(app.instance_path), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Register Blueprints
    from .routes import main
    app.register_blueprint(main)

    # Setup Flask-Login
    from app.models import User
    login_manager = LoginManager()
    login_manager.login_view = 'main.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Custom Jinja filter for formatting datetime objects
    def datetimeformat(value, format='%b %-d %Y'):
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d')
            except Exception:
                return value
        return value.strftime(format)

    app.jinja_env.filters['datetimeformat'] = datetimeformat

    # Inject is_admin function into Jinja templates (so you can use {{ is_admin }} in HTML)
    @app.context_processor
    def inject_is_admin():
        return dict(is_admin=is_admin())

    return app
