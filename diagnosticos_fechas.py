"""
Diagnostico: compara cuantas peliculas distintas aparecen en un cine
si consultas SOLO hoy, vs si consultas hoy + los proximos N dias.

Esto ayuda a confirmar si la diferencia entre lo que ves en la web
(ej. 12 peliculas en Cali, incluyendo preventas/estrenos) y lo que
guarda el scraper (2 peliculas en Cali) se debe a que la web agrega
varios dias + preventas, mientras el scraper solo pide "hoy".

Uso:
    python diagnostico_fechas.py --cine mallplaza --dias 10
"""

import argparse
import time
from datetime import date, timedelta

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.cinemark.com.co/",
    "Origin": "https://www.cinemark.com.co",
    "Accept": "application/json, text/plain, */*",
    "Connectapitoken": "web-co-token",
}
COMPANY_ID = "5db771be04daec00076df3f5"


def obtener_cartelera(cinema_slug, fecha):
    url = f"https://api.cinemark-core.com/vista/country/co/theater/{cinema_slug}"
    params = {
        "date": fecha,
        "companyId": COMPANY_ID,
        "midnightSessionStart": "23:10",
        "midnightSessionEnd": "03:00",
    }
    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def main(cine_slug, dias):
    peliculas_por_dia = {}
    todas_las_peliculas = {}  # slug -> nombre

    for i in range(dias):
        fecha = (date.today() + timedelta(days=i)).isoformat()
        try:
            data = obtener_cartelera(cine_slug, fecha)
        except requests.RequestException as e:
            print(f"  [ERROR] {fecha}: {e}")
            continue

        nombres = []
        for peli in data.get("Movies", []):
            slug = peli["SlugName"]
            nombres.append(peli["Name"].strip())
            todas_las_peliculas[slug] = peli["Name"].strip()

        peliculas_por_dia[fecha] = nombres
        print(f"{fecha}: {len(nombres)} peliculas -> {nombres}")
        time.sleep(0.3)

    print()
    print(f"=== TOTAL: {len(todas_las_peliculas)} peliculas distintas en {dias} dias ===")
    for slug, nombre in todas_las_peliculas.items():
        print(f"  - {nombre} ({slug})")

    print()
    print("Si este numero se acerca a lo que ves en la web (ej. 12 en Cali),")
    print("confirma que el problema es que el scraper solo mira 'hoy'.")
    print("Si SIGUE siendo mucho menor, puede que la web tambien este sumando")
    print("preventas sin fecha de funcion aun (revisar si el sitio tiene un")
    print("endpoint separado tipo /coming-soon o /preventa).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cine", default="mallplaza", help="Slug del cine, ej: mallplaza, pacific-mall")
    parser.add_argument("--dias", type=int, default=10, help="Cuantos dias hacia adelante consultar")
    args = parser.parse_args()
    main(args.cine, args.dias)