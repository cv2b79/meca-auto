"""
╔══════════════════════════════════════════════════════════════╗
║         MECA AUTO — Script de migration définitif            ║
║  Synchronise le schéma PostgreSQL avec les modèles actuels   ║
║  Idempotent : peut être relancé autant de fois que voulu     ║
║  Usage : python migrate_db.py                                ║
╚══════════════════════════════════════════════════════════════╝
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

# ──────────────────────────────────────────────────────────────
# ÉTAPE 1 : Création des tables manquantes
# (dans l'ordre des dépendances FK)
# ──────────────────────────────────────────────────────────────
CREATE_TABLES = [
    # classes (pas de FK sortante)
    """CREATE TABLE IF NOT EXISTS classes (
        id          SERIAL PRIMARY KEY,
        nom         VARCHAR(50) NOT NULL UNIQUE,
        niveau      VARCHAR(20),
        actif       BOOLEAN DEFAULT TRUE,
        created_at  TIMESTAMP DEFAULT NOW()
    )""",

    # clients
    """CREATE TABLE IF NOT EXISTS clients (
        id          SERIAL PRIMARY KEY,
        nom         VARCHAR(100) NOT NULL,
        prenom      VARCHAR(100) NOT NULL,
        adresse     VARCHAR(255),
        telephone   VARCHAR(20),
        email       VARCHAR(100),
        created_at  TIMESTAMP DEFAULT NOW(),
        updated_at  TIMESTAMP DEFAULT NOW()
    )""",

    # users (dépend de classes)
    """CREATE TABLE IF NOT EXISTS users (
        id                   SERIAL PRIMARY KEY,
        nom                  VARCHAR(50) NOT NULL,
        prenom               VARCHAR(50) NOT NULL,
        login                VARCHAR(20) NOT NULL UNIQUE,
        email                VARCHAR(100),
        password_hash        VARCHAR(255) NOT NULL,
        role                 VARCHAR(20) NOT NULL DEFAULT 'eleve',
        actif                BOOLEAN DEFAULT TRUE,
        security_question    VARCHAR(200),
        security_answer      VARCHAR(200),
        failed_attempts      INTEGER DEFAULT 0,
        locked_until         TIMESTAMP,
        must_change_password BOOLEAN DEFAULT FALSE,
        classe_id            INTEGER REFERENCES classes(id),
        created_at           TIMESTAMP DEFAULT NOW(),
        updated_at           TIMESTAMP DEFAULT NOW()
    )""",

    # vehicules (dépend de clients)
    """CREATE TABLE IF NOT EXISTS vehicules (
        id               SERIAL PRIMARY KEY,
        immatriculation  VARCHAR(20) NOT NULL UNIQUE,
        marque           VARCHAR(50),
        modele           VARCHAR(50),
        annee            INTEGER,
        vin              VARCHAR(17),
        energie          VARCHAR(20),
        kilometrage      INTEGER,
        proprietaire_id  INTEGER REFERENCES clients(id),
        created_at       TIMESTAMP DEFAULT NOW(),
        updated_at       TIMESTAMP DEFAULT NOW()
    )""",

    # historique propriétaires
    """CREATE TABLE IF NOT EXISTS vehicule_proprio_history (
        id          SERIAL PRIMARY KEY,
        vehicule_id INTEGER NOT NULL REFERENCES vehicules(id) ON DELETE CASCADE,
        client_id   INTEGER NOT NULL REFERENCES clients(id),
        date_debut  TIMESTAMP DEFAULT NOW(),
        date_fin    TIMESTAMP
    )""",

    # ordres_reparation (dépend de vehicules, clients, users)
    """CREATE TABLE IF NOT EXISTS ordres_reparation (
        id                   SERIAL PRIMARY KEY,
        numero               VARCHAR(20) NOT NULL UNIQUE,
        vehicule_id          INTEGER NOT NULL REFERENCES vehicules(id),
        client_id            INTEGER NOT NULL REFERENCES clients(id),
        description          TEXT,
        statut               VARCHAR(20) DEFAULT 'ouvert',
        mode_tarif           VARCHAR(20) DEFAULT 'forfait',
        montant              NUMERIC(10,2),
        client_recup_pieces  BOOLEAN DEFAULT TRUE,
        client_recup_fluides BOOLEAN DEFAULT TRUE,
        montant_surcharge    NUMERIC(10,2) DEFAULT 0,
        classe_nom           VARCHAR(50),
        eleve_nom            VARCHAR(100),
        eleve_id             INTEGER REFERENCES users(id),
        pas_de_facturation   BOOLEAN DEFAULT FALSE,
        attente_pieces       BOOLEAN DEFAULT FALSE,
        date_attente_pieces  TIMESTAMP,
        remarque_attente     TEXT,
        rdv_date_heure       TIMESTAMP,
        rdv_titre            VARCHAR(100),
        ct_valide            BOOLEAN DEFAULT FALSE,
        assurance_valide     BOOLEAN DEFAULT FALSE,
        created_by           INTEGER REFERENCES users(id),
        created_at           TIMESTAMP DEFAULT NOW(),
        updated_at           TIMESTAMP DEFAULT NOW(),
        date_ouverture       TIMESTAMP DEFAULT NOW(),
        date_cloture         TIMESTAMP,
        date_facture         TIMESTAMP
    )""",

    # fournitures
    """CREATE TABLE IF NOT EXISTS fournitures (
        id            SERIAL PRIMARY KEY,
        nom           VARCHAR(100) NOT NULL,
        prix_unitaire NUMERIC(10,2) DEFAULT 0,
        actif         BOOLEAN DEFAULT TRUE,
        created_at    TIMESTAMP DEFAULT NOW()
    )""",

    # interventions élèves (dépend de ordres_reparation, users, fournitures)
    """CREATE TABLE IF NOT EXISTS eleve_interventions (
        id             SERIAL PRIMARY KEY,
        or_id          INTEGER NOT NULL REFERENCES ordres_reparation(id) ON DELETE CASCADE,
        eleve_id       INTEGER NOT NULL REFERENCES users(id),
        description    TEXT,
        heures         NUMERIC(5,2) DEFAULT 0,
        fourniture_id  INTEGER REFERENCES fournitures(id),
        quantite       INTEGER DEFAULT 1,
        created_at     TIMESTAMP DEFAULT NOW(),
        updated_at     TIMESTAMP DEFAULT NOW()
    )""",

    # factures
    """CREATE TABLE IF NOT EXISTS factures (
        id           SERIAL PRIMARY KEY,
        numero       VARCHAR(20) NOT NULL UNIQUE,
        or_id        INTEGER UNIQUE REFERENCES ordres_reparation(id),
        montant      NUMERIC(10,2) NOT NULL,
        mode_tarif   VARCHAR(20),
        details      TEXT,
        emitted_at   TIMESTAMP DEFAULT NOW(),
        send_by_email BOOLEAN DEFAULT FALSE
    )""",

    # états des lieux
    """CREATE TABLE IF NOT EXISTS etats_lieux (
        id               SERIAL PRIMARY KEY,
        or_id            INTEGER NOT NULL REFERENCES ordres_reparation(id) ON DELETE CASCADE,
        type             VARCHAR(10) NOT NULL,
        kilometrage      INTEGER,
        niveau_carburant VARCHAR(20),
        dommages         TEXT,
        observations     TEXT,
        responsable      VARCHAR(100),
        created_at       TIMESTAMP DEFAULT NOW()
    )""",

    # contrôles visuels
    """CREATE TABLE IF NOT EXISTS controles_visuels (
        id          SERIAL PRIMARY KEY,
        or_id       INTEGER NOT NULL REFERENCES ordres_reparation(id) ON DELETE CASCADE,
        controle_data TEXT,
        created_at  TIMESTAMP DEFAULT NOW(),
        created_by  INTEGER REFERENCES users(id)
    )""",

    # forfaits
    """CREATE TABLE IF NOT EXISTS forfaits (
        id          SERIAL PRIMARY KEY,
        nom         VARCHAR(100) NOT NULL,
        description TEXT,
        montant     NUMERIC(10,2) NOT NULL,
        actif       BOOLEAN DEFAULT TRUE,
        created_at  TIMESTAMP DEFAULT NOW(),
        updated_at  TIMESTAMP DEFAULT NOW()
    )""",

    # enseignants
    """CREATE TABLE IF NOT EXISTS enseignants (
        id         SERIAL PRIMARY KEY,
        nom        VARCHAR(100) NOT NULL,
        prenom     VARCHAR(100) NOT NULL,
        email      VARCHAR(120),
        telephone  VARCHAR(20),
        actif      BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    )""",

    # frais dépollution
    """CREATE TABLE IF NOT EXISTS recup_surcharges (
        id          SERIAL PRIMARY KEY,
        nom         VARCHAR(100) NOT NULL,
        description TEXT,
        montant     NUMERIC(10,2) NOT NULL,
        actif       BOOLEAN DEFAULT TRUE,
        created_at  TIMESTAMP DEFAULT NOW()
    )""",

    # consommables
    """CREATE TABLE IF NOT EXISTS consommables (
        id            SERIAL PRIMARY KEY,
        nom           VARCHAR(100) NOT NULL,
        unite         VARCHAR(20) DEFAULT 'pcs',
        prix_unitaire NUMERIC(10,2),
        stock         NUMERIC(10,2) DEFAULT 0,
        actif         BOOLEAN DEFAULT TRUE,
        created_at    TIMESTAMP DEFAULT NOW()
    )""",

    # paramètres
    """CREATE TABLE IF NOT EXISTS parametres (
        id     SERIAL PRIMARY KEY,
        cle    VARCHAR(50) NOT NULL UNIQUE,
        valeur TEXT
    )""",

    # archives
    """CREATE TABLE IF NOT EXISTS archives (
        id          SERIAL PRIMARY KEY,
        year        INTEGER NOT NULL,
        created_at  TIMESTAMP DEFAULT NOW(),
        file_path   VARCHAR(255),
        description TEXT
    )""",

    # logs
    """CREATE TABLE IF NOT EXISTS logs (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        action      VARCHAR(100) NOT NULL,
        details     TEXT,
        target_type VARCHAR(50),
        target_id   INTEGER,
        created_at  TIMESTAMP DEFAULT NOW()
    )""",

    # checklist items
    """CREATE TABLE IF NOT EXISTS checklist_items (
        id          SERIAL PRIMARY KEY,
        nom         VARCHAR(200) NOT NULL,
        description TEXT,
        actif       BOOLEAN DEFAULT TRUE,
        ordre       INTEGER DEFAULT 0
    )""",

    # checklist vérifications
    """CREATE TABLE IF NOT EXISTS checklist_verifications (
        id                SERIAL PRIMARY KEY,
        or_id             INTEGER NOT NULL REFERENCES ordres_reparation(id) ON DELETE CASCADE,
        checklist_item_id INTEGER NOT NULL REFERENCES checklist_items(id),
        verified          BOOLEAN DEFAULT FALSE,
        verified_at       TIMESTAMP DEFAULT NOW(),
        verified_by       INTEGER REFERENCES users(id)
    )""",

    # rendez-vous
    """CREATE TABLE IF NOT EXISTS rendez_vous (
        id          SERIAL PRIMARY KEY,
        client_id   INTEGER NOT NULL REFERENCES clients(id),
        vehicule_id INTEGER REFERENCES vehicules(id),
        titre       VARCHAR(100) NOT NULL,
        description TEXT,
        date_heure  TIMESTAMP NOT NULL,
        duree       INTEGER DEFAULT 60,
        statut      VARCHAR(20) DEFAULT 'planifie',
        created_by  INTEGER REFERENCES users(id),
        created_at  TIMESTAMP DEFAULT NOW()
    )""",

    # sessions de travail
    """CREATE TABLE IF NOT EXISTS sessions_travail (
        id               SERIAL PRIMARY KEY,
        or_id            INTEGER NOT NULL REFERENCES ordres_reparation(id) ON DELETE CASCADE,
        enseignant_id    INTEGER NOT NULL REFERENCES users(id),
        date_session     TIMESTAMP NOT NULL,
        classe_nom       VARCHAR(50),
        eleves_presents  TEXT,
        zone_vehicule    VARCHAR(50),
        observations     TEXT,
        certified_at     TIMESTAMP,
        created_at       TIMESTAMP DEFAULT NOW()
    )""",

    # incidents
    """CREATE TABLE IF NOT EXISTS incidents (
        id               SERIAL PRIMARY KEY,
        or_id            INTEGER NOT NULL REFERENCES ordres_reparation(id) ON DELETE CASCADE,
        declared_by      INTEGER NOT NULL REFERENCES users(id),
        validated_by     INTEGER REFERENCES users(id),
        validated_at     TIMESTAMP,
        statut           VARCHAR(20) DEFAULT 'en_attente',
        type_incident    VARCHAR(30) NOT NULL,
        description      TEXT NOT NULL,
        objets_concernes TEXT,
        date_constat     TIMESTAMP NOT NULL,
        created_at       TIMESTAMP DEFAULT NOW()
    )""",
]

# ──────────────────────────────────────────────────────────────
# ÉTAPE 2 : Ajout des colonnes manquantes (ALTER TABLE IF NOT EXISTS)
# Pour les tables qui existaient avant et n'avaient pas toutes les colonnes
# ──────────────────────────────────────────────────────────────
ADD_COLUMNS = [
    # users
    ("users", "email",                "VARCHAR(100)"),
    ("users", "security_question",    "VARCHAR(200)"),
    ("users", "security_answer",      "VARCHAR(200)"),
    ("users", "failed_attempts",      "INTEGER DEFAULT 0"),
    ("users", "locked_until",         "TIMESTAMP"),
    ("users", "must_change_password", "BOOLEAN DEFAULT FALSE"),
    ("users", "classe_id",            "INTEGER REFERENCES classes(id)"),
    ("users", "updated_at",           "TIMESTAMP"),

    # clients
    ("clients", "adresse",    "VARCHAR(255)"),
    ("clients", "updated_at", "TIMESTAMP DEFAULT NOW()"),

    # vehicules
    ("vehicules", "vin",             "VARCHAR(17)"),
    ("vehicules", "energie",         "VARCHAR(20)"),
    ("vehicules", "kilometrage",     "INTEGER"),
    ("vehicules", "proprietaire_id", "INTEGER REFERENCES clients(id)"),
    ("vehicules", "updated_at",      "TIMESTAMP"),

    # ordres_reparation
    ("ordres_reparation", "mode_tarif",           "VARCHAR(20) DEFAULT 'forfait'"),
    ("ordres_reparation", "client_recup_pieces",  "BOOLEAN DEFAULT TRUE"),
    ("ordres_reparation", "client_recup_fluides", "BOOLEAN DEFAULT TRUE"),
    ("ordres_reparation", "montant_surcharge",    "NUMERIC(10,2) DEFAULT 0"),
    ("ordres_reparation", "classe_nom",           "VARCHAR(50)"),
    ("ordres_reparation", "eleve_nom",            "VARCHAR(100)"),
    ("ordres_reparation", "eleve_id",             "INTEGER REFERENCES users(id)"),
    ("ordres_reparation", "pas_de_facturation",   "BOOLEAN DEFAULT FALSE"),
    ("ordres_reparation", "attente_pieces",       "BOOLEAN DEFAULT FALSE"),
    ("ordres_reparation", "date_attente_pieces",  "TIMESTAMP"),
    ("ordres_reparation", "remarque_attente",     "TEXT"),
    ("ordres_reparation", "rdv_date_heure",       "TIMESTAMP"),
    ("ordres_reparation", "rdv_titre",            "VARCHAR(100)"),
    ("ordres_reparation", "ct_valide",            "BOOLEAN DEFAULT FALSE"),
    ("ordres_reparation", "assurance_valide",     "BOOLEAN DEFAULT FALSE"),
    ("ordres_reparation", "created_by",           "INTEGER REFERENCES users(id)"),
    ("ordres_reparation", "updated_at",           "TIMESTAMP"),
    ("ordres_reparation", "date_ouverture",       "TIMESTAMP"),
    ("ordres_reparation", "date_cloture",         "TIMESTAMP"),
    ("ordres_reparation", "date_facture",         "TIMESTAMP"),

    # eleve_interventions
    ("eleve_interventions", "fourniture_id", "INTEGER REFERENCES fournitures(id)"),
    ("eleve_interventions", "quantite",      "INTEGER DEFAULT 1"),
    ("eleve_interventions", "updated_at",    "TIMESTAMP"),

    # factures
    ("factures", "mode_tarif",       "VARCHAR(20)"),
    ("factures", "details",          "TEXT"),
    ("factures", "send_by_email",    "BOOLEAN DEFAULT FALSE"),
    ("factures", "statut_paiement",  "VARCHAR(20) DEFAULT 'en_attente'"),

    # etats_lieux
    ("etats_lieux", "responsable",        "VARCHAR(100)"),
    ("etats_lieux", "created_at",         "TIMESTAMP DEFAULT NOW()"),
    ("etats_lieux", "inventaire_objets",  "TEXT"),
    ("etats_lieux", "inventaire_signe",   "BOOLEAN DEFAULT FALSE"),
]


def run():
    print("\n╔══════════════════════════════════════════════╗")
    print("║     MECA AUTO — Migration base de données    ║")
    print("╚══════════════════════════════════════════════╝\n")

    tables_ok = 0
    tables_skip = 0
    cols_ok = 0
    cols_skip = 0
    errors = []

    with app.app_context():
        with db.engine.connect() as conn:

            # — Étape 1 : tables —
            print("▶ Création des tables manquantes...")
            for sql in CREATE_TABLES:
                table_name = sql.split("EXISTS")[1].strip().split()[0].strip("(").strip()
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    # Vérifie si la table existait déjà (IF NOT EXISTS ne lève pas d'erreur)
                    result = conn.execute(text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name=:t"
                    ), {"t": table_name}).scalar()
                    tables_ok += 1
                    print(f"  ✅ {table_name}")
                except Exception as e:
                    errors.append(f"Table {table_name}: {str(e).split(chr(10))[0]}")
                    print(f"  ❌ {table_name}: {str(e).split(chr(10))[0]}")

            # — Étape 2 : colonnes —
            print("\n▶ Ajout des colonnes manquantes...")
            for table, col, col_type in ADD_COLUMNS:
                # Vérifie si la colonne existe déjà
                exists = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
                ), {"t": table, "c": col}).scalar()

                if exists:
                    cols_skip += 1
                    print(f"  ⏭  {table}.{col} (déjà présente)")
                else:
                    try:
                        conn.execute(text(
                            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
                        ))
                        conn.commit()
                        cols_ok += 1
                        print(f"  ✅ {table}.{col} ajoutée")
                    except Exception as e:
                        errors.append(f"Colonne {table}.{col}: {str(e).split(chr(10))[0]}")
                        print(f"  ❌ {table}.{col}: {str(e).split(chr(10))[0]}")

    # — Résumé —
    print("\n╔══════════════════════════════════════════════╗")
    print(f"║  Tables  : {tables_ok} traitées                       ")
    print(f"║  Colonnes: {cols_ok} ajoutées, {cols_skip} déjà présentes          ")
    if errors:
        print(f"║  Erreurs : {len(errors)}                               ")
    print("╚══════════════════════════════════════════════╝")

    if errors:
        print("\n⚠️  Erreurs rencontrées :")
        for e in errors:
            print(f"   • {e}")
    else:
        print("\n🎉 Base de données entièrement à jour !")


if __name__ == '__main__':
    run()
