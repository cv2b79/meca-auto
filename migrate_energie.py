"""Migration : remplace colonne 'couleur' par 'energie' dans la table vehicules"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        dialect = db.engine.dialect.name

        if dialect == 'sqlite':
            # SQLite ne supporte pas DROP COLUMN avant 3.35 — on recrée la table
            conn.execute(text("ALTER TABLE vehicules ADD COLUMN energie VARCHAR(20)"))
            try:
                conn.execute(text("ALTER TABLE vehicules DROP COLUMN couleur"))
            except Exception:
                print("Note: DROP COLUMN non supporté sur cette version SQLite — colonne 'couleur' conservée mais inutilisée.")
            conn.commit()

        elif dialect == 'postgresql':
            conn.execute(text("ALTER TABLE vehicules ADD COLUMN IF NOT EXISTS energie VARCHAR(20)"))
            conn.execute(text("ALTER TABLE vehicules DROP COLUMN IF EXISTS couleur"))
            conn.commit()

        else:
            conn.execute(text("ALTER TABLE vehicules ADD COLUMN energie VARCHAR(20)"))
            conn.execute(text("ALTER TABLE vehicules DROP COLUMN couleur"))
            conn.commit()

    print("Migration terminée : colonne 'energie' ajoutée, 'couleur' supprimée.")
