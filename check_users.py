import sqlite3
conn = sqlite3.connect('instance/mecaauto.db')
cur = conn.cursor()
print("Nombre d'enregistrements:", cur.execute("SELECT COUNT(*) FROM enseignants").fetchone()[0])
print("Liste:")
for row in cur.execute("SELECT id, nom, prenom, actif FROM enseignants"):
    print(row)