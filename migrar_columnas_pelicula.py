"""
Migración puntual: agrega a la tabla `peliculas` las columnas nuevas de
enriquecimiento (sinopsis, director, actores, trailer_url, tmdb_id).

Se corre UNA SOLA VEZ, sobre una cines.db que ya existe (creada antes de
este cambio). Si la columna ya existe, la salta sin error.

Uso:
    python migrar_columnas_pelicula.py
"""

from db import get_conn

COLUMNAS_NUEVAS = {
    "sinopsis": "TEXT",
    "director": "TEXT",
    "actores": "TEXT",
    "trailer_url": "TEXT",
    "tmdb_id": "INTEGER",
}


def main():
    conn = get_conn()
    existentes = {
        fila["name"] for fila in conn.execute("PRAGMA table_info(peliculas)")
    }

    for columna, tipo in COLUMNAS_NUEVAS.items():
        if columna in existentes:
            print(f"  - {columna}: ya existe, se omite")
            continue
        conn.execute(f"ALTER TABLE peliculas ADD COLUMN {columna} {tipo}")
        print(f"  - {columna}: agregada")

    conn.commit()
    conn.close()
    print("Migración completa.")


if __name__ == "__main__":
    main()
    
    