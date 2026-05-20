from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
from datetime import timedelta

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Sécurité session ──────────────────────────────────────
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    app.config['SESSION_COOKIE_HTTPONLY']    = True   # inaccessible au JS
    app.config['SESSION_COOKIE_SAMESITE']    = 'Lax'  # protection CSRF basique
    # Activer uniquement si HTTPS est configuré :
    import os
    if os.getenv('FLASK_ENV') == 'production':
        app.config['SESSION_COOKIE_SECURE'] = True    # cookie uniquement sur HTTPS

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Add etab info to all templates
    @app.before_request
    def add_etab_info():
        from app.models import Parametre
        g.etab_nom     = Parametre.get('etab_nom', '')
        g.etab_adresse = Parametre.get('etab_adresse', '')
        g.etab_tel     = Parametre.get('etab_tel', '')
        g.etab_email   = Parametre.get('etab_email', '')
        g.etab_siren   = Parametre.get('etab_siren', '')
        g.etab_logo    = Parametre.get('etab_logo', '')

    # ── Headers de sécurité HTTP ─────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options']  = 'nosniff'
        response.headers['X-Frame-Options']          = 'SAMEORIGIN'
        response.headers['X-XSS-Protection']         = '1; mode=block'
        response.headers['Referrer-Policy']           = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy']        = 'geolocation=(), microphone=(), camera=()'
        return response

    from app.routes import register_routes
    register_routes(app)

    # ── Auto-migration colonnes manquantes ────────────────────
    # Ajoute les nouvelles colonnes sans bloquer si elles existent déjà.
    with app.app_context():
        try:
            from sqlalchemy import text, inspect as sa_inspect
            _inspector = sa_inspect(db.engine)
            _migrations = {
                'ordres_reparation': [
                    ("depollution_offerte", "BOOLEAN DEFAULT FALSE"),
                ],
                'factures': [
                    ("statut_paiement", "VARCHAR(20) DEFAULT 'en_attente'"),
                ],
            }
            with db.engine.connect() as _conn:
                for _table, _cols in _migrations.items():
                    _existing = [c['name'] for c in _inspector.get_columns(_table)]
                    for _col, _coltype in _cols:
                        if _col not in _existing:
                            _conn.execute(text(
                                f"ALTER TABLE {_table} ADD COLUMN {_col} {_coltype}"
                            ))
                            import sys
                            print(f"[AUTO-MIGRATE] {_table}.{_col} ajoutée", file=sys.stderr)
                _conn.commit()
        except Exception as _e:
            import sys
            print(f"[AUTO-MIGRATE] Erreur: {_e}", file=sys.stderr)

    return app