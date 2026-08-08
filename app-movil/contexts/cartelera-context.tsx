// ============================================================
// CONTEXTO DE CARTELERA
// ============================================================
// Centraliza el fetch de /home (lista de películas) y de
// /peliculas/{slug} (detalle: sinopsis, director, reparto, trailer).
//
// Por qué existe: antes cada pantalla (Home, ficha de película) hacía
// su propio fetch y mostraba su propio "Cargando...". Eso significaba
// que, aunque el splash ya hubiera terminado, el usuario seguía viendo
// spinners al entrar a Home o a una ficha.
//
// Ahora el RootLayout mantiene el splash visible hasta que este
// contexto termina de cargar la cartelera COMPLETA (la lista + el
// detalle de cada película, precargado en paralelo). Cuando el splash
// se oculta, Home y las fichas ya tienen todo listo en `cache` y
// pueden pintarse sin spinner.
//
// El detalle de una película puede además pedirse "a demanda" con
// obtenerDetalle(slug): si ya está en cache lo devuelve al instante;
// si no (ej. una película se agregó al backend después del arranque),
// dispara el fetch y cachea el resultado, como fallback.
// ============================================================

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

// ------------------------------------------------------------
// CONFIGURACIÓN: única fuente de la dirección del backend.
// (Antes esta constante estaba duplicada en index.tsx y about.tsx.)
// ------------------------------------------------------------
const API_URL = "http://192.168.1.13:8000";

// ------------------------------------------------------------
// TIPOS
// ------------------------------------------------------------
export type Pelicula = {
  id: number;
  nombre: string;
  slug: string;
  genero: string | null;
  clasificacion: string | null;
  duracion_min: number | null;
  cover_image_url: string | null;
  tipo: "ESTRENO" | "PREVENTA" | "PROXIMAMENTE";
  fecha_estreno: string | null;
};

export type PeliculaDetalle = Pelicula & {
  sinopsis: string | null;
  director: string | null;
  actores: string | null;
  trailer_url: string | null;
};

type CarteleraContextValue = {
  // Lista de /home. Vacía hasta que termina el primer fetch.
  peliculas: Pelicula[];
  // true mientras se carga la lista Y el detalle de cada película.
  // El RootLayout usa esto para no ocultar el splash antes de tiempo.
  cargando: boolean;
  // Error del fetch de la lista (el de un detalle puntual no se
  // propaga acá para no tumbar toda la app por una sola película).
  error: string | null;
  // Cache de detalle por slug.
  detalles: Record<string, PeliculaDetalle>;
  // Pide (o devuelve de cache) el detalle de una película.
  obtenerDetalle: (slug: string) => Promise<PeliculaDetalle>;
};

const CarteleraContext = createContext<CarteleraContextValue | null>(null);

export function CarteleraProvider({ children }: { children: ReactNode }) {
  const [peliculas, setPeliculas] = useState<Pelicula[]>([]);
  const [detalles, setDetalles] = useState<Record<string, PeliculaDetalle>>({});
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Evita disparar el mismo fetch de detalle dos veces si dos
  // pantallas lo piden casi al mismo tiempo (ej. precarga inicial +
  // el usuario toca la tarjeta antes de que termine).
  const promesasEnCurso = useRef<Record<string, Promise<PeliculaDetalle>>>({});
  const cacheDetalles = useRef<Record<string, PeliculaDetalle>>({});

  const obtenerDetalle = useCallback((slug: string): Promise<PeliculaDetalle> => {
    if (cacheDetalles.current[slug]) {
      return Promise.resolve(cacheDetalles.current[slug]);
    }
    if (promesasEnCurso.current[slug]) {
      return promesasEnCurso.current[slug];
    }

    const promesa = fetch(`${API_URL}/peliculas/${slug}`)
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error(`El backend respondió con error ${respuesta.status}`);
        }
        return respuesta.json() as Promise<PeliculaDetalle>;
      })
      .then((datos) => {
        cacheDetalles.current[slug] = datos;
        setDetalles((anteriores) => ({ ...anteriores, [slug]: datos }));
        return datos;
      })
      .finally(() => {
        delete promesasEnCurso.current[slug];
      });

    promesasEnCurso.current[slug] = promesa;
    return promesa;
  }, []);

  useEffect(() => {
    let cancelado = false;

    fetch(`${API_URL}/home`)
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error(`El backend respondió con error ${respuesta.status}`);
        }
        return respuesta.json() as Promise<Pelicula[]>;
      })
      .then(async (datos) => {
        if (cancelado) return;
        setPeliculas(datos);

        // Precarga en paralelo del detalle de cada película (sinopsis,
        // director, reparto, trailer) para que al entrar a cualquier
        // ficha ya esté todo listo, sin su propio "Cargando...".
        await Promise.all(
          datos.map((p) =>
            obtenerDetalle(p.slug).catch(() => {
              // Si el detalle de UNA película falla, no bloqueamos el
              // resto de la app: esa ficha reintentará sola cuando el
              // usuario entre a ella (ver fallback en about.tsx).
            })
          )
        );
      })
      .catch((err) => {
        if (!cancelado) setError(err.message);
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });

    return () => {
      cancelado = true;
    };
    // Solo se ejecuta una vez, al montar el provider (arranque de la app).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <CarteleraContext.Provider
      value={{ peliculas, cargando, error, detalles, obtenerDetalle }}
    >
      {children}
    </CarteleraContext.Provider>
  );
}

export function useCartelera(): CarteleraContextValue {
  const contexto = useContext(CarteleraContext);
  if (!contexto) {
    throw new Error("useCartelera debe usarse dentro de <CarteleraProvider>");
  }
  return contexto;
}