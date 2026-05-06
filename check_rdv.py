import sqlite3
conn = sqlite3.connect('instance/mecaauto.db')
cur = conn.cursor()
print("RDV dans la DB:")
for row in cur.execute("SELECT id, titre, date_heure, created_by FROM rendez_vous"):
    print(row)