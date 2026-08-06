"""
Conexión de solo lectura a cines.db para el backend.

El backend NUNCA escribe en la base de datos: solo el scraper lo hace.
La ruta de la base se configura con la variable de entorno CINES_DB_PATH,
o por defecto busca "cines.db" en el directorio desde el que se ejecuta uvicorn.
"""

import os
import sqlite3

DB_PATH = os.environ.get("CINES_DB_PATH", "cines.db")


def get_conn():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"No se encontró la base de datos en '{DB_PATH}'. "
            f"Define CINES_DB_PATH o coloca cines.db en el directorio de trabajo."
        )
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn