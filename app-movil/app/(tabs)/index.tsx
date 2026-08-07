// ============================================================
// PANTALLA DE INICIO — Grid de películas (Estreno / Preventa / Próximamente)
// ============================================================
// Medidas, colores y espaciados sincronizados con el diseño de Figma
// "Home / Authorized" (logo absoluto 85x85 en left:12/top:25, barra de
// controles pegada a la derecha, grid con padding-top 124 bajo el header).
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
  TouchableOpacity,
} from "react-native";
import { Ionicons, MaterialIcons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { BlurView } from "expo-blur";

// ------------------------------------------------------------
// CONFIGURACIÓN: dirección de tu backend
// ------------------------------------------------------------
const API_URL = "http://192.168.1.13:8000";

// ------------------------------------------------------------
// PALETA DE COLORES (confirmados desde tailwind.config.ts del export)
// ------------------------------------------------------------
const COLORES = {
  fondo: "#1A2232",
  primario: "#FF8036",
  primarioOscuro: "#FC6D19",
  atenuado: "#637394",
  vidrio: "rgba(31,41,61,0.7)",
};

// ------------------------------------------------------------
// TIPOS
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
// FUNCIÓN AUXILIAR: "2026-08-20" -> "20 AGO"
// ------------------------------------------------------------
function formatearFecha(fechaISO: string): string {
  const meses = [
    "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
    "JUL", "AGO", "SEP", "OCT", "NOV", "DIC",
  ];
  const [, mes, dia] = fechaISO.split("-");
  return `${parseInt(dia, 10)} ${meses[parseInt(mes, 10) - 1]}`;
}

// ------------------------------------------------------------
// COMPONENTE: header — vidrio esmerilado (BlurView), con logo a la
// izquierda y pills + Log in a la derecha, como estaba antes.
// ------------------------------------------------------------
function CinemaHeader() {
  return (
    <View style={styles.barraFixedContainer}>
      {/* El BlurView da el efecto de vidrio; va DETRÁS del contenido */}
      <BlurView intensity={20} tint="dark" style={styles.blurFondo} />

      <View style={styles.contenidoHeader}>
        <Image
          source={require("../../assets/images/logo.png")}
          style={styles.logo}
          resizeMode="contain"
        />

        <View style={styles.controlesFila}>
          <View style={styles.opcionesGrupo}>
            <View style={styles.pill}>
              <Ionicons name="location-outline" size={20} color={COLORES.atenuado} />
              <Text style={styles.pillTexto}>Cali</Text>
            </View>

            <View style={styles.pill}>
              <MaterialIcons name="translate" size={20} color={COLORES.atenuado} />
              <Text style={styles.pillTexto}>Es</Text>
            </View>
          </View>

          <LinearGradient
            colors={[COLORES.primario, COLORES.primarioOscuro]}
            style={styles.botonLogin}
          >
            <TouchableOpacity>
              <Text style={styles.botonLoginTexto}>Log in</Text>
            </TouchableOpacity>
          </LinearGradient>
        </View>
      </View>
    </View>
  );
}

// ------------------------------------------------------------
// COMPONENTE: título + lupa
// ------------------------------------------------------------
function TituloSeccion() {
  return (
    <View style={styles.tituloFila}>
      <Text style={styles.titulo}>Now in cinemas</Text>
      <TouchableOpacity style={styles.botonBuscar}>
        <Ionicons name="search-outline" size={24} color={COLORES.atenuado} />
      </TouchableOpacity>
    </View>
  );
}

// ------------------------------------------------------------
// COMPONENTE: MovieCard — chip naranja para estrenos, chip de vidrio
// (BlurView) para preventas/próximamente.
// ------------------------------------------------------------
function MovieCard({ pelicula }: { pelicula: Pelicula }) {
  const esChipNaranja = pelicula.tipo === "ESTRENO";

  let textoChip = pelicula.clasificacion ?? "";
  if (pelicula.tipo === "PREVENTA" && pelicula.fecha_estreno) {
    textoChip = formatearFecha(pelicula.fecha_estreno);
  } else if (pelicula.tipo === "PROXIMAMENTE") {
    textoChip = "PRONTO";
  }

  return (
    <View style={styles.tarjeta}>
      <View style={styles.posterContenedor}>
        {pelicula.cover_image_url ? (
          <Image
            source={{ uri: pelicula.cover_image_url }}
            style={styles.poster}
            resizeMode="cover"
          />
        ) : (
          <View style={[styles.poster, styles.posterVacio]}>
            <Text style={styles.posterVacioTexto}>Sin imagen</Text>
          </View>
        )}

        {esChipNaranja ? (
          <View style={styles.chipNaranja}>
            <Text style={styles.chipTexto}>{textoChip}</Text>
          </View>
        ) : (
          <BlurView intensity={20} tint="dark" style={styles.chipVidrio}>
            <Text style={styles.chipTexto}>{textoChip}</Text>
          </BlurView>
        )}
      </View>

      <View style={styles.infoTarjeta}>
        <Text style={styles.tituloTarjeta} numberOfLines={1}>
          {pelicula.nombre}
        </Text>
        <Text style={styles.generoTarjeta} numberOfLines={1}>
          {pelicula.genero ?? ""}
        </Text>
      </View>
    </View>
  );
}

// ------------------------------------------------------------
// PANTALLA PRINCIPAL
// ------------------------------------------------------------
export default function PantallaInicio() {
  const [peliculas, setPeliculas] = useState<Pelicula[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  if (cargando) {
    return (
      <SafeAreaView style={styles.centrado}>
        <ActivityIndicator size="large" color="#fff" />
        <Text style={styles.textoAyuda}>Cargando cartelera...</Text>
      </SafeAreaView>
    );
  }

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

  return (
    <View style={styles.contenedor}>
      <FlatList
        data={peliculas}
        keyExtractor={(pelicula) => pelicula.slug}
        numColumns={2}
        contentContainerStyle={styles.grid}
        columnWrapperStyle={styles.fila}
        ListHeaderComponent={<TituloSeccion />}
        renderItem={({ item }) => <MovieCard pelicula={item} />}
      />
      <CinemaHeader />
    </View>
  );
}

// ------------------------------------------------------------
// ESTILOS
// ------------------------------------------------------------
const styles = StyleSheet.create({
  contenedor: {
    flex: 1,
    backgroundColor: COLORES.fondo,
  },
  centrado: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: COLORES.fondo,
    padding: 20,
  },

  // --- Barra superior fija: 108px de alto, igual que en Figma (Fixed) ---
  barraFixedContainer: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 108,
    zIndex: 10,
  },
  blurFondo: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: COLORES.vidrio,
  },
  // Logo posicionado igual que en Figma: left 12, top 25, 85x85
  logo: {
    width: 85,
    height: 85,
  },

  contenidoHeader: {
  position: "absolute",
  top: 44,           // debajo de la barra de estado del celular
  left: 0,
  right: 0,
  height: 64,         // la barra real, donde va tu contenido
  flexDirection: "row",
  alignItems: "center",         // esto sí centra verticalmente, dentro de estos 64px
  justifyContent: "space-between",
  paddingHorizontal: 16,
},

  // Fila de controles (Cali / Es / Log in), pegada a la derecha
  controlesFila: {
    height: 40,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  opcionesGrupo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    height: 40,
    paddingHorizontal: 8,
    borderRadius: 8,
  },
  pillTexto: {
    color: "white",
    fontSize: 14,
    fontWeight: "700",
  },
  botonLogin: {
    height: 40,
    paddingHorizontal: 16,
    borderRadius: 8,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: COLORES.primario,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 4,
  },
  botonLoginTexto: {
    color: "white",
    fontSize: 14,
    fontWeight: "700",
  },

  // --- Título de sección ---
  tituloFila: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    marginBottom: 16,
  },
  titulo: {
    flex: 1,
    color: "white",
    fontSize: 24,
    fontWeight: "700",
  },
  botonBuscar: {
    height: 40,
    width: 40,
    justifyContent: "center",
    alignItems: "center",
  },

  // --- Grid y tarjetas ---
  grid: {
    paddingHorizontal: 16,
    paddingTop: 124, // 108 (barra fija) + 16 (padding del Content en Figma)
    paddingBottom: 64,
  },
  fila: {
    gap: 16,
    marginBottom: 16,
  },
  tarjeta: {
    flex: 1,
    gap: 8,
  },
  posterContenedor: {
    position: "relative",
    borderRadius: 8,
    overflow: "hidden",
    shadowColor: "rgb(7,9,13)",
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.25,
    shadowRadius: 40,
    elevation: 8,
  },
  poster: {
    width: "100%",
    height: 230,
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
  chipNaranja: {
    position: "absolute",
    top: 4,
    right: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    backgroundColor: COLORES.primario,
    shadowColor: COLORES.primario,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 4,
  },
  chipVidrio: {
    position: "absolute",
    top: 4,
    right: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    overflow: "hidden",
    backgroundColor: COLORES.vidrio,
  },
  chipTexto: {
    color: "white",
    fontSize: 12,
    fontWeight: "700",
  },
  infoTarjeta: {
    gap: 4,
  },
  tituloTarjeta: {
    color: "white",
    fontSize: 16,
    fontWeight: "700",
     textTransform: "uppercase",
  },
  generoTarjeta: {
    color: COLORES.atenuado,
    fontSize: 14,
  },

  textoError: {
    color: "#e74c3c",
    fontSize: 16,
    fontWeight: "bold",
    marginBottom: 8,
    textAlign: "center",
  },
  textoAyuda: {
    color: COLORES.atenuado,
    fontSize: 13,
    marginTop: 8,
    textAlign: "center",
  },
});