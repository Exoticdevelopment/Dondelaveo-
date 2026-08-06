// ============================================================
// PANTALLA DE INICIO — Grid de películas (Estreno / Preventa / Próximamente)
// ============================================================
// Esta pantalla le pregunta al backend (FastAPI) qué películas hay,
// y las pinta en una cuadrícula de 2 columnas, como en el mockup.
// ============================================================

import { useEffect, useState } from "react";
import {
  View,
  Text,
  Image,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  SafeAreaView,
} from "react-native";

// ------------------------------------------------------------
// CONFIGURACIÓN: dirección de tu backend
// ------------------------------------------------------------
// IMPORTANTE: "localhost" o "127.0.0.1" NO funcionan aquí, porque
// el celular es un dispositivo DISTINTO al computador. Necesita la
// dirección de tu PC dentro de la red WiFi (la misma que viste en
// Expo Go: "Connected to expo-cli 192.168.1.13:8081").
//
// Cambia el número de abajo si tu PC tiene otra dirección IP.
const API_URL = "http://192.168.1.13:8000";

// ------------------------------------------------------------
// TIPOS: le decimos a TypeScript cómo se ve cada película
// que nos devuelve el backend (esto ayuda a detectar errores
// antes de que la app se ejecute, no solo cuando ya falló)
// ------------------------------------------------------------
type Pelicula = {
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

// ------------------------------------------------------------
// FUNCIÓN AUXILIAR: convierte "2026-08-20" en "20 AGO"
// (más fácil de leer que la fecha completa)
// ------------------------------------------------------------
function formatearFecha(fechaISO: string): string {
  const meses = [
    "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
    "JUL", "AGO", "SEP", "OCT", "NOV", "DIC",
  ];
  const [anio, mes, dia] = fechaISO.split("-");
  return `${parseInt(dia, 10)} ${meses[parseInt(mes, 10) - 1]}`;
}

// ------------------------------------------------------------
// COMPONENTE: la etiqueta de color (ESTRENO / PREVENTA / PROXIMAMENTE)
// ------------------------------------------------------------
function Etiqueta({ pelicula }: { pelicula: Pelicula }) {
  if (pelicula.tipo === "PREVENTA" && pelicula.fecha_estreno) {
    return (
      <View style={[styles.etiqueta, styles.etiquetaPreventa]}>
        <Text style={styles.etiquetaTexto}>
          PREVENTA · {formatearFecha(pelicula.fecha_estreno)}
        </Text>
      </View>
    );
  }
  if (pelicula.tipo === "PROXIMAMENTE") {
    return (
      <View style={[styles.etiqueta, styles.etiquetaProximamente]}>
        <Text style={styles.etiquetaTexto}>PRÓXIMAMENTE</Text>
      </View>
    );
  }
  // Si es "ESTRENO", no mostramos etiqueta (así se ve como en el mockup original)
  return null;
}

// ------------------------------------------------------------
// COMPONENTE: una tarjeta individual del grid (un póster + info)
// ------------------------------------------------------------
function TarjetaPelicula({ pelicula }: { pelicula: Pelicula }) {
  return (
    <View style={styles.tarjeta}>
      <View style={styles.posterContenedor}>
        {pelicula.cover_image_url ? (
          // Si la película tiene póster guardado, lo mostramos
          <Image
            source={{ uri: pelicula.cover_image_url }}
            style={styles.poster}
            resizeMode="cover"
          />
        ) : (
          // Si no hay póster (pasa con datos viejos), mostramos un cuadro gris
          // en vez de dejar un hueco feo o que la app se rompa
          <View style={[styles.poster, styles.posterVacio]}>
            <Text style={styles.posterVacioTexto}>Sin imagen</Text>
          </View>
        )}
        <Etiqueta pelicula={pelicula} />
      </View>
      <Text style={styles.titulo} numberOfLines={1}>
        {pelicula.nombre}
      </Text>
      <Text style={styles.genero}>{pelicula.genero ?? ""}</Text>
    </View>
  );
}

// ------------------------------------------------------------
// PANTALLA PRINCIPAL
// ------------------------------------------------------------
export default function PantallaInicio() {
  // "peliculas" guarda la lista que llega del backend.
  // "cargando" nos dice si todavía estamos esperando la respuesta.
  // "error" guarda un mensaje si algo salió mal (para mostrarlo, no ocultarlo).
  const [peliculas, setPeliculas] = useState<Pelicula[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // useEffect con [] al final = "corre esto UNA sola vez, cuando la
  // pantalla aparece por primera vez" (no cada vez que algo cambia).
  useEffect(() => {
    fetch(`${API_URL}/home`)
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error(`El backend respondió con error ${respuesta.status}`);
        }
        return respuesta.json();
      })
      .then((datos) => setPeliculas(datos))
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  // Mientras esperamos la respuesta del backend, mostramos un círculo girando
  if (cargando) {
    return (
      <SafeAreaView style={styles.centrado}>
        <ActivityIndicator size="large" />
        <Text style={styles.textoAyuda}>Cargando cartelera...</Text>
      </SafeAreaView>
    );
  }

  // Si algo falló (backend apagado, IP incorrecta, etc.), lo decimos
  // claramente en vez de mostrar una pantalla en blanco sin explicación
  if (error) {
    return (
      <SafeAreaView style={styles.centrado}>
        <Text style={styles.textoError}>No se pudo conectar al backend</Text>
        <Text style={styles.textoAyuda}>{error}</Text>
        <Text style={styles.textoAyuda}>
          Revisa que el backend esté corriendo con --host 0.0.0.0{"\n"}
          y que la IP en API_URL sea correcta.
        </Text>
      </SafeAreaView>
    );
  }

  // Si todo salió bien, mostramos el grid de 2 columnas
  return (
    <SafeAreaView style={styles.contenedor}>
      <Text style={styles.encabezado}>¿Dónde la Veo?</Text>
      <FlatList
        data={peliculas}
        keyExtractor={(pelicula) => pelicula.slug}
        numColumns={2}
        contentContainerStyle={styles.grid}
        renderItem={({ item }) => <TarjetaPelicula pelicula={item} />}
      />
    </SafeAreaView>
  );
}

// ------------------------------------------------------------
// ESTILOS (el "CSS" de React Native)
// ------------------------------------------------------------
const styles = StyleSheet.create({
  contenedor: {
    flex: 1,
    backgroundColor: "#0d1117",
  },
  centrado: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#0d1117",
    padding: 20,
  },
  encabezado: {
    fontSize: 24,
    fontWeight: "bold",
    color: "white",
    padding: 16,
  },
  grid: {
    paddingHorizontal: 8,
  },
  tarjeta: {
    flex: 1,
    margin: 8,
    maxWidth: "46%",
  },
  posterContenedor: {
    position: "relative",
  },
  poster: {
    width: "100%",
    aspectRatio: 2 / 3,
    borderRadius: 8,
  },
  posterVacio: {
    backgroundColor: "#333",
    justifyContent: "center",
    alignItems: "center",
  },
  posterVacioTexto: {
    color: "#888",
    fontSize: 12,
  },
  etiqueta: {
    position: "absolute",
    bottom: 6,
    left: 6,
    right: 6,
    paddingVertical: 4,
    borderRadius: 4,
  },
  etiquetaPreventa: {
    backgroundColor: "#e67e22",
  },
  etiquetaProximamente: {
    backgroundColor: "#555",
  },
  etiquetaTexto: {
    color: "white",
    fontSize: 10,
    fontWeight: "bold",
    textAlign: "center",
  },
  titulo: {
    color: "white",
    fontSize: 14,
    fontWeight: "600",
    marginTop: 6,
  },
  genero: {
    color: "#999",
    fontSize: 12,
  },
  textoError: {
    color: "#e74c3c",
    fontSize: 16,
    fontWeight: "bold",
    marginBottom: 8,
    textAlign: "center",
  },
  textoAyuda: {
    color: "#999",
    fontSize: 13,
    marginTop: 8,
    textAlign: "center",
  },
});