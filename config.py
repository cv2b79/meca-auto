import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Utiliser SQLite en local (dev), PostgreSQL en prod
    db_url = os.getenv('DATABASE_URL', '')
    if db_url:
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        basedir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(basedir, "instance", "mecaauto.db")}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SMTP_HOST = os.getenv('SMTP_HOST', '')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM = os.getenv('SMTP_FROM', 'atelier@lycee.fr')

    ETABLISSEMENT_NOM = os.getenv('ETABLISSEMENT_NOM', 'Lycée Professionnel')
    ETABLISSEMENT_ADRESSE = os.getenv('ETABLISSEMENT_ADRESSE', '')
    ETABLISSEMENT_TEL = os.getenv('ETABLISSEMENT_TEL', '')
    ETABLISSEMENT_EMAIL = os.getenv('ETABLISSEMENT_EMAIL', '')

    TARIF_HORAIRE = 45.00

    @classmethod
    def init_app(cls, app):
        pass