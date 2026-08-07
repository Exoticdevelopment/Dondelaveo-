"""
Scraper de Cine Colombia — corre sobre "Vista OCAPI" (Omni-Channel API),
una plataforma estándar usada por cines en más de 80 países, con
documentación pública en https://developer.vista.co

A diferencia de Cinemark e Izi Movie, aquí SÍ pudimos confirmar los
endpoints reales contra la documentación oficial, no solo por prueba
y error.

Requiere un token temporal (dura ~12 horas) que se extrae de cualquier
página de selección de asientos del sitio — no requiere iniciar sesión
con una cuenta real, es un token de "invitado" genérico.

Uso:
    python scraper_cinecolombia.py
"""

import json
import re
import time
from datetime import date, timedelta

import requests

from db import (
    get_conn,
    crear_tablas,
    upsert_cine,
    upsert_pelicula,
    upsert_funcion,
    upsert_precio,
)

API_BASE = "https://digital-api.cinecolombia.com/ocapi/v1"
CADENA = "Cine Colombia"
CIUDAD_OBJETIVO = "Cali"  # por ahora solo Cali; se puede ampliar después
DIAS_A_CONSULTAR = 7
PAUSA_ENTRE_PETICIONES = 0.3

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.cinecolombia.com/",
}


def obtener_token():
    """
    El token no viene de un login real: cualquier página de selección de
    asientos del sitio lo trae incrustado en su HTML (dentro de un bloque
    <script id="__NEXT_DATA__">, como JSON). Usamos una función/cine
    cualquiera conocido solo para "sacarle" el token — no compramos nada.
    """
    url = "https://multiplex.cinecolombia.com/order/showtimes/6162-13117/seats"
    response = requests.get(url, headers=HEADERS_BASE, timeout=15)
    response.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text, re.DOTALL
    )
    if not match:
        raise RuntimeError(
            "No se encontró el bloque __NEXT_DATA__ en la página de asientos"
        )

    datos = json.loads(match.group(1))
    token = datos["props"]["pageProps"]["environment"]["gasToken"]
    return token


def obtener_sitios(token):
    """GET /sites — trae TODOS los cines de Cine Colombia en el país."""
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/sites", headers=headers, timeout=15)
    response.raise_for_status()
    return response.json().get("sites", [])


def obtener_peliculas_de_sitio(token, site_id):
    """GET /sites/{siteId}/films — películas en cartelera en un cine específico."""
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE}/sites/{site_id}/films", headers=headers, timeout=15
    )
    response.raise_for_status()
    return response.json()


def obtener_horarios(token, film_id, site_ids, fecha_iso):
    """GET /showtimes/by-business-date/{fecha} — horarios de una película en varios cines."""
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    params = [("filmIds", film_id)] + [("siteIds", sid) for sid in site_ids]
    response = requests.get(
        f"{API_BASE}/showtimes/by-business-date/{fecha_iso}",
        headers=headers,
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def obtener_precio(token, showtime_id):
    """
    GET /showtimes/{id}/ticket-prices — precios de una función.
    Tomamos el ticket "isDefault: true" sin restricciones de membresía
    (descarta tarjetas de club, puntos, etc.), igual criterio que usamos
    con Cinemark e Izi Movie.
    """
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE}/showtimes/{showtime_id}/ticket-prices", headers=headers, timeout=15
    )
    response.raise_for_status()
    data = response.json()

    candidatos = [
        t
        for t in data.get("ticketPrices", [])
        if t.get("isDefault") and not t.get("restrictions")
    ]
    if not candidatos:
        return None
    return candidatos[0]["price"]["valueIncludingTax"]


def main():
    crear_tablas()

    print("Consiguiendo token de acceso...")
    token = obtener_token()
    print("Token obtenido correctamente.\n")

    print("Descargando lista de cines...")
    sitios = obtener_sitios(token)
    sitios_cali = [
        s
        for s in sitios
        if CIUDAD_OBJETIVO.lower()
        in s.get("contactDetails", {}).get("address", {}).get("city", "").lower()
    ]
    print(f"Encontrados {len(sitios_cali)} cines en {CIUDAD_OBJETIVO}.\n")

    conn = get_conn()
    for sitio in sitios_cali:
        site_id = sitio["id"]
        nombre = sitio["name"]["text"]
        ciudad = sitio["contactDetails"]["address"]["city"].split(",")[0].strip()
        lat = sitio.get("location", {}).get("latitude")
        lon = sitio.get("location", {}).get("longitude")

        upsert_cine(
            conn,
            id=int(site_id),
            nombre=nombre,
            ciudad=ciudad,
            latitud=lat,
            longitud=lon,
            company_id=site_id,
            slug=f"cinecolombia-{site_id}",
            cadena=CADENA,
        )
        conn.commit()

    fechas = [
        (date.today() + timedelta(days=i)).isoformat() for i in range(DIAS_A_CONSULTAR)
    ]

    for sitio in sitios_cali:
        site_id = sitio["id"]
        nombre = sitio["name"]["text"]

        try:
            peliculas_data = obtener_peliculas_de_sitio(token, site_id)
        except requests.RequestException as e:
            print(f"  [ERROR] No se pudo obtener películas de {nombre}: {e}")
            continue

        films_relacionados = {f["id"]: f for f in peliculas_data.get("films", [])}
        film_ids = list(films_relacionados.keys())

        procesadas = 0
        for film_id in film_ids:
            pelicula_info = films_relacionados[film_id]
            print(f"    Procesando: {pelicula_info['title']['text']}")
            pelicula_id_local = upsert_pelicula(
                conn,
                nombre=pelicula_info["title"]["text"].strip(),
                slug="cinecolombia-" + film_id,
                duracion_min=pelicula_info.get("runtimeInMinutes"),
                clasificacion=None,
                genero=None,
                cover_image_url=None,
            )
            conn.commit()

            for fecha_iso in fechas:
                try:
                    horarios = obtener_horarios(token, film_id, [site_id], fecha_iso)
                except requests.RequestException as e:
                    print(f"    [ERROR] Horarios de {film_id} en {fecha_iso}: {e}")
                    continue

                for funcion in horarios.get("showtimes", []):
                    showtime_id = funcion["id"]
                    inicio = funcion["schedule"]["startsAt"]
                    hora = inicio.split("T")[1][:8]
                    session_id_local = (
                        hash(showtime_id) & 0x7FFFFFFF
                    )  # id no numérico -> hash estable

                    upsert_funcion(
                        conn,
                        session_id=session_id_local,
                        cine_id=int(site_id),
                        pelicula_id=pelicula_id_local,
                        fecha=fecha_iso,
                        hora=hora,
                        formato=None,
                        idioma=None,
                        asientos_disponibles=None,
                    )
                    conn.commit()

                    try:
                        precio = obtener_precio(token, showtime_id)
                        if precio:
                            upsert_precio(conn, session_id_local, int(precio))
                            conn.commit()
                    except requests.RequestException as e:
                        print(f"      [ERROR] Precio de {showtime_id}: {e}")

                    procesadas += 1
                    time.sleep(PAUSA_ENTRE_PETICIONES)

        print(
            f"  OK: {nombre} — {len(film_ids)} películas, {procesadas} funciones procesadas"
        )

    conn.close()
    print("\nListo. Datos de Cine Colombia guardados en cines.db")


if __name__ == "__main__":
    main()
