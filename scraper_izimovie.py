"""
Scraper de Izi Movie (Cali) — corre sobre la plataforma "Cinexo" que usa
este cine independiente. A diferencia de Cinemark, Cinexo no tiene un
endpoint limpio para el precio: hay que cargar la página de compra y
"pescarlo" del HTML con una técnica de búsqueda de texto (regex).

Uso:
    python scraper_izimovie.py
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


def con_reintentos(funcion, intentos=3, espera_inicial=2):
    """
    Recibe una función que hace una petición de red (por ejemplo,
    'obtener_precio') y devuelve una VERSIÓN NUEVA de esa misma función
    que, si falla, la vuelve a intentar sola antes de rendirse.

    Parámetros:
        funcion:         la función original que queremos hacer más resistente.
        intentos:        cuántas veces lo intenta en total antes de rendirse (por defecto 3).
        espera_inicial:  cuántos segundos espera después del primer fallo (por defecto 2).
                         Cada intento siguiente espera más tiempo que el anterior
                         (2s, luego 4s, luego 6s...), para no bombardear al servidor
                         si está teniendo un problema temporal.
    """

    def envoltorio(*args, **kwargs):
        for intento in range(1, intentos + 1):
            try:
                return funcion(*args, **kwargs)
            except Exception as e:
                if intento == intentos:
                    raise
                espera = espera_inicial * intento
                print(f"  [REINTENTO {intento}/{intentos}] fallo, esperando {espera}s: {e}")
                time.sleep(espera)

    return envoltorio


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.izi.movie/",
    "Origin": "https://www.izi.movie",
    "Accept": "application/json, text/plain, */*",
}

ID_COMPLEJO = "1002"  # Izi Movie, visto en la petición capturada
CADENA = "Izi Movie"
DIAS_A_CONSULTAR = 7  # mismo criterio que Cinemark: hoy + 6 días más
PAUSA_ENTRE_PETICIONES = 0.3  # un poco más conservador que Cinemark, es un sitio más chico


def obtener_cartelera(fecha_ddmmyyyy):
    """
    Trae películas + funciones (sin precio) para una fecha dada.
    fecha_ddmmyyyy debe venir como "06/08/2026" (día/mes/año).
    """
    url = "https://apifront.cinexo.com.ar/mobile/consultas/peliculas/PeliculasConFuncionesYHorarios"
    params = {"idComplejo": ID_COMPLEJO, "fecha": fecha_ddmmyyyy}
    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def extraer_tarifas_de_pagina_compra(html):
    """
    El precio no viene en ningún endpoint de API limpio: hay que cargar
    la página de compra (HTML) y extraerlo de un bloque de datos interno
    que usa Next.js para "hidratar" la página (protocolo llamado
    "React Server Components Flight"). Ese bloque contiene texto tipo:

        self.__next_f.push([1, "18:...\"tarifas\":[{...\"precio\":\"7500\"...}]..."])

    Esta función busca todos esos fragmentos, los "desescapa" (porque
    vienen codificados como si fueran un string de JSON), y saca de ahí
    el arreglo "tarifas" con los precios.
    """
    fragmentos = re.findall(
        r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', html
    )

    texto_completo = ""
    for frag in fragmentos:
        try:
            texto_completo += json.loads('"' + frag + '"')
        except json.JSONDecodeError:
            continue

    match = re.search(r'"tarifas":(\[.*?\])(?=,"|\})', texto_completo)
    if not match:
        return []

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return []


def obtener_precio_de_funcion(id_funcion, id_pelicula):
    """
    Carga la página de compra de una función específica y extrae el
    precio de la tarifa "general" (la más cara de las disponibles;
    descarta promocionales/club, que suelen ser más baratas).
    """
    url = "https://www.izi.movie/es-AR/compra"
    params = {"cid": ID_COMPLEJO, "fid": id_funcion, "pid": id_pelicula}
    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()

    tarifas = extraer_tarifas_de_pagina_compra(response.text)
    if not tarifas:
        return None

    candidatas = [t for t in tarifas if t.get("precio")]
    if not candidatas:
        return None
    tarifa = max(candidatas, key=lambda t: int(t["precio"]))
    return int(tarifa["precio"])


def procesar_fecha(fecha_iso):
    """Procesa un día completo: cartelera + funciones + precio de cada función."""
    fecha_ddmmyyyy = "/".join(
        reversed(fecha_iso.split("-"))
    )  # "2026-08-06" -> "06/08/2026"

    conn = get_conn()

    upsert_cine(
        conn,
        id=int(ID_COMPLEJO),
        nombre="Izi Movie",
        ciudad="Cali",
        latitud=None,
        longitud=None,
        company_id=ID_COMPLEJO,
        slug="izi-movie",
        cadena=CADENA,
    )
    conn.commit()

    try:
        # NUEVO: envuelto con con_reintentos() — si falla por un problema
        # de red pasajero, lo reintenta solo antes de rendirse de verdad.
        cartelera = con_reintentos(obtener_cartelera)(fecha_ddmmyyyy)
    except requests.RequestException as e:
        print(f"  [ERROR] No se pudo obtener cartelera de Izi Movie ({fecha_iso}): {e}")
        conn.close()
        return

    datos = cartelera.get("data", {})
    peliculas_raw = datos.get("datos", [])
    funciones_raw = datos.get("funciones", [])

    codigo_a_pelicula_id = {}
    for pelicula in peliculas_raw:
        pelicula_id = upsert_pelicula(
            conn,
            nombre=pelicula["peliculas_nombre"].strip(),
            slug="izi-" + pelicula["peliculas_codigo"],
            duracion_min=(
                int(pelicula["peliculas_duracion"])
                if pelicula.get("peliculas_duracion")
                else None
            ),
            clasificacion=pelicula.get("peliculas_clasificacion"),
            genero=pelicula.get("peliculas_genero"),
            cover_image_url=pelicula.get("imagen"),
        )
        conn.commit()
        codigo_a_pelicula_id[pelicula["peliculas_codigo"]] = pelicula_id

    procesadas = 0
    for funcion in funciones_raw:
        codigo_pelicula = funcion["codPelicula"]
        pelicula_id = codigo_a_pelicula_id.get(codigo_pelicula)
        if pelicula_id is None:
            continue

        session_id = int(funcion["_id"])
        upsert_funcion(
            conn,
            session_id=session_id,
            cine_id=int(ID_COMPLEJO),
            pelicula_id=pelicula_id,
            fecha=fecha_iso,
            hora=funcion["hora"] + ":00",
            formato=funcion.get("formato"),
            idioma="SUB" if funcion.get("subtitulada") == "1" else "DOB",
            asientos_disponibles=None,
        )
        conn.commit()

        try:
            # NUEVO: mismo tratamiento de reintentos para el precio.
            precio = con_reintentos(obtener_precio_de_funcion)(session_id, codigo_pelicula)
            if precio:
                upsert_precio(conn, session_id, precio)
                conn.commit()
        except requests.RequestException as e:
            print(f"    [ERROR] No se pudo obtener precio de función {session_id}: {e}")

        procesadas += 1
        time.sleep(PAUSA_ENTRE_PETICIONES)

    print(
        f"  OK: Izi Movie ({fecha_iso}) — {len(peliculas_raw)} películas, {procesadas} funciones procesadas"
    )
    conn.close()


def main():
    crear_tablas()
    fechas = [
        (date.today() + timedelta(days=i)).isoformat() for i in range(DIAS_A_CONSULTAR)
    ]

    print(
        f"Procesando Izi Movie para {len(fechas)} días ({fechas[0]} a {fechas[-1]})...\n"
    )
    for fecha_iso in fechas:
        procesar_fecha(fecha_iso)

    print("\nListo. Datos de Izi Movie guardados en cines.db")


if __name__ == "__main__":
    main()