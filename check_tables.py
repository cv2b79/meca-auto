import sqlite3
conn = sqlite3.connect('instance/mecaauto.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%controle%'")
print([r[0] for r in cur.fetchall()])