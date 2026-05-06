def register_routes(app):
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.clients import clients_bp
    from app.routes.vehicules import vehicules_bp
    from app.routes.ordres import ordres_bp
    from app.routes.factures import factures_bp
    from app.routes.data import data_bp
    from app.routes.settings import settings_bp
    from app.routes.agenda import agenda_bp
    from app.routes.stats import stats_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(clients_bp, url_prefix='/clients')
    app.register_blueprint(vehicules_bp, url_prefix='/vehicules')
    app.register_blueprint(ordres_bp, url_prefix='/ordres')
    app.register_blueprint(factures_bp, url_prefix='/factures')
    app.register_blueprint(data_bp, url_prefix='/data')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(agenda_bp, url_prefix='/agenda')
    app.register_blueprint(stats_bp, url_prefix='/stats')