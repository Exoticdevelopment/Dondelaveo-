"""
Esquema y funciones de acceso a la base de datos del comparador de cines.

Uso:
    from db import get_conn, crear_tablas, upsert_cine, upsert_pelicula, upsert_funcion, upsert_precio
"""

import sqlite3

DB_PATH = "cines.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # permite lecturas/escrituras concurrentes
    conn.execute("PRAGMA journal_mode = WAL")
    # espera si otro hilo tiene el lock
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def crear_tablas():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS cines (
        id INTEGER PRIMARY KEY,
        nombre TEXT NOT NULL,
        ciudad TEXT NOT NULL,
        latitud REAL,
        longitud REAL,
        company_id TEXT,
        slug TEXT,
        cadena TEXT
    );

  CREATE TABLE IF NOT EXISTS peliculas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        slug TEXT UNIQUE,
        duracion_min INTEGER,
        clasificacion TEXT,
        genero TEXT,
        cover_image_url TEXT
    );

    CREATE TABLE IF NOT EXISTS funciones (
        session_id INTEGER PRIMARY KEY,
        cine_id INTEGER NOT NULL REFERENCES cines(id),
        pelicula_id INTEGER NOT NULL REFERENCES peliculas(id),
        fecha TEXT NOT NULL,
        hora TEXT NOT NULL,
        formato TEXT,
        idioma TEXT,
        asientos_disponibles INTEGER
    );

    CREATE TABLE IF NOT EXISTS precios (
        session_id INTEGER PRIMARY KEY REFERENCES funciones(session_id),
        precio_cop INTEGER NOT NULL,
        actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


def upsert_cine(conn, id, nombre, ciudad, latitud, longitud, company_id, slug, cadena):
    conn.execute(
        """
        INSERT INTO cines (id, nombre, ciudad, latitud, longitud, company_id, slug, cadena)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nombre=excluded.nombre, ciudad=excluded.ciudad,
            latitud=excluded.latitud, longitud=excluded.longitud,
            company_id=excluded.company_id, slug=excluded.slug,
            cadena=excluded.cadena
    """,
        (id, nombre, ciudad, latitud, longitud, company_id, slug, cadena),
    )


def upsert_pelicula(
    conn, nombre, slug, duracion_min, clasificacion, genero, cover_image_url=None
):
    conn.execute(
        """
        INSERT INTO peliculas (nombre, slug, duracion_min, clasificacion, genero, cover_image_url)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            nombre=excluded.nombre, duracion_min=excluded.duracion_min,
            clasificacion=excluded.clasificacion, genero=excluded.genero,
            cover_image_url=COALESCE(excluded.cover_image_url, cover_image_url)
    """,
        (nombre, slug, duracion_min, clasificacion, genero, cover_image_url),
    )
    row = conn.execute("SELECT id FROM peliculas WHERE slug = ?", (slug,)).fetchone()
    return row["id"]


def upsert_funcion(
    conn,
    session_id,
    cine_id,
    pelicula_id,
    fecha,
    hora,
    formato,
    idioma,
    asientos_disponibles,
):
    conn.execute(
        """
        INSERT INTO funciones (session_id, cine_id, pelicula_id, fecha, hora, formato, idioma, asientos_disponibles)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            asientos_disponibles=excluded.asientos_disponibles
    """,
        (
            session_id,
            cine_id,
            pelicula_id,
            fecha,
            hora,
            formato,
            idioma,
            asientos_disponibles,
        ),
    )


def upsert_precio(conn, session_id, precio_cop):
    conn.execute(
        """
        INSERT INTO precios (session_id, precio_cop, actualizado_en)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id) DO UPDATE SET
            precio_cop=excluded.precio_cop, actualizado_en=CURRENT_TIMESTAMP
    """,
        (session_id, precio_cop),
    )


if __name__ == "__main__":
    crear_tablas()
    print(f"Base de datos creada en {DB_PATH}")
