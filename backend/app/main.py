"""
Backend del comparador de cines (Cinemark Colombia + Izi Movie).

Lee de cines.db (poblada por los scrapers). Nunca escribe en la base.

Ejecutar localmente:
    uvicorn app.main:app --reload

Documentación interactiva automática en:
    http://127.0.0.1:8000/docs
"""

import re
import unicodedata
import difflib
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import get_conn
from .geo import distancia_km
from .schemas import (
    Cine, Pelicula, Funcion, FuncionesPorPelicula, CarteleraCine, ComparacionItem, HomeItem,
)

app = FastAPI(
    title="Comparador de Cines API",
    description="Compara cartelera, horarios y precios entre cines Cinemark Colombia e Izi Movie.",
    version="0.1.0",
)

# Durante desarrollo permitimos cualquier origen (la app móvil corre en otro puerto/host).
# Antes de producción, restringir a los dominios reales de la app.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _hoy():
    return date.today().isoformat()

def _normalizar_titulo(texto: str) -> str:
    """Limpia un título para poder compararlo: sin tildes, mayúsculas ni puntuación."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)  # espacio, no borrar (evita pegar palabras)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _son_la_misma_pelicula(nombre1: str, nombre2: str, umbral: float = 0.82) -> bool:
    """
    Compara dos títulos de película (posiblemente de cadenas distintas,
    con nombres escritos de forma distinta) y decide si son la misma
    película, sin necesitar una lista manual de equivalencias.

    Usa dos reglas:
    1) Similitud letra por letra (para variaciones tipo tildes/orden,
       ej. "Spiderman Nuevo Dia" vs "Spiderman: Un Nuevo Día").
    2) Si un título es una versión recortada del otro (ej. "Bajo Presión"
       vs "El Día D: Bajo Presión"), revisamos si TODAS las palabras del
       título más corto aparecen dentro del más largo.
    """
    a, b = _normalizar_titulo(nombre1), _normalizar_titulo(nombre2)

    if difflib.SequenceMatcher(None, a, b).ratio() >= umbral:
        return True

    palabras_a, palabras_b = set(a.split()), set(b.split())
    menor, mayor = (palabras_a, palabras_b) if len(palabras_a) <= len(palabras_b) else (palabras_b, palabras_a)
    # Exigimos al menos 2 palabras en el título corto, para no confundir
    # dos películas distintas que por casualidad compartan una sola palabra.
    if len(menor) >= 2 and menor.issubset(mayor):
        return True

    return False

def _agrupar_peliculas_duplicadas(filas):
    """
    Recibe filas de la tabla 'peliculas' (posiblemente con la MISMA película
    repetida por venir de cadenas distintas, ej. "Spiderman" en Cinemark
    Y en Izi Movie) y las agrupa en "clusters" de películas equivalentes,
    usando la misma comparación automática de títulos que usa /comparar.

    Devuelve una lista de clusters; cada cluster es una lista de filas
    que representan la MISMA película en distintas cadenas.
    """
    clusters = []
    for fila in filas:
        encontro_cluster = False
        for cluster in clusters:
            representante = cluster[0]
            if _son_la_misma_pelicula(representante["nombre"], fila["nombre"]):
                cluster.append(fila)
                encontro_cluster = True
                break
        if not encontro_cluster:
            clusters.append([fila])
    return clusters


def _row_a_cine(row, lat=None, lon=None):
    d = None
    if lat is not None and lon is not None:
        d = distancia_km(lat, lon, row["latitud"], row["longitud"])
    return Cine(
        id=row["id"], nombre=row["nombre"], ciudad=row["ciudad"],
        latitud=row["latitud"], longitud=row["longitud"], slug=row["slug"],
        cadena=row["cadena"] if "cadena" in row.keys() else None,
        distancia_km=d,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ciudades", response_model=list[str])
def listar_ciudades():
    conn = get_conn()
    try:
        rows = conn.execute("SELECT DISTINCT ciudad FROM cines ORDER BY ciudad").fetchall()
        return [r["ciudad"] for r in rows]
    finally:
        conn.close()


@app.get("/cines", response_model=list[Cine])
def listar_cines(ciudad: Optional[str] = None):
    conn = get_conn()
    try:
        if ciudad:
            rows = conn.execute(
                "SELECT * FROM cines WHERE ciudad = ? ORDER BY nombre", (ciudad,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM cines ORDER BY ciudad, nombre").fetchall()
        return [_row_a_cine(r) for r in rows]
    finally:
        conn.close()


@app.get("/cines/cercanos", response_model=list[Cine])
def cines_cercanos(
    lat: float = Query(..., description="Latitud del usuario"),
    lon: float = Query(..., description="Longitud del usuario"),
    limite: int = Query(10, ge=1, le=50),
):
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM cines").fetchall()
        cines = [_row_a_cine(r, lat, lon) for r in rows]
        cines = [c for c in cines if c.distancia_km is not None]
        cines.sort(key=lambda c: c.distancia_km)
        return cines[:limite]
    finally:
        conn.close()


@app.get("/peliculas", response_model=list[Pelicula])
def listar_peliculas(fecha: str = Query(default_factory=_hoy)):
    """Películas con al menos una función guardada en esa fecha (todo el país)."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT p.* FROM peliculas p
            JOIN funciones f ON f.pelicula_id = p.id
            WHERE f.fecha = ?
            ORDER BY p.nombre
            """,
            (fecha,),
        ).fetchall()
        return [Pelicula(**dict(r)) for r in rows]
    finally:
        conn.close()


@app.get("/peliculas/{slug}/fechas", response_model=list[str])
def fechas_disponibles(slug: str):
    """Qué fechas hay datos guardados para esta película (útil para navegar 'próximos días')."""
    conn = get_conn()
    try:
        pelicula = conn.execute("SELECT id FROM peliculas WHERE slug = ?", (slug,)).fetchone()
        if not pelicula:
            raise HTTPException(404, f"Película '{slug}' no encontrada")
        rows = conn.execute(
            "SELECT DISTINCT fecha FROM funciones WHERE pelicula_id = ? ORDER BY fecha",
            (pelicula["id"],),
        ).fetchall()
        return [r["fecha"] for r in rows]
    finally:
        conn.close()


@app.get("/peliculas/{slug}/comparar", response_model=list[ComparacionItem])
def comparar_precios(
    slug: str,
    fecha: str = Query(default_factory=_hoy),
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    """
    El endpoint central del comparador: para una película y fecha dadas,
    devuelve todas las funciones en todos los cines (de CUALQUIER cadena
    cuyo título coincida automáticamente), ordenadas de más barata a más
    cara. Si se manda lat/lon, incluye distancia a cada cine.
    """
    conn = get_conn()
    try:
        pelicula = conn.execute("SELECT id, nombre FROM peliculas WHERE slug = ?", (slug,)).fetchone()
        if not pelicula:
            raise HTTPException(404, f"Película '{slug}' no encontrada")

        # Buscamos TODAS las películas (de cualquier cadena) cuyo nombre
        # coincida automáticamente con la que se pidió, sin lista manual.
        todas_las_peliculas = conn.execute("SELECT id, nombre FROM peliculas").fetchall()
        ids_coincidentes = [
            p["id"] for p in todas_las_peliculas
            if _son_la_misma_pelicula(pelicula["nombre"], p["nombre"])
        ]
        placeholders = ",".join("?" * len(ids_coincidentes))

        rows = conn.execute(
            f"""
            SELECT f.session_id, f.hora, f.formato, f.idioma, f.asientos_disponibles,
                   pr.precio_cop, c.*, p.nombre as pelicula_nombre
            FROM funciones f
            JOIN cines c ON c.id = f.cine_id
            JOIN peliculas p ON p.id = f.pelicula_id
            LEFT JOIN precios pr ON pr.session_id = f.session_id
            WHERE f.pelicula_id IN ({placeholders}) AND f.fecha = ?
            ORDER BY pr.precio_cop ASC
            """,
            (*ids_coincidentes, fecha),
        ).fetchall()

        resultado = []
        for r in rows:
            cine = _row_a_cine(r, lat, lon)
            resultado.append(ComparacionItem(
                cine=cine, pelicula_nombre=r["pelicula_nombre"],
                hora=r["hora"], formato=r["formato"], idioma=r["idioma"],
                precio_cop=r["precio_cop"], asientos_disponibles=r["asientos_disponibles"],
            ))
        return resultado
    finally:
        conn.close()


@app.get("/cartelera/{cine_id}", response_model=CarteleraCine)
def cartelera_de_cine(cine_id: int, fecha: str = Query(default_factory=_hoy)):
    """Cartelera completa (todas las películas y horarios) de un cine en una fecha."""
    conn = get_conn()
    try:
        cine_row = conn.execute("SELECT * FROM cines WHERE id = ?", (cine_id,)).fetchone()
        if not cine_row:
            raise HTTPException(404, f"Cine {cine_id} no encontrado")

        rows = conn.execute(
            """
            SELECT p.id as pelicula_id, p.nombre, p.slug, p.duracion_min, p.clasificacion, p.genero,
                   f.session_id, f.hora, f.formato, f.idioma, f.asientos_disponibles, pr.precio_cop
            FROM funciones f
            JOIN peliculas p ON p.id = f.pelicula_id
            LEFT JOIN precios pr ON pr.session_id = f.session_id
            WHERE f.cine_id = ? AND f.fecha = ?
            ORDER BY p.nombre, f.hora
            """,
            (cine_id, fecha),
        ).fetchall()

        peliculas_map = {}
        for r in rows:
            pid = r["pelicula_id"]
            if pid not in peliculas_map:
                peliculas_map[pid] = FuncionesPorPelicula(
                    pelicula=Pelicula(
                        id=r["pelicula_id"], nombre=r["nombre"], slug=r["slug"],
                        duracion_min=r["duracion_min"], clasificacion=r["clasificacion"],
                        genero=r["genero"],
                    ),
                    funciones=[],
                )
            peliculas_map[pid].funciones.append(Funcion(
                session_id=r["session_id"], hora=r["hora"], formato=r["formato"],
                idioma=r["idioma"], asientos_disponibles=r["asientos_disponibles"],
                precio_cop=r["precio_cop"],
            ))

        return CarteleraCine(
            cine=_row_a_cine(cine_row), fecha=fecha, peliculas=list(peliculas_map.values()),
        )
    finally:
        conn.close()


@app.get("/home", response_model=list[HomeItem])
def home(fecha: str = Query(default_factory=_hoy)):
    """
    Lista de películas para la pantalla principal de la app, con su tipo
    (ESTRENO / PREVENTA / PROXIMAMENTE) calculado a partir de la fecha
    más temprana en la que cada película tiene función guardada.

    IMPORTANTE: una misma película puede existir varias veces en la base
    (una vez por cada cadena que la tenga, ej. Cinemark e Izi Movie).
    Antes de responder, agrupamos automáticamente esas repeticiones para
    que la app muestre cada película UNA sola vez.
    """
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.nombre, p.slug, p.genero, p.clasificacion, p.duracion_min,
                   p.cover_image_url, MIN(f.fecha) as fecha_min
            FROM peliculas p
            LEFT JOIN funciones f ON f.pelicula_id = p.id
            GROUP BY p.id
            ORDER BY p.nombre
            """
        ).fetchall()

        clusters = _agrupar_peliculas_duplicadas(rows)

        resultado = []
        for cluster in clusters:
            # Representante: preferimos la fila que sí tenga póster,
            # para no perder la imagen si una de las cadenas no la trae.
            representante = next((f for f in cluster if f["cover_image_url"]), cluster[0])

            # La fecha de estreno real es la más temprana entre TODAS las
            # cadenas que tengan esta película (si Izi Movie la estrena
            # antes que Cinemark, esa es la fecha que debe mostrarse).
            fechas_min = [f["fecha_min"] for f in cluster if f["fecha_min"] is not None]
            fecha_min_global = min(fechas_min) if fechas_min else None

            if fecha_min_global is None:
                tipo, fecha_estreno = "PROXIMAMENTE", None
            elif fecha_min_global <= fecha:
                tipo, fecha_estreno = "ESTRENO", None
            else:
                tipo, fecha_estreno = "PREVENTA", fecha_min_global

            resultado.append(HomeItem(
                id=representante["id"], nombre=representante["nombre"], slug=representante["slug"],
                genero=representante["genero"], clasificacion=representante["clasificacion"],
                duracion_min=representante["duracion_min"], cover_image_url=representante["cover_image_url"],
                tipo=tipo, fecha_estreno=fecha_estreno,
            ))

        resultado.sort(key=lambda item: item.nombre)
        return resultado
    finally:
        conn.close()