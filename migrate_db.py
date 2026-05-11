"""
Script de migration complète de la base de données.
Ajoute toutes les colonnes manquantes sans toucher aux données existantes.
Usage : python migrate_db.py
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

MIGRATIONS = [
    # ── vehicules ──────────────────────────────────────────────────────────────
    "ALTER TABLE vehicules ADD COLUMN IF NOT EXISTS vin VARCHAR(17)",
    "ALTER TABLE vehicules ADD COLUMN IF NOT EXISTS energie VARCHAR(20)",
    "ALTER TABLE vehicules ADD COLUMN IF NOT EXISTS kilometrage INTEGER",
    "ALTER TABLE vehicules ADD COLUMN IF NOT EXISTS proprietaire_id INTEGER REFERENCES clients(id)",
    "ALTER TABLE vehicules ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",

    # ── vehicule_proprio_history ───────────────────────────────────────────────
    "CREATE TABLE IF NOT EXISTS vehicule_proprio_history ("
    "  id SERIAL PRIMARY KEY,"
    "  vehicule_id INTEGER NOT NULL REFERENCES vehicules(id),"
    "  client_id INTEGER NOT NULL REFERENCES clients(id),"
    "  date_debut TIMESTAMP DEFAULT NOW(),"
    "  date_fin TIMESTAMP"
    ")",

    # ── ordres_reparation ──────────────────────────────────────────────────────
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS client_recup_pieces BOOLEAN DEFAULT TRUE",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS client_recup_fluides BOOLEAN DEFAULT TRUE",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS montant_surcharge NUMERIC(10,2) DEFAULT 0",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS classe_nom VARCHAR(50)",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS eleve_nom VARCHAR(100)",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS eleve_id INTEGER REFERENCES users(id)",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS pas_de_facturation BOOLEAN DEFAULT FALSE",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS attente_pieces BOOLEAN DEFAULT FALSE",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS date_attente_pieces TIMESTAMP",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS remarque_attente TEXT",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS rdv_date_heure TIMESTAMP",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS rdv_titre VARCHAR(100)",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS ct_valide BOOLEAN DEFAULT FALSE",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS assurance_valide BOOLEAN DEFAULT FALSE",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS date_ouverture TIMESTAMP",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS date_cloture TIMESTAMP",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS date_facture TIMESTAMP",
    "ALTER TABLE ordres_reparation ADD COLUMN IF NOT EXISTS mode_tarif VARCHAR(20) DEFAULT 'forfait'",

    # ── eleve_interventions ────────────────────────────────────────────────────
    "ALTER TABLE eleve_interventions ADD COLUMN IF NOT EXISTS fourniture_id INTEGER REFERENCES fournitures(id)",
    "ALTER TABLE eleve_interventions ADD COLUMN IF NOT EXISTS quantite INTEGER DEFAULT 1",
    "ALTER TABLE eleve_interventions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",

    # ── factures ───────────────────────────────────────────────────────────────
    "ALTER TABLE factures ADD COLUMN IF NOT EXISTS mode_tarif VARCHAR(20)",
    "ALTER TABLE factures ADD COLUMN IF NOT EXISTS details TEXT",
    "ALTER TABLE factures ADD COLUMN IF NOT EXISTS send_by_email BOOLEAN DEFAULT FALSE",

    # ── etats_lieux ────────────────────────────────────────────────────────────
    "ALTER TABLE etats_lieux ADD COLUMN IF NOT EXISTS responsable VARCHAR(100)",
    "ALTER TABLE etats_lieux ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",

    # ── users ──────────────────────────────────────────────────────────────────
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS security_question VARCHAR(200)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS security_answer VARCHAR(200)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS classe_id INTEGER REFERENCES classes(id)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",

    # ── nouvelles tables ───────────────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS controles_visuels (
        id SERIAL PRIMARY KEY,
        or_id INTEGER NOT NULL REFERENCES ordres_reparation(id),
        controle_data TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        created_by INTEGER REFERENCES users(id)
    )""",

    """CREATE TABLE IF NOT EXISTS checklist_items (
        id SERIAL PRIMARY KEY,
        nom VARCHAR(200) NOT NULL,
        description TEXT,
        actif BOOLEAN DEFAULT TRUE,
        ordre INTEGER DEFAULT 0
    )""",

    """CREATE TABLE IF NOT EXISTS checklist_verifications (
        id SERIAL PRIMARY KEY,
        or_id INTEGER NOT NULL REFERENCES ordres_reparation(id),
        checklist_item_id INTEGER NOT NULL REFERENCES checklist_items(id),
        verified BOOLEAN DEFAULT FALSE,
        verified_at TIMESTAMP DEFAULT NOW(),
        verified_by INTEGER REFERENCES users(id)
    )""",

    """CREATE TABLE IF NOT EXISTS rendez_vous (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL REFERENCES clients(id),
        vehicule_id INTEGER REFERENCES vehicules(id),
        titre VARCHAR(100) NOT NULL,
        description TEXT,
        date_heure TIMESTAMP NOT NULL,
        duree INTEGER DEFAULT 60,
        statut VARCHAR(20) DEFAULT 'planifie',
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT NOW()
    )""",

    """CREATE TABLE IF NOT EXISTS recup_surcharges (
        id SERIAL PRIMARY KEY,
        nom VARCHAR(100) NOT NULL,
        description TEXT,
        montant NUMERIC(10,2) NOT NULL,
        actif BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    )""",

    """CREATE TABLE IF NOT EXISTS consommables (
        id SERIAL PRIMARY KEY,
        nom VARCHAR(100) NOT NULL,
        unite VARCHAR(20) DEFAULT 'pcs',
        prix_unitaire NUMERIC(10,2),
        stock NUMERIC(10,2) DEFAULT 0,
        actif BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    )""",

    """CREATE TABLE IF NOT EXISTS archives (
        id SERIAL PRIMARY KEY,
        year INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        file_path VARCHAR(255),
        description TEXT
    )""",
]

def run():
    with app.app_context():
        ok = 0
        errors = []
        with db.engine.connect() as conn:
            for sql in MIGRATIONS:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    ok += 1
                except Exception as e:
                    err = str(e).split('\n')[0]
                    errors.append(f"⚠️  {err}")

        print(f"\n✅ {ok}/{len(MIGRATIONS)} migrations appliquées")
        if errors:
            print(f"\n⚠️  {len(errors)} avertissement(s) (généralement sans gravité) :")
            for e in errors:
                print(f"   {e}")
        print("\n🎉 Base de données à jour !")

if __name__ == '__main__':
    run()
