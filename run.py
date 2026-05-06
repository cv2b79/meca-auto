from app import create_app, db
from app.models import User, Forfait, Parametre

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Forfait': Forfait, 'Parametre': Parametre}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        if User.query.count() == 0:
            admin = User(nom='Admin', prenom='DDFPT', login='admin', role='ddfpt')
            admin.set_password('admin123')
            db.session.add(admin)

            forfaits = [
                Forfait(nom='Vidange', description='Vidange moteur + filtre', montant=45),
                Forfait(nom='Pneumatiques', description='Montage équilibrage', montant=35),
                Forfait(nom='Freinage', description='Freins AV ou AR', montant=60),
            ]
            for f in forfaits:
                db.session.add(f)

            db.session.commit()
            print('Base initialisée: admin / admin123')

    app.run(host='0.0.0.0', port=5000, debug=True)