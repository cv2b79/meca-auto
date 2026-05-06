from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Add etab info to all templates
    @app.before_request
    def add_etab_info():
        from app.models import Parametre
        g.etab_nom = Parametre.get('etab_nom', '')
        g.etab_adresse = Parametre.get('etab_adresse', '')
        g.etab_tel = Parametre.get('etab_tel', '')
        g.etab_email = Parametre.get('etab_email', '')

    from app.routes import register_routes
    register_routes(app)

    return app