from datetime import datetime
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    prenom = db.Column(db.String(50), nullable=False)
    login = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='eleve')
    actif = db.Column(db.Boolean, default=True)
    security_question = db.Column(db.String(200))
    security_answer = db.Column(db.String(200))
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    must_change_password = db.Column(db.Boolean, default=False)
    classe_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    classe = db.relationship('Classe', backref='eleves', lazy='joined')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    interventions = db.relationship('EleveIntervention', backref='eleve', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role in ['ddfpt', 'admin']

    def has_permission(self, perm):
        perms = {
            'ddfpt': ['create_or', 'edit_or', 'delete_or', 'facturer', 'see_stats', 'manage_settings', 'manage_users', 'manage_clients', 'manage_vehicules', 'edit_intervention', 'edit_etat_lieu', 'controle_visuel'],
            'magasinier': ['facturer', 'manage_settings', 'edit_etat_lieu', 'controle_visuel'],
            'enseignant': ['create_or', 'edit_or', 'manage_clients', 'manage_vehicules', 'edit_intervention', 'edit_etat_lieu', 'controle_visuel'],
            'eleve': ['edit_intervention', 'edit_etat_lieu', 'controle_visuel']
        }
        return perm in perms.get(self.role, [])

    def can_manage_settings(self):
        return self.has_permission('manage_settings')

    def can_create_or(self):
        return self.has_permission('create_or')

    def can_edit_or(self):
        return self.has_permission('edit_or')

    def can_delete_or(self):
        return self.has_permission('delete_or')

    def can_facturer(self):
        return self.has_permission('facturer')

    def can_see_stats(self):
        return self.has_permission('see_stats')
    
    def can_manage_users(self):
        return self.has_permission('manage_users')
    
    def can_manage_clients(self):
        return self.has_permission('manage_clients')
    
    def can_manage_vehicules(self):
        return self.has_permission('manage_vehicules')
    
    def can_edit_etat_lieu(self):
        return self.has_permission('edit_etat_lieu')
    
    def can_controle_visuel(self):
        return self.has_permission('controle_visuel')
    
    def can_delete(self):
        return self.role == 'ddfpt'

    def __repr__(self):
        return f'{self.prenom} {self.nom} ({self.role})'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    adresse = db.Column(db.String(255))
    telephone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vehicules = db.relationship('Vehicule', backref='proprietaire', lazy='dynamic', foreign_keys='Vehicule.proprietaire_id')

    def __repr__(self):
        return f'{self.prenom} {self.nom}'


class Vehicule(db.Model):
    __tablename__ = 'vehicules'

    id = db.Column(db.Integer, primary_key=True)
    immatriculation = db.Column(db.String(20), unique=True, nullable=False)
    marque = db.Column(db.String(50))
    modele = db.Column(db.String(50))
    annee = db.Column(db.Integer)
    vin = db.Column(db.String(17))
    couleur = db.Column(db.String(30))
    kilometrage = db.Column(db.Integer)
    proprietaire_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    historiques_proprio = db.relationship('VehiculeProprioHistory', backref='vehicule', lazy='dynamic', cascade='all, delete-orphan')
    ordres_reparation = db.relationship('OrdreReparation', backref='vehicule', lazy='dynamic')

    def __repr__(self):
        return f'{self.immatriculation} - {self.marque} {self.modele}'


class VehiculeProprioHistory(db.Model):
    __tablename__ = 'vehicule_proprio_history'

    id = db.Column(db.Integer, primary_key=True)
    vehicule_id = db.Column(db.Integer, db.ForeignKey('vehicules.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    date_debut = db.Column(db.DateTime, default=datetime.utcnow)
    date_fin = db.Column(db.DateTime)

    client = db.relationship('Client')


class OrdreReparation(db.Model):
    __tablename__ = 'ordres_reparation'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    vehicule_id = db.Column(db.Integer, db.ForeignKey('vehicules.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    description = db.Column(db.Text)
    statut = db.Column(db.String(20), default='ouvert')
    mode_tarif = db.Column(db.String(20), default='forfait')
    montant = db.Column(db.Numeric(10, 2))
    
    # Options dépollution
    client_recup_pieces = db.Column(db.Boolean, default=True)
    client_recup_fluides = db.Column(db.Boolean, default=True)
    montant_surcharge = db.Column(db.Numeric(10, 2), default=0)
    
    # Classe et élève (optionnels)
    classe_nom = db.Column(db.String(50))
    eleve_nom = db.Column(db.String(100))
    eleve_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    eleve = db.relationship('User', foreign_keys=[eleve_id], lazy='joined')
    
    # Pas de facturation
    pas_de_facturation = db.Column(db.Boolean, default=False)
    
    # Attente pièces
    attente_pieces = db.Column(db.Boolean, default=False)
    date_attente_pieces = db.Column(db.DateTime)
    remarque_attente = db.Column(db.Text)
    
    # Rendez-vous planifié
    rdv_date_heure = db.Column(db.DateTime)
    rdv_titre = db.Column(db.String(100))
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by_user = db.relationship('User', foreign_keys=[created_by], lazy='joined')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    date_ouverture = db.Column(db.DateTime, default=datetime.utcnow)
    date_cloture = db.Column(db.DateTime)
    date_facture = db.Column(db.DateTime)

    interventions_eleves = db.relationship('EleveIntervention', backref='ordre', lazy='dynamic', cascade='all, delete-orphan')
    etats_lieux = db.relationship('etat_lieu', backref='ordre', lazy='dynamic', cascade='all, delete-orphan')
    facture = db.relationship('Facture', backref='ordre', uselist=False)
    client = db.relationship('Client', backref='ordres')

    @staticmethod
    def generer_numero():
        now = datetime.now()
        year = now.year
        week = now.isocalendar()[1]
        last_or = OrdreReparation.query.filter(
            db.extract('year', OrdreReparation.created_at) == year,
            OrdreReparation.numero.like(f'{year}-S{week:02d}%')
        ).order_by(OrdreReparation.numero.desc()).first()

        if last_or:
            try:
                num = int(last_or.numero.split('-')[-1]) + 1
            except:
                num = 1
        else:
            num = 1

        return f'{year}-S{week:02d}-{num:03d}'

    def __repr__(self):
        return self.numero


class EleveIntervention(db.Model):
    __tablename__ = 'eleve_interventions'

    id = db.Column(db.Integer, primary_key=True)
    or_id = db.Column(db.Integer, db.ForeignKey('ordres_reparation.id'), nullable=False)
    eleve_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.Text)
    heures = db.Column(db.Numeric(5, 2), default=0)
    fourniture_id = db.Column(db.Integer, db.ForeignKey('fournitures.id'))
    fourniture = db.relationship('Fourniture', backref='interventions')
    quantite = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Facture(db.Model):
    __tablename__ = 'factures'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    or_id = db.Column(db.Integer, db.ForeignKey('ordres_reparation.id'), unique=True)
    montant = db.Column(db.Numeric(10, 2), nullable=False)
    mode_tarif = db.Column(db.String(20))
    details = db.Column(db.Text)
    emitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    send_by_email = db.Column(db.Boolean, default=False)

    @staticmethod
    def generer_numero(or_obj):
        return or_obj.numero


class etat_lieu(db.Model):
    __tablename__ = 'etats_lieux'

    id = db.Column(db.Integer, primary_key=True)
    or_id = db.Column(db.Integer, db.ForeignKey('ordres_reparation.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    kilometrage = db.Column(db.Integer)
    niveau_carburant = db.Column(db.String(20))
    dommages = db.Column(db.Text)
    observations = db.Column(db.Text)
    responsable = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.type} - {self.or_id}'


class ControleVisuel(db.Model):
    __tablename__ = 'controles_visuels'
    
    id = db.Column(db.Integer, primary_key=True)
    or_id = db.Column(db.Integer, db.ForeignKey('ordres_reparation.id'), nullable=False)
    controle_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    ordre = db.relationship('OrdreReparation', backref='controle_visuel')
    creator = db.relationship('User', backref='controles')


class Forfait(db.Model):
    __tablename__ = 'forfaits'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    montant = db.Column(db.Numeric(10, 2), nullable=False)
    actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'{self.nom} ({self.montant}€)'


class Fourniture(db.Model):
    __tablename__ = 'fournitures'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prix_unitaire = db.Column(db.Numeric(10, 2), default=0)
    actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return self.nom


class Enseignant(db.Model):
    __tablename__ = 'enseignants'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    telephone = db.Column(db.String(20))
    actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'{self.prenom} {self.nom}'


class Classe(db.Model):
    __tablename__ = 'classes'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False, unique=True)
    niveau = db.Column(db.String(20))
    actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return self.nom


class RecupSurcharge(db.Model):
    __tablename__ = 'recup_surcharges'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    montant = db.Column(db.Numeric(10, 2), nullable=False)
    actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'{self.nom} ({self.montant}€)'


class Consumable(db.Model):
    __tablename__ = 'consommables'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    unite = db.Column(db.String(20), default='pcs')
    prix_unitaire = db.Column(db.Numeric(10, 2))
    stock = db.Column(db.Numeric(10, 2), default=0)
    actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'{self.nom} ({self.stock} {self.unite})'


class Parametre(db.Model):
    __tablename__ = 'parametres'

    id = db.Column(db.Integer, primary_key=True)
    cle = db.Column(db.String(50), unique=True, nullable=False)
    valeur = db.Column(db.Text)

    @staticmethod
    def get(key, default=None):
        param = Parametre.query.filter_by(cle=key).first()
        return param.valeur if param else default

    @staticmethod
    def set(key, value):
        param = Parametre.query.filter_by(cle=key).first()
        if param:
            param.valeur = value
        else:
            param = Parametre(cle=key, valeur=value)
            db.session.add(param)
        db.session.commit()


class Archive(db.Model):
    __tablename__ = 'archives'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(255))
    description = db.Column(db.Text)


class Log(db.Model):
    __tablename__ = 'logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', lazy='joined')
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def log(user, action, details=None, target_type=None, target_id=None):
        if user is None:
            return
        log_entry = Log(
            user_id=user.id,
            action=action,
            details=details,
            target_type=target_type,
            target_id=target_id
        )
        db.session.add(log_entry)
        db.session.commit()


class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    actif = db.Column(db.Boolean, default=True)
    ordre = db.Column(db.Integer, default=0)

    @staticmethod
    def get_active():
        return ChecklistItem.query.filter_by(actif=True).order_by(ChecklistItem.ordre).all()


class ChecklistVerification(db.Model):
    __tablename__ = 'checklist_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    or_id = db.Column(db.Integer, db.ForeignKey('ordres_reparation.id'), nullable=False)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey('checklist_items.id'), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    verified_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    checklist_item = db.relationship('ChecklistItem')


class RendezVous(db.Model):
    __tablename__ = 'rendez_vous'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    vehicule_id = db.Column(db.Integer, db.ForeignKey('vehicules.id'))
    titre = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    date_heure = db.Column(db.DateTime, nullable=False)
    duree = db.Column(db.Integer, default=60)  # minutes
    statut = db.Column(db.String(20), default='planifie')  # planifie, confirme, annule, termine
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    client = db.relationship('Client', backref='rendez_vous')
    vehicule = db.relationship('Vehicule', backref='rendez_vous')
    created_by_user = db.relationship('User', foreign_keys=[created_by])