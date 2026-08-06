# Backend — Comparador de Cines (Cinemark Colombia)

API en FastAPI que lee de `cines.db` (poblada por el scraper) y expone
cartelera, horarios, precios y cercanía por GPS. **Nunca escribe** en la
base de datos — eso lo hace únicamente `scrapercinemark.py` por separado.

## Correrlo en tu PC

1. Copia tu `cines.db` real a esta carpeta (o define su ruta con una
   variable de entorno).

2. Instala dependencias:
   ```
   pip install -r requirements.txt
   ```

3. Arranca el servidor:
   ```
   # Si cines.db está en esta misma carpeta:
   uvicorn app.main:app --reload

   # Si está en otra ruta:
   # Windows (PowerShell):
   $env:CINES_DB_PATH="C:\ruta\a\cines.db"; uvicorn app.main:app --reload
   # Mac/Linux:
   CINES_DB_PATH=/ruta/a/cines.db uvicorn app.main:app --reload
   ```

4. Abre en el navegador: **http://127.0.0.1:8000/docs**
   Ahí FastAPI genera documentación interactiva automática — puedes
   probar cada endpoint desde el navegador sin escribir código.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/ciudades` | Lista de ciudades con cines |
| GET | `/cines?ciudad=` | Cines (opcionalmente filtrados por ciudad) |
| GET | `/cines/cercanos?lat=&lon=&limite=` | Cines ordenados por distancia GPS real |
| GET | `/peliculas?fecha=` | Películas con función ese día (todo el país) |
| GET | `/peliculas/{slug}/fechas` | Fechas con datos guardados para esa película |
| GET | `/peliculas/{slug}/comparar?fecha=&lat=&lon=` | Todos los cines + horario + precio para esa película, ordenado de más barato a más caro |
| GET | `/cartelera/{cine_id}?fecha=` | Cartelera completa de un cine |

`fecha` siempre usa formato `YYYY-MM-DD` y por defecto es hoy.

## Notas importantes

- **Cobertura de fechas**: hoy `cines.db` solo tiene datos del día en que
  corriste el scraper. Para poder comparar precios en distintos días
  (ej. "¿es más barato ir el sábado que el domingo?"), el scraper necesita
  correr con `date` de varios días hacia adelante, no solo hoy. Es el
  siguiente ajuste pendiente antes de que `/peliculas/{slug}/comparar`
  tenga sentido con más de una fecha.
- **CORS**: por ahora está abierto a cualquier origen (`allow_origins=["*"]`)
  para que la app móvil pueda conectarse fácil durante desarrollo. Antes
  de producción, restringir a los dominios reales de la app.

## Deploy (cuando estés listo)

Este proyecto ya está listo para deploy en Render o Railway (planes
gratuitos) sin cambios de código, solo:
1. Subir el repo a GitHub (backend + `cines.db`, o mejor, un job separado
   que suba `cines.db` actualizado periódicamente).
2. En Render/Railway: definir el comando de arranque como
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Configurar `CINES_DB_PATH` como variable de entorno si el archivo no
   está en la raíz del proyecto.

Podemos hacer esto juntos cuando quieras — solo dime cuándo.
