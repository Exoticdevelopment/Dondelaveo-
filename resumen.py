import sqlite3

conn = sqlite3.connect("cines.db")
print("Cines:", conn.execute("SELECT COUNT(*) FROM cines").fetchone()[0])
print("Peliculas:", conn.execute("SELECT COUNT(*) FROM peliculas").fetchone()[0])
print("Funciones:", conn.execute("SELECT COUNT(*) FROM funciones").fetchone()[0])
print("Precios guardados:", conn.execute("SELECT COUNT(*) FROM precios").fetchone()[0])
