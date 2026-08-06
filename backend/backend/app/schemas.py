from typing import Optional, List
from pydantic import BaseModel


class Cine(BaseModel):
    id: int
    nombre: str
    ciudad: str
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    slug: Optional[str] = None
    distancia_km: Optional[float] = None


class Pelicula(BaseModel):
    id: int
    nombre: str
    slug: str
    duracion_min: Optional[int] = None
    clasificacion: Optional[str] = None
    genero: Optional[str] = None


class Funcion(BaseModel):
    session_id: int
    hora: str
    formato: Optional[str] = None
    idioma: Optional[str] = None
    asientos_disponibles: Optional[int] = None
    precio_cop: Optional[int] = None


class FuncionesPorPelicula(BaseModel):
    pelicula: Pelicula
    funciones: List[Funcion]


class CarteleraCine(BaseModel):
    cine: Cine
    fecha: str
    peliculas: List[FuncionesPorPelicula]


class ComparacionItem(BaseModel):
    cine: Cine
    hora: str
    formato: Optional[str] = None
    idioma: Optional[str] = None
    precio_cop: Optional[int] = None
    asientos_disponibles: Optional[int] = None
    
    
class HomeItem(BaseModel):
    id: int
    nombre: str
    slug: str
    genero: Optional[str] = None
    clasificacion: Optional[str] = None
    duracion_min: Optional[int] = None
    cover_image_url: Optional[str] = None
    tipo: str  # "ESTRENO", "PREVENTA", o "PROXIMAMENTE"
    fecha_estreno: Optional[str] = None
    
    