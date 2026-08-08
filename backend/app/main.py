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
    Cine,
    Pelicula,
    Funcion,
    FuncionesPorPelicula,
    CarteleraCine,
    ComparacionItem,
    HomeItem,
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
    texto = re.sub(
        r"[^a-z0-9\s]", " ", texto
    )  # espacio, no borrar (evita pegar palabras)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _son_la_misma_pelicula(fila1, fila2, umbral: float = 0.82) -> bool:
    """
    Compara dos FILAS de la tabla 'peliculas' (posiblemente de cadenas
    distintas, con nombres escritos de forma distinta, o incluso en
    idiomas distintos) y decide si son la misma película.

    Usa dos señales, en este orden:
    1) tmdb_id: cuando enriquecemos con TMDB, cada película real recibe
       un identificador único (tmdb_id) sin importar cómo la haya
       nombrado cada cadena. Si dos filas tienen el MISMO tmdb_id, son
       la misma película con certeza, sin importar qué tan distintos
       sean los nombres (ej. "Bajo Presión" vs "Pressure").
    2) Si no hay tmdb_id en alguna de las dos (o no coincide), caemos
       al criterio de texto que ya usábamos:
       a) Similitud letra por letra (variaciones tipo tildes/orden).
       b) Si un título es una versión recortada del otro, revisamos si
          TODAS las palabras del título más corto aparecen en el más largo.
    """
    tmdb_1 = fila1["tmdb_id"] if "tmdb_id" in fila1.keys() else None
    tmdb_2 = fila2["tmdb_id"] if "tmdb_id" in fila2.keys() else None
    if tmdb_1 is not None and tmdb_2 is not None and tmdb_1 == tmdb_2:
        return True

    a, b = _normalizar_titulo(fila1["nombre"]), _normalizar_titulo(fila2["nombre"])

    if difflib.SequenceMatcher(None, a, b).ratio() >= umbral:
        return True

    palabras_a, palabras_b = set(a.split()), set(b.split())
    menor, mayor = (
        (palabras_a, palabras_b)
        if len(palabras_a) <= len(palabras_b)
        else (palabras_b, palabras_a)
    )
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
    usando la misma comparación automática que usa /comparar (tmdb_id primero,
    texto como respaldo).

    IMPORTANTE: comparamos la nueva fila contra TODOS los miembros de cada
    cluster existente (no solo el primero), porque a veces A se parece a B
    por texto, y B comparte tmdb_id con C, pero A y C no se parecen entre
    sí directamente (ej. "Bajo Presión" ~ "El Día D: Bajo Presión" por texto,
    y esta última comparte tmdb_id con "Pressure"). Sin esto, C se quedaría
    afuera del cluster de A y B.

    Devuelve una lista de clusters; cada cluster es una lista de filas
    que representan la MISMA película en distintas cadenas.
    """
    clusters = []
    for fila in filas:
        cluster_encontrado = None
        for cluster in clusters:
            if any(_son_la_misma_pelicula(miembro, fila) for miembro in cluster):
                cluster_encontrado = cluster
                break
        if cluster_encontrado is not None:
            cluster_encontrado.append(fila)
        else:
            clusters.append([fila])
    return clusters


def _mismo_mes(fecha_iso: str, fecha_referencia: str) -> bool:
    """True si dos fechas 'YYYY-MM-DD' caen en el mismo año y mes."""
    return fecha_iso[:7] == fecha_referencia[:7]


def _row_a_cine(row, lat=None, lon=None):
    d = None
    if lat is not None and lon is not None:
        d = distancia_km(lat, lon, row["latitud"], row["longitud"])
    return Cine(
        id=row["id"],
        nombre=row["nombre"],
        ciudad=row["ciudad"],
        latitud=row["latitud"],
        longitud=row["longitud"],
        slug=row["slug"],
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
        rows = conn.execute(
            "SELECT DISTINCT ciudad FROM cines ORDER BY ciudad"
        ).fetchall()
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
            rows = conn.execute(
                "SELECT * FROM cines ORDER BY ciudad, nombre"
            ).fetchall()
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
        
        
        
@app.get("/peliculas/{slug}", response_model=Pelicula)
def detalle_pelicula(slug: str):
    """Detalle completo de una película (incluye sinopsis/director/actores/trailer de TMDB), para la pantalla de detalle de la app."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM peliculas WHERE slug = ?", (slug,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Película '{slug}' no encontrada")
        return Pelicula(**dict(row))
    finally:
        conn.close()


@app.get("/peliculas/{slug}/fechas", response_model=list[str])
def fechas_disponibles(slug: str):
    """Qué fechas hay datos guardados para esta película (útil para navegar 'próximos días')."""
    conn = get_conn()
    try:
        pelicula = conn.execute(
            "SELECT id FROM peliculas WHERE slug = ?", (slug,)
        ).fetchone()
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
        pelicula = conn.execute(
            "SELECT id, nombre, tmdb_id FROM peliculas WHERE slug = ?", (slug,)
        ).fetchone()
        if not pelicula:
            raise HTTPException(404, f"Película '{slug}' no encontrada")

        # Agrupamos TODAS las películas (de cualquier cadena) en clusters de
        # "misma película" (mismo criterio que usa /home: tmdb_id primero,
        # texto como respaldo) y nos quedamos con el cluster de la que se pidió.
        todas_las_peliculas = conn.execute(
            "SELECT id, nombre, tmdb_id FROM peliculas"
        ).fetchall()
        clusters = _agrupar_peliculas_duplicadas(todas_las_peliculas)
        cluster_de_la_pelicula = next(
            (c for c in clusters if any(f["id"] == pelicula["id"] for f in c)),
            [pelicula],
        )
        ids_coincidentes = [f["id"] for f in cluster_de_la_pelicula]
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
            resultado.append(
                ComparacionItem(
                    cine=cine,
                    pelicula_nombre=r["pelicula_nombre"],
                    hora=r["hora"],
                    formato=r["formato"],
                    idioma=r["idioma"],
                    precio_cop=r["precio_cop"],
                    asientos_disponibles=r["asientos_disponibles"],
                )
            )
        return resultado
    finally:
        conn.close()


@app.get("/cartelera/{cine_id}", response_model=CarteleraCine)
def cartelera_de_cine(cine_id: int, fecha: str = Query(default_factory=_hoy)):
    """Cartelera completa (todas las películas y horarios) de un cine en una fecha."""
    conn = get_conn()
    try:
        cine_row = conn.execute(
            "SELECT * FROM cines WHERE id = ?", (cine_id,)
        ).fetchone()
        if not cine_row:
            raise HTTPException(404, f"Cine {cine_id} no encontrado")

        rows = conn.execute(
            """
            SELECT p.id as pelicula_id, p.nombre, p.slug, p.duracion_min, p.clasificacion, p.genero,
                   p.cover_image_url,
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
                        id=r["pelicula_id"],
                        nombre=r["nombre"],
                        slug=r["slug"],
                        duracion_min=r["duracion_min"],
                        clasificacion=r["clasificacion"],
                        genero=r["genero"],
                        cover_image_url=r["cover_image_url"],
                    ),
                    funciones=[],
                )
            peliculas_map[pid].funciones.append(
                Funcion(
                    session_id=r["session_id"],
                    hora=r["hora"],
                    formato=r["formato"],
                    idioma=r["idioma"],
                    asientos_disponibles=r["asientos_disponibles"],
                    precio_cop=r["precio_cop"],
                )
            )

        return CarteleraCine(
            cine=_row_a_cine(cine_row),
            fecha=fecha,
            peliculas=list(peliculas_map.values()),
        )
    finally:
        conn.close()


@app.get("/home", response_model=list[HomeItem])
def home(fecha: str = Query(default_factory=_hoy)):
    """
    Lista de películas para la pantalla principal de la app, con su tipo
    (ESTRENO / PREVENTA) calculado a partir de la fecha más temprana en
    la que cada película tiene función guardada.

    Solo se muestran películas que tengan AL MENOS una función guardada
    en alguna cadena (ESTRENO), o cuya función más próxima caiga dentro
    del mes actual (PREVENTA). Las películas sin ninguna función registrada
    (catálogo sin fecha real: obras de teatro, conciertos, anuncios sin
    horarios aún) no se muestran, y las preventas de meses más adelante
    tampoco, hasta que se acerque su mes.

    IMPORTANTE: una misma película puede existir varias veces en la base
    (una vez por cada cadena que la tenga, ej. Cinemark e Izi Movie).
    Antes de responder, agrupamos automáticamente esas repeticiones para
    que la app muestre cada película UNA sola vez.
    """
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT p.id, p.nombre, p.slug, p.genero, p.clasificacion, p.duracion_min,
                   p.cover_image_url, p.tmdb_id, MIN(f.fecha) as fecha_min
            FROM peliculas p
            LEFT JOIN funciones f ON f.pelicula_id = p.id
            GROUP BY p.id
            ORDER BY p.nombre
            """).fetchall()

        clusters = _agrupar_peliculas_duplicadas(rows)

        resultado = []
        for cluster in clusters:
            # Representante: preferimos la fila que sí tenga póster,
            # para no perder la imagen si una de las cadenas no la trae.
            representante = next(
                (f for f in cluster if f["cover_image_url"]), cluster[0]
            )

            # La fecha de estreno real es la más temprana entre TODAS las
            # cadenas que tengan esta película (si Izi Movie la estrena
            # antes que Cinemark, esa es la fecha que debe mostrarse).
            fechas_min = [f["fecha_min"] for f in cluster if f["fecha_min"] is not None]

            if not fechas_min:
                # Ninguna función registrada en ninguna cadena: no la mostramos
                # (evita listar catálogo sin fecha real, ej. obras de teatro,
                # conciertos o anuncios sin horarios todavía).
                continue

            fecha_min_global = min(fechas_min)

            if fecha_min_global <= fecha:
                tipo, fecha_estreno = "ESTRENO", None
            elif _mismo_mes(fecha_min_global, fecha):
                tipo, fecha_estreno = "PREVENTA", fecha_min_global
            else:
                # Preventa de un mes más adelante: todavía no se muestra.
                continue

            resultado.append(
                HomeItem(
                    id=representante["id"],
                    nombre=representante["nombre"],
                    slug=representante["slug"],
                    genero=representante["genero"],
                    clasificacion=representante["clasificacion"],
                    duracion_min=representante["duracion_min"],
                    cover_image_url=representante["cover_image_url"],
                    tipo=tipo,
                    fecha_estreno=fecha_estreno,
                )
            )

        resultado.sort(key=lambda item: item.nombre)
        return resultado
    finally:
        conn.close()