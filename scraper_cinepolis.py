#!/usr/bin/env python3
"""
Scraper completo de Cinepolis Colombia.

Recorre todas las ciudades y cines, descarga la cartelera de cada uno,
y guarda cines + películas + funciones + precio general en cines.db.

Uso:
    python scraper_cinepolis.py                # todas las ciudades
    python scraper_cinepolis.py --ciudad cali  # solo una ciudad
"""
import argparse
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse
import re
import json

import requests
from bs4 import BeautifulSoup

# IMPORTA las funciones de tu repo (mismo contrato que el scraper de Cinemark)
from db import (
    get_conn,
    crear_tablas,
    upsert_cine,
    upsert_pelicula,
    upsert_funcion,
    upsert_precio,
)

# Opciones configurables
BASE_SITE = "https://cinepolis.com.co"
CARTELERA_PAGE = "https://cinepolis.com.co/cartelera/cali-colombia"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CarteleraScraper/1.0; +https://tusitio.example)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": CARTELERA_PAGE,
}
PAUSA_ENTRE_PETICIONES = 0.25
CINES_EN_PARALELO = 6
DIAS_A_CONSULTAR = 7
print_lock = threading.Lock()


def log(msg):
    with print_lock:
        print(msg)


def con_reintentos(funcion, intentos=3, espera_inicial=2):
    def envoltorio(*args, **kwargs):
        for intento in range(1, intentos + 1):
            try:
                return funcion(*args, **kwargs)
            except Exception as e:
                if intento == intentos:
                    raise
                espera = espera_inicial * intento
                log(f"    [REINTENTO {intento}/{intentos}] fallo, esperando {espera}s: {e}")
                time.sleep(espera)
    return envoltorio


def descubrir_endpoint_json(cartelera_url=CARTELERA_PAGE):
    """
    Intenta encontrar un endpoint JSON en el HTML de la página de cartelera.
    Busca patrones comunes (/api/, /showtimes, /theaters, /sessions) dentro de scripts.
    Devuelve la URL completa si la encuentra, o None.
    """
    resp = requests.get(cartelera_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.text

    # Buscar URLs JSON en scripts o en llamadas XHR embebidas
    posibles = set()
    # 1) URLs absolutas/relativas en el HTML que contengan palabras clave
    for match in re.findall(r'["\'](\/?api[^\s"\'<>]+)["\']', html, flags=re.IGNORECASE):
        posibles.add(urljoin(BASE_SITE, match))
    for match in re.findall(r'["\'](\/?showtimes[^\s"\'<>]+)["\']', html, flags=re.IGNORECASE):
        posibles.add(urljoin(BASE_SITE, match))
    for match in re.findall(r'["\'](\/?theaters[^\s"\'<>]+)["\']', html, flags=re.IGNORECASE):
        posibles.add(urljoin(BASE_SITE, match))
    for match in re.findall(r'fetch\(["\'](\/?[^\)]+)["\']', html, flags=re.IGNORECASE):
        posibles.add(urljoin(BASE_SITE, match))

    # 2) Buscar JSON embebido en <script type="application/ld+json"> o variables JS
    if not posibles:
        for script in re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.DOTALL | re.IGNORECASE):
            if "showtimes" in script.lower() or "theater" in script.lower():
                # intentar extraer URLs dentro del script
                for match in re.findall(r'["\'](https?:\/\/[^"\']+\.json)["\']', script):
                    posibles.add(match)

    # Validar candidatos haciendo una petición HEAD/GET ligera
    for url in posibles:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                # comprobar si parece JSON
                ct = r.headers.get("Content-Type", "")
                if "application/json" in ct or r.text.strip().startswith("{"):
                    log(f"  Endpoint JSON detectado: {url}")
                    return url
        except Exception:
            continue
    return None


def fetch_cartelera_api(endpoint, params=None):
    resp = requests.get(endpoint, headers=HEADERS, params=params or {}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_cartelera_json(data, ciudad_nombre, fecha):
    """
    Normaliza la respuesta JSON al esquema que usa tu BD.
    Este parser es flexible: intenta mapear campos comunes.
    """
    movies = []
    # Estructuras posibles: data["movies"], data["results"], data["data"]
    candidates = data.get("movies") or data.get("results") or data.get("data") or data
    # Si candidates es dict con keys por cine, iterar
    if isinstance(candidates, dict) and "theaters" in candidates:
        # estructura por teatro
        for theater in candidates.get("theaters", []):
            for m in theater.get("movies", []):
                movies.append((theater, m))
    elif isinstance(candidates, list):
        # lista de películas
        for m in candidates:
            movies.append((None, m))
    else:
        # fallback: intentar encontrar objetos movie dentro del JSON
        for k, v in data.items():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and ("title" in item or "name" in item):
                        movies.append((None, item))

    normalized = []
    for theater, raw in movies:
        # extraer campos comunes
        title = raw.get("title") or raw.get("name")
        slug = raw.get("slug") or raw.get("id") or raw.get("movieId")
        duration = raw.get("duration") or raw.get("runtime")
        cover = raw.get("poster") or raw.get("posterUrl") or raw.get("image")
        if cover and cover.startswith("/"):
            cover = urljoin(BASE_SITE, cover)
        # showtimes puede estar en raw["showtimes"] o en formatos->sessions
        showtimes = []
        if raw.get("showtimes"):
            showtimes = raw.get("showtimes")
        elif raw.get("sessions"):
            showtimes = raw.get("sessions")
        elif raw.get("formats"):
            for f in raw.get("formats", []):
                for s in f.get("sessions", []):
                    showtimes.append(s)
        # si theater proviene del JSON, extraer info de sala
        theater_info = theater or {}
        normalized.append({
            "title": title,
            "slug": slug,
            "duration_min": int(duration) if duration else None,
            "cover_image_url": cover,
            "genres": raw.get("genres") or raw.get("genre"),
            "rating": raw.get("rating") or raw.get("classification"),
            "showtimes": showtimes,
            "theater": {
                "name": theater_info.get("name") or theater_info.get("theaterName"),
                "id": theater_info.get("id") or theater_info.get("theaterId"),
            },
            "raw": raw,
            "fecha": fecha,
            "ciudad": ciudad_nombre,
        })
    return normalized


def parse_cartelera_html_with_playwright(html, fecha, ciudad_nombre):
    """
    Parser HTML con BeautifulSoup para el fallback cuando no hay endpoint JSON.
    Ajusta selectores según la estructura real de Cinepolis.
    """
    soup = BeautifulSoup(html, "html.parser")
    movies = []
    for card in soup.select(".movie-card, .card--movie, .pelicula, .movie"):
        title_el = card.select_one(".movie-title, .title, h3")
        title = title_el.get_text(strip=True) if title_el else None
        slug = None
        poster_el = card.select_one("img")
        poster = poster_el["src"] if poster_el and poster_el.has_attr("src") else None
        if poster and poster.startswith("/"):
            poster = urljoin(BASE_SITE, poster)
        showtimes = [t.get_text(strip=True) for t in card.select(".showtime, .horario, .funcion")]
        movies.append({
            "title": title,
            "slug": slug,
            "duration_min": None,
            "cover_image_url": poster,
            "showtimes": showtimes,
            "theater": {"name": None, "id": None},
            "raw": None,
            "fecha": fecha,
            "ciudad": ciudad_nombre,
        })
    return movies


def render_page_playwright(url):
    """
    Renderiza la página con Playwright y devuelve HTML.
    """
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle")
        html = page.content()
        browser.close()
    return html


def obtener_lista_ciudades_y_cines(endpoint_json=None):
    """
    Intenta obtener la lista de ciudades y cines.
    - Si hay endpoint JSON conocido, usarlo.
    - Si no, parsear la página de cartelera para extraer cines (fallback).
    Devuelve una lista de dicts con keys: CitySlug, Name, Theaters (lista de cines).
    """
    # Intentar endpoint público (ejemplo heurístico)
    posibles_endpoints = []
    if endpoint_json:
        posibles_endpoints.append(endpoint_json)
    # endpoints heurísticos que podrían existir en Cinepolis
    posibles_endpoints.extend([
        urljoin(BASE_SITE, "/api/theaters"),
        urljoin(BASE_SITE, "/api/theaters/list"),
        urljoin(BASE_SITE, "/api/cities-theaters"),
        urljoin(BASE_SITE, "/showtimes/theaters"),
    ])
    for ep in posibles_endpoints:
        try:
            r = requests.get(ep, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Normalizar estructura mínima
                ciudades = []
                # Si la respuesta ya viene agrupada por ciudad
                if isinstance(data, list):
                    # suponer que es lista de cines o ciudades
                    # intentar detectar estructura: city -> theaters
                    for item in data:
                        if "CitySlug" in item or "City" in item or "city" in item:
                            ciudades.append(item)
                    if ciudades:
                        return ciudades
                elif isinstance(data, dict):
                    # buscar keys comunes
                    if "cities" in data:
                        return data["cities"]
                    if "theaters" in data and "cities" in data:
                        return data["cities"]
                    # fallback: construir una sola ciudad con theaters
                    if "theaters" in data:
                        return [{"CitySlug": "unknown", "Name": "Unknown", "Theaters": data["theaters"]}]
        except Exception:
            continue

    # Fallback: parsear la página de cartelera para extraer cines mínimos
    r = requests.get(CARTELERA_PAGE, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    # buscar selectores que contengan lista de cines/ciudades
    ciudades = []
    # ejemplo: <select id="city"> o lista de botones
    city_select = soup.select_one("select#city, select[name=city]")
    if city_select:
        for opt in city_select.select("option"):
            slug = opt.get("value")
            name = opt.get_text(strip=True)
            ciudades.append({"CitySlug": slug, "Name": name, "Theaters": []})
    # si no hay select, intentar extraer cines desde bloques
    if not ciudades:
        # buscar bloques de teatro
        for block in soup.select(".theater, .cinema, .sede"):
            name_el = block.select_one(".theater-name, .cinema-name, h3")
            name = name_el.get_text(strip=True) if name_el else None
            slug = None
            ciudades.append({"CitySlug": "unknown", "Name": "Unknown", "Theaters": [{"Name": name, "TheaterId": None}]})
    return ciudades


def slugify(nombre):
    return (
        nombre.lower()
        .replace(" ", "-")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("á", "a")
        .replace("ú", "u")
        .replace("ñ", "n")
    )


def obtener_precio_general_cinepolis(session_obj):
    """
    Heurística para obtener precio general desde un objeto de sesión.
    Si el JSON de Cinepolis incluye precios, extraer el ticket general.
    session_obj: dict con info de la sesión (puede variar).
    """
    # Estructuras posibles: session_obj["prices"], session_obj["tickets"], session_obj["price"]
    if not session_obj:
        return None
    # buscar lista de tickets
    for key in ("prices", "tickets", "priceList", "ticketTypes"):
        if key in session_obj and isinstance(session_obj[key], list):
            candidatos = []
            for t in session_obj[key]:
                # heurística: elegir ticket con Price > 0 y no exclusivo
                price = t.get("price") or t.get("PriceInCents") or t.get("amount")
                if price is None:
                    continue
                # normalizar cents
                if isinstance(price, int) and price > 1000:  # podría estar en cents
                    price_val = price / 100.0
                else:
                    price_val = float(price)
                candidatos.append(price_val)
            if candidatos:
                # devolver el máximo o el más común; aquí devolvemos el máximo razonable
                return max(candidatos)
    # si hay campo directo
    if "price" in session_obj:
        try:
            return float(session_obj["price"])
        except Exception:
            pass
    return None


def procesar_cine(cine, ciudad_nombre, fecha, endpoint_json=None):
    """
    Procesa un cine: guarda cine, recorre películas y funciones, obtiene precio general.
    """
    conn = get_conn()
    # intentar obtener identificadores del cine
    cine_id = None
    try:
        cine_id = int(cine.get("TheaterId") or cine.get("id") or cine.get("ID") or 0)
    except Exception:
        cine_id = None

    company_id = None  # Cinepolis puede no usar companyId; lo dejamos None
    slug = cine.get("slug") or cine.get("CinemaSlug") or (slugify(cine.get("Name") or cine.get("name") or "cine"))

    upsert_cine(
        conn,
        id=cine_id,
        nombre=cine.get("Name") or cine.get("name"),
        ciudad=ciudad_nombre,
        latitud=float(cine.get("Latitude")) if cine.get("Latitude") else None,
        longitud=float(cine.get("Longitude")) if cine.get("Longitude") else None,
        company_id=company_id,
        slug=slug,
        cadena="Cinepolis",
    )
    conn.commit()

    # Obtener cartelera: preferir endpoint JSON si existe
    cartelera_data = None
    if endpoint_json:
        try:
            # algunos endpoints requieren parámetros: city, date, theaterId...
            params = {"city": ciudad_nombre, "date": fecha}
            # si cine tiene id, pasar theaterId
            if cine.get("TheaterId") or cine.get("id"):
                params["theaterId"] = cine.get("TheaterId") or cine.get("id")
            cartelera_data = con_reintentos(fetch_cartelera_api)(endpoint_json, params=params)
        except Exception as e:
            log(f"    [WARN] fallo al usar endpoint JSON para {cine.get('Name')}: {e}")
            cartelera_data = None

    # Si no hay JSON, fallback a renderizado y parseo HTML
    peliculas_normalizadas = []
    if cartelera_data:
        peliculas_normalizadas = parse_cartelera_json(cartelera_data, ciudad_nombre, fecha)
    else:
        # construir URL de cartelera por cine si existe
        cine_url = cine.get("Url") or cine.get("url") or CARTELERA_PAGE
        try:
            html = render_page_playwright(cine_url)
            peliculas_normalizadas = parse_cartelera_html_with_playwright(html, fecha, ciudad_nombre)
        except Exception as e:
            log(f"    [ERROR] No se pudo renderizar página para {cine.get('Name')}: {e}")
            conn.close()
            return

    time.sleep(PAUSA_ENTRE_PETICIONES)

    # Guardar películas y funciones
    for pelicula in peliculas_normalizadas:
        try:
            pelicula_id = upsert_pelicula(
                conn,
                nombre=(pelicula.get("title") or "").strip(),
                slug=pelicula.get("slug") or None,
                duracion_min=pelicula.get("duration_min"),
                clasificacion=pelicula.get("rating"),
                genero=",".join(pelicula.get("genres") or []) if pelicula.get("genres") else None,
                cover_image_url=pelicula.get("cover_image_url"),
            )
            conn.commit()
        except Exception as e:
            log(f"    [ERROR] upsert_pelicula fallo para {pelicula.get('title')}: {e}")
            continue

        # iterar showtimes (estructura variable)
        for sesion in pelicula.get("showtimes") or []:
            # sesion puede ser string (hora) o dict con campos
            try:
                if isinstance(sesion, str):
                    hora = sesion
                    session_id = None
                else:
                    hora = sesion.get("time") or sesion.get("Showtime") or sesion.get("start") or sesion.get("hora")
                    session_id = sesion.get("sessionId") or sesion.get("SessionId") or sesion.get("id")
                upsert_funcion(
                    conn,
                    session_id=session_id,
                    cine_id=cine_id,
                    pelicula_id=pelicula_id,
                    fecha=fecha,
                    hora=hora,
                    formato=",".join(sesion.get("formats") or []) if isinstance(sesion, dict) else None,
                    idioma=",".join(sesion.get("languages") or []) if isinstance(sesion, dict) else None,
                    asientos_disponibles=sesion.get("seatsAvailable") if isinstance(sesion, dict) else None,
                )
                conn.commit()
                # intentar obtener precio general heurísticamente
                precio = None
                try:
                    precio = con_reintentos(obtener_precio_general_cinepolis)(sesion)
                    if precio:
                        upsert_precio(conn, session_id, precio)
                        conn.commit()
                except Exception as e:
                    log(f"    [WARN] No se pudo obtener precio para sesión {session_id}: {e}")
                time.sleep(PAUSA_ENTRE_PETICIONES)
            except Exception as e:
                log(f"    [ERROR] fallo procesando sesion para {pelicula.get('title')}: {e}")
                continue

    log(f"    OK: {cine.get('Name')} ({ciudad_nombre}) — {len(peliculas_normalizadas)} películas procesadas")
    conn.close()


def main(ciudad_filtro=None):
    crear_tablas()
    fechas = [(date.today() + timedelta(days=i)).isoformat() for i in range(DIAS_A_CONSULTAR)]

    log("Descubriendo endpoint JSON (si existe)...")
    endpoint = descubrir_endpoint_json()
    if endpoint:
        log(f"Usando endpoint JSON: {endpoint}")
    else:
        log("No se detectó endpoint JSON; se usará renderizado con Playwright como fallback.")

    log("Descargando lista de ciudades y cines...")
    ciudades = obtener_lista_ciudades_y_cines(endpoint_json=endpoint)

    tareas = []
    for ciudad in ciudades:
        if ciudad_filtro and (ciudad.get("CitySlug") or ciudad.get("City") or ciudad.get("Name")).lower() != ciudad_filtro.lower():
            continue
        for cine in ciudad.get("Theaters", []) or []:
            for fecha in fechas:
                tareas.append((cine, ciudad.get("Name") or ciudad.get("City") or "Unknown", fecha))

    log(f"Procesando {len(tareas)} combinaciones cine+fecha con {CINES_EN_PARALELO} en paralelo...\n")
    log(f"({len(fechas)} días: {fechas[0]} a {fechas[-1]})\n")

    with ThreadPoolExecutor(max_workers=CINES_EN_PARALELO) as executor:
        futuros = [executor.submit(procesar_cine, cine, ciudad_nombre, fecha, endpoint) for cine, ciudad_nombre, fecha in tareas]
        for futuro in as_completed(futuros):
            try:
                futuro.result()
            except Exception as e:
                log(f"[ERROR] tarea falló: {e}")

    log("\nListo. Datos guardados en cines.db")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ciudad", help="Slug de ciudad, ej: cali (opcional, si no se pasa recorre todas)")
    args = parser.parse_args()
    main(ciudad_filtro=args.ciudad)


