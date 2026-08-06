"""
Scraper completo de Cinemark Colombia.

Recorre todas las ciudades y cines, descarga la cartelera de cada uno,
y guarda cines + películas + funciones + precio general en cines.db.

Uso:
    python scraper_completo.py                # todas las ciudades
    python scraper_completo.py --ciudad cali   # solo una ciudad
"""

import argparse
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import requests

from db import get_conn, crear_tablas, upsert_cine, upsert_pelicula, upsert_funcion, upsert_precio

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.cinemark.com.co/",
    "Origin": "https://www.cinemark.com.co",
    "Accept": "application/json, text/plain, */*",
    "Connectapitoken": "web-co-token",
}

PAUSA_ENTRE_PETICIONES = 0.2  # segundos, dentro de un mismo cine
CINES_EN_PARALELO = 6  # cuántos cines se procesan al mismo tiempo
print_lock = threading.Lock()


def log(msg):
    with print_lock:
        print(msg)


def obtener_cines():
    url = "https://api.cinemark-core.com/vista/country/co/cities-theaters"
    params = {
        "$format": "json",
        "$select": "ID,Name,PhoneNumber,Address1,Address2,Latitude,Longitude,City,LoyaltyCode",
    }
    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def obtener_cartelera(cinema_slug, company_id, fecha):
    url = f"https://api.cinemark-core.com/vista/country/co/theater/{cinema_slug}"
    params = {
        "date": fecha,
        "companyId": company_id,
        "midnightSessionStart": "23:10",
        "midnightSessionEnd": "03:00",
    }
    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def obtener_precio_general(cinema_id, session_id, company_id):
    url = f"https://api.cinemark-core.com/vista/country/co/cinemas/{cinema_id}/sessions/{session_id}/tickets"
    params = {
        "timestamp": int(time.time() * 1000),
        "$format": "json",
        "salesChannelFilter": "SUNDW",
        "userSessionId": uuid.uuid4().hex[:26],
        "companyId": company_id,
    }
    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    data = response.json()

    candidatos = [
        t for t in data.get("Tickets", [])
        if not t["IsAvailableForLoyaltyMembersOnly"]
        and not t["IsPackageTicket"]
        and not t["BinDetails"]
        and t["PriceInCents"] > 0
    ]
    if not candidatos:
        return None
    boleta_general = max(candidatos, key=lambda t: len(t["SalesChannels"]))
    return boleta_general["PriceInCents"] / 100


def slugify(nombre):
    """Convierte el nombre de un cine en el slug que usa la URL (aproximado)."""
    return (
        nombre.lower()
        .replace(" ", "-")
        .replace("é", "e").replace("í", "i").replace("ó", "o")
        .replace("á", "a").replace("ú", "u").replace("ñ", "n")
    )


def procesar_cine(cine, ciudad_nombre, fecha):
    conn = get_conn()  # cada hilo necesita su propia conexión a SQLite
    cine_id = int(cine["ID"])
    company_id = "5db771be04daec00076df3f5"  # fijo, visto en todas las peticiones
    slug = cine.get("CinemaSlug") or slugify(cine["Name"])

    upsert_cine(
        conn, id=cine_id, nombre=cine["Name"], ciudad=ciudad_nombre,
        latitud=float(cine["Latitude"]) if cine["Latitude"] else None,
        longitud=float(cine["Longitude"]) if cine["Longitude"] else None,
        company_id=company_id, slug=slug,
    )
    conn.commit()

    try:
        cartelera = obtener_cartelera(slug, company_id, fecha)
    except requests.RequestException as e:
        log(f"    [ERROR] No se pudo obtener cartelera de {cine['Name']}: {e}")
        conn.close()
        return
    time.sleep(PAUSA_ENTRE_PETICIONES)

    for pelicula in cartelera.get("Movies", []):
        pelicula_id = upsert_pelicula(
            conn, nombre=pelicula["Name"].strip(), slug=pelicula["SlugName"],
            duracion_min=int(pelicula["Duration"]
                             ) if pelicula["Duration"] else None,
            clasificacion=pelicula.get("Rating"), genero=pelicula.get("GenreName"),
            cover_image_url=pelicula.get("CoverImageUrl"),
        )

        conn.commit()

        for formato in pelicula.get("Format", []):
            idioma = ",".join(formato.get("LangTypes", []))
            tipo_pantalla = ",".join(formato.get("ScreenTypes", []))

            for sesion in formato.get("Sessions", []):
                if not sesion.get("IsVisible"):
                    continue  # función oculta/no vendible, no vale la pena guardarla

                session_id = int(sesion["SessionId"])
                upsert_funcion(
                    conn, session_id=session_id, cine_id=cine_id, pelicula_id=pelicula_id,
                    fecha=fecha, hora=sesion["Showtime"], formato=tipo_pantalla,
                    idioma=idioma, asientos_disponibles=sesion.get(
                        "SeatsAvailable"),
                )
                conn.commit()

                try:
                    precio = obtener_precio_general(
                        cine_id, session_id, company_id)
                    if precio:
                        upsert_precio(conn, session_id, precio)
                        conn.commit()
                except requests.RequestException as e:
                    log(
                        f"    [ERROR] No se pudo obtener precio de sesión {session_id}: {e}")
                time.sleep(PAUSA_ENTRE_PETICIONES)

    log(f"    OK: {cine['Name']} ({ciudad_nombre}) — {len(cartelera.get('Movies', []))} películas procesadas")
    conn.close()


DIAS_A_CONSULTAR = 7  # hoy + 6 días más, para detectar preventas


def main(ciudad_filtro=None):
    crear_tablas()
    fechas = [(date.today() + timedelta(days=i)).isoformat()
              for i in range(DIAS_A_CONSULTAR)]

    print("Descargando lista de ciudades y cines...")
    ciudades = obtener_cines()

    tareas = []  # lista de (cine, ciudad_nombre, fecha) a procesar
    for ciudad in ciudades:
        if ciudad_filtro and ciudad["CitySlug"].lower() != ciudad_filtro.lower():
            continue
        for cine in ciudad["Theaters"]:
            for fecha in fechas:
                tareas.append((cine, ciudad["Name"], fecha))

    print(
        f"Procesando {len(tareas)} combinaciones cine+fecha con {CINES_EN_PARALELO} en paralelo...\n")
    print(f"({len(fechas)} días: {fechas[0]} a {fechas[-1]})\n")

    with ThreadPoolExecutor(max_workers=CINES_EN_PARALELO) as executor:
        futuros = [executor.submit(procesar_cine, cine, ciudad_nombre, fecha)
                   for cine, ciudad_nombre, fecha in tareas]
        for futuro in as_completed(futuros):
            futuro.result()  # relanza cualquier excepción no capturada, para verla

    print("\nListo. Datos guardados en cines.db")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ciudad", help="Slug de ciudad, ej: cali (opcional, si no se pasa recorre todas)")
    args = parser.parse_args()
    main(ciudad_filtro=args.ciudad)
