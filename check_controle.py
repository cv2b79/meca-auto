import sqlite3
conn = sqlite3.connect('instance/mecaauto.db')
cur = conn.cursor()
for row in cur.execute("SELECT id, or_id, controle_data FROM controles_visuels"):
    print(row)