<p align="center">
  <img src="docs/logo.png" alt="¿Dónde la Veo?" width="420"/>
</p>

<h3 align="center">Compara cines. Ahorra en tu boleta.</h3>

<p align="center">
  Un comparador de precios de cine en tiempo real para Colombia — porque la misma película,
  el mismo día, puede costar el triple según a qué cine vayas.
</p>

---

## 🎬 Qué es esto

**¿Dónde la Veo?** responde una pregunta simple que nadie más responde bien:

> *"Quiero ver [película] hoy. ¿En qué cine me sale más barata, y a qué hora hay función?"*

El proyecto recorre automáticamente **Cinemark Colombia** e **Izi Movie** (Cali), guarda toda su
cartelera, horarios y precios en una base de datos propia, y los expone a través de una API y una
app móvil — comparando entre cadenas distintas, no solo entre sucursales de una misma cadena.

## ✨ Funcionalidades

- 🎟️ **Comparador de precios entre cadenas** — la misma película puede costar $6.750 en un cine y
  $21.450 en otro. Esta app te dice cuál es cuál, incluso cuando cada cadena escribe el título de
  forma distinta.
- 🍿 **Cartelera diaria con estrenos, preventas y "próximamente"**, calculado automáticamente a
  partir de cuándo cada cine empieza a vender boletas — sin mantener una lista a mano.
- 🔁 **Coincidencia automática de títulos entre cadenas**, incluso cuando cada una nombra la
  película distinto (ej. *"Spiderman Nuevo Día"* en una y *"Spiderman: Un Nuevo Día"* en otra).
- 📍 **Cines cercanos por GPS** (backend listo, integración en la app en progreso).
- 📱 **App móvil nativa** (iOS/Android) construida en React Native + Expo, con diseño fiel a Figma.

## 🏗️ Arquitectura

```
┌──────────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────────┐
│   Scrapers   │───▶│   cines.db   │───▶│   Backend   │───▶│  App móvil │
│ (Python)     │    │  (SQLite)    │    │  (FastAPI)  │    │ (Expo/RN)  │
└──────────────┘    └──────────────┘    └─────────────┘    └────────────┘
Cinemark + Izi         Cines,            /home, /comparar,      Grid de
Movie (Cinexo)       películas,          /cartelera, etc.      películas,
                     funciones,                                header,
                     precios                                   splash
```

Cada pieza corre por separado y de forma independiente:

- **Scrapers**: corren por lotes (manual o programados), nunca en vivo desde la app.
- **cines.db**: única fuente de verdad, poblada por los scrapers, leída (nunca escrita) por el backend.
- **Backend**: API REST de solo lectura sobre `cines.db`.
- **App móvil**: consume la API, no conoce nada de cómo se obtienen los datos.

## 🛠️ Stack tecnológico

| Capa | Tecnología |
|---|---|
| Scraping | Python, `requests`, expresiones regulares (para APIs sin JSON limpio) |
| Base de datos | SQLite (modo WAL para escritura concurrente) |
| Backend | FastAPI, Pydantic |
| Coincidencia de títulos | `difflib` + normalización de texto (sin listas manuales) |
| App móvil | React Native, Expo, TypeScript |
| Diseño | Figma → código exacto vía MCP / Builder.io |

## 📂 Estructura del proyecto

```
cine/
├── scrapercinemark.py       # Scraper de Cinemark Colombia
├── scraper_izimovie.py      # Scraper de Izi Movie (plataforma Cinexo)
├── db.py                    # Esquema y acceso a cines.db
├── diagnosticos_fechas.py   # Utilidad de diagnóstico de cobertura
├── backend/
│   └── app/
│       ├── main.py          # Endpoints de la API
│       ├── schemas.py       # Modelos Pydantic
│       ├── database.py      # Conexión de solo lectura
│       └── geo.py           # Cálculo de distancias (haversine)
└── app-movil/
    └── app/
        ├── splash.tsx       # Pantalla de bienvenida
        └── (tabs)/
            └── index.tsx    # Pantalla principal (grid de películas)
```

## 🚀 Cómo correrlo localmente

**1. Scrapers** (generan/actualizan `cines.db`):
```bash
python scrapercinemark.py
python scraper_izimovie.py
```

**2. Backend**:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Documentación interactiva en `http://localhost:8000/docs`.

**3. App móvil**:
```bash
cd app-movil
npm install
npx expo start
```
Escanea el QR con la app **Expo Go**, o corre `w` para verla en el navegador.

> ⚠️ La app necesita la IP local de tu computador (no `localhost`) para hablarle al backend desde
> el celular — configúrala en la constante `API_URL` de `app/(tabs)/index.tsx`.

## 🗺️ Roadmap

- [x] Scraper de Cinemark Colombia (18 ciudades, 31 cines)
- [x] Scraper de Izi Movie (Cali)
- [x] Backend con comparador de precios y coincidencia automática entre cadenas
- [x] Pantalla principal de la app con diseño fiel a Figma
- [x] Pantalla de Splash
- [ ] Pantalla de detalle: comparar precios de una película al tocarla
- [ ] Cines cercanos con GPS real en la app
- [ ] Scraper de una tercera cadena (Cine Colombia / Cinépolis)
- [ ] Deploy del backend (Render/Railway)
- [ ] Publicación en App Store / Play Store

## 🧠 Sobre este proyecto

Este es un proyecto de portafolio construido desde cero en Cali, Colombia — sin experiencia previa
en web scraping antes de empezarlo. Cada pieza (ingeniería inversa de APIs no documentadas,
scraping paralelo con manejo de errores, un backend con comparación automática de texto entre
fuentes distintas, y una app móvil con diseño pixel-perfect) se construyó paso a paso, resolviendo
errores reales en el camino en lugar de seguir un tutorial.

## 👤 Autor

**Exotic Development** — [github.com/Exoticdevelopment](https://github.com/Exoticdevelopment)

---

<p align="center"><i>Hecho con Python, FastAPI, React Native, y bastante paciencia para leer tracebacks. 🎬</i></p>
