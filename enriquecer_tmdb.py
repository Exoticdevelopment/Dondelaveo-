"""
Enriquece las películas que ya están en cines.db con datos que las cadenas
de cine NO traen: sinopsis, director, actores principales y trailer.

Fuente de datos: TMDB (The Movie Database, https://www.themoviedb.org/).

Requiere una API key de TMDB en la variable de entorno TMDB_API_KEY
(la tomamos de un archivo .env en la raíz del proyecto — nunca se escribe
la key directamente en este archivo).

Uso:
    python enriquecer_tmdb.py                 # todas las películas sin tmdb_id
    python enriquecer_tmdb.py --forzar-todas   # re-consulta incluso las que ya tienen tmdb_id
"""

import argparse
import os
import time

import requests
from dotenv import load_dotenv

from db import get_conn, upsert_pelicula

load_dotenv()

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"
PAUSA_ENTRE_PETICIONES = 0.25  # segundos, para no saturar la API gratuita
MAX_ACTORES = 5  # cuántos actores del reparto guardamos


def buscar_pelicula(nombre):
    """Busca una película por nombre en TMDB y devuelve el primer resultado (o None)."""
    respuesta = requests.get(
        f"{TMDB_BASE}/search/movie",
        params={"api_key": TMDB_API_KEY, "query": nombre, "language": "es-ES"},
        timeout=15,
    )
    respuesta.raise_for_status()
    resultados = respuesta.json().get("results", [])
    return resultados[0] if resultados else None


def obtener_detalle(tmdb_id):
    """Trae sinopsis + créditos (director, actores) + videos (trailer) en una sola llamada."""
    respuesta = requests.get(
        f"{TMDB_BASE}/movie/{tmdb_id}",
        params={
            "api_key": TMDB_API_KEY,
            "language": "es-ES",
            "append_to_response": "credits,videos",
        },
        timeout=15,
    )
    respuesta.raise_for_status()
    return respuesta.json()


def extraer_director(credits):
    return next(
        (persona["name"] for persona in credits.get("crew", []) if persona["job"] == "Director"),
        None,
    )


def extraer_actores(credits):
    reparto = credits.get("cast", [])[:MAX_ACTORES]
    return ", ".join(persona["name"] for persona in reparto) if reparto else None


def extraer_trailer_url(videos):
    trailer = next(
        (
            v
            for v in videos.get("results", [])
            if v.get("type") == "Trailer" and v.get("site") == "YouTube"
        ),
        None,
    )
    return f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else None

def resolver_cover_image_url(cover_image_url_scraper, detalle):
    """
    No todas las cadenas traen póster (ej. Cine Colombia nunca lo captura).
    Si el scraper no trajo imagen, usamos el póster de TMDB como respaldo
    para no dejar la tarjeta sin imagen en la app.
    """
    if cover_image_url_scraper:
        return cover_image_url_scraper
    poster_path = detalle.get("poster_path")
    return f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None


def enriquecer_una_pelicula(conn, pelicula_row):
    nombre = pelicula_row["nombre"]
    encontrada = buscar_pelicula(nombre)
    if not encontrada:
        print(f"  [SIN MATCH] '{nombre}' no se encontró en TMDB")
        return False

    detalle = obtener_detalle(encontrada["id"])
    credits = detalle.get("credits", {})
    videos = detalle.get("videos", {})

    upsert_pelicula(
        conn,
        nombre=pelicula_row["nombre"],
        slug=pelicula_row["slug"],
        duracion_min=pelicula_row["duracion_min"],
        clasificacion=pelicula_row["clasificacion"],
        genero=pelicula_row["genero"],
        cover_image_url=resolver_cover_image_url(pelicula_row["cover_image_url"], detalle),
        sinopsis=detalle.get("overview") or None,
        director=extraer_director(credits),
        actores=extraer_actores(credits),
        trailer_url=extraer_trailer_url(videos),
        tmdb_id=encontrada["id"],
    )
    conn.commit()
    print(f"  [OK] '{nombre}' -> tmdb_id={encontrada['id']}")
    return True


def main(forzar_todas):
    if not TMDB_API_KEY:
        raise SystemExit(
            "No se encontró TMDB_API_KEY. Crea un archivo .env en la raíz del "
            "proyecto con la línea: TMDB_API_KEY=tu_key_aqui"
        )

    conn = get_conn()
    if forzar_todas:
        peliculas = conn.execute("SELECT * FROM peliculas").fetchall()
    else:
        peliculas = conn.execute(
            "SELECT * FROM peliculas WHERE tmdb_id IS NULL"
        ).fetchall()

    print(f"Enriqueciendo {len(peliculas)} película(s)...\n")

    exitosas = 0
    for pelicula in peliculas:
        try:
            if enriquecer_una_pelicula(conn, pelicula):
                exitosas += 1
        except requests.RequestException as e:
            print(f"  [ERROR] '{pelicula['nombre']}': {e}")
        time.sleep(PAUSA_ENTRE_PETICIONES)

    conn.close()
    print(f"\nListo. {exitosas}/{len(peliculas)} películas enriquecidas.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--forzar-todas",
        action="store_true",
        help="Re-consulta incluso películas que ya tienen tmdb_id guardado",
    )
    args = parser.parse_args()
    main(forzar_todas=args.forzar_todas)
    
    
    