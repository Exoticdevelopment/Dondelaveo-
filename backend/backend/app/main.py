"""
Backend del comparador de cines (Cinemark Colombia).

Lee de cines.db (poblada por el scraper). Nunca escribe en la base.

Ejecutar localmente:
    uvicorn app.main:app --reload

Documentación interactiva automática en:
    http://127.0.0.1:8000/docs
"""

from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ..database import get_conn
from ..geo import distancia_km
from .schemas import (
    Cine, Pelicula, Funcion, FuncionesPorPelicula, CarteleraCine, ComparacionItem, HomeItem,
)

app = FastAPI(
    title="Comparador de Cines API",
    description="Compara cartelera, horarios y precios entre cines Cinemark Colombia.",
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


def _row_a_cine(row, lat=None, lon=None):
    d = None
    if lat is not None and lon is not None:
        d = distancia_km(lat, lon, row["latitud"], row["longitud"])
    return Cine(
        id=row["id"], nombre=row["nombre"], ciudad=row["ciudad"],
        latitud=row["latitud"], longitud=row["longitud"], slug=row["slug"],
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
    devuelve todas las funciones en todos los cines, ordenadas de más
    barata a más cara. Si se manda lat/lon, incluye distancia a cada cine.
    """
    conn = get_conn()
    try:
        pelicula = conn.execute("SELECT id FROM peliculas WHERE slug = ?", (slug,)).fetchone()
        if not pelicula:
            raise HTTPException(404, f"Película '{slug}' no encontrada")

        rows = conn.execute(
            """
            SELECT f.session_id, f.hora, f.formato, f.idioma, f.asientos_disponibles,
                   pr.precio_cop, c.*
            FROM funciones f
            JOIN cines c ON c.id = f.cine_id
            LEFT JOIN precios pr ON pr.session_id = f.session_id
            WHERE f.pelicula_id = ? AND f.fecha = ?
            ORDER BY pr.precio_cop ASC
            """,
            (pelicula["id"], fecha),
        ).fetchall()

        resultado = []
        for r in rows:
            cine = _row_a_cine(r, lat, lon)
            resultado.append(ComparacionItem(
                cine=cine, hora=r["hora"], formato=r["formato"], idioma=r["idioma"],
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
