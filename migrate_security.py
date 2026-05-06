import sqlite3
conn = sqlite3.connect('instance/mecaauto.db')
cur = conn.cursor()
cur.execute("ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0")
cur.execute("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP")
conn.commit()
print("Colonnes ajoutées")