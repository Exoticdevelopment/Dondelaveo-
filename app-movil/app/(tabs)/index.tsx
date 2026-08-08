// ============================================================
// PANTALLA DE INICIO — Grid de películas (Estreno / Preventa / Próximamente)
// ============================================================
// Medidas, colores y espaciados sincronizados con el diseño de Figma
// "Home / Authorized" (logo absoluto 85x85 en left:12/top:25, barra de
// controles pegada a la derecha, grid con padding-top 124 bajo el header).
// ============================================================

import { useState, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { Ionicons, MaterialIcons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { BlurView } from "expo-blur";
import { useCartelera, type Pelicula } from "../../contexts/cartelera-context";

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
          contentFit="contain"
          cachePolicy="memory-disk"
          transition={0}
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

// Igual que el resto de la app (fetch de /home, prefetch de posters,
// espera del trailer), ninguna carga de imagen puede quedar pegada para
// siempre. El poster de cada tarjeta normalmente ya viene precargado
// desde cartelera-context (Image.prefetch antes de ocultar el splash),
// pero si esa precarga puntual falló o se agregó una película nueva
// después del arranque, este <Image> hace su propio intento — y ese
// intento SÍ necesita su propio timeout, o si la red va lenta se queda
// girando (o de plano en blanco) sin nunca caer a un estado de error.
const POSTER_TIMEOUT_MS = 8000;

function PosterPelicula({ uri }: { uri: string }) {
  const [estado, setEstado] = useState<"cargando" | "listo" | "error">("cargando");

  useEffect(() => {
    setEstado("cargando");
    const temporizador = setTimeout(() => {
      setEstado((actual) => (actual === "cargando" ? "error" : actual));
    }, POSTER_TIMEOUT_MS);
    return () => clearTimeout(temporizador);
    // Si cambia la uri (ej. re-render con otra película en la misma
    // posición de la lista), reinicia el intento desde cero.
  }, [uri]);

  if (estado === "error") {
    return (
      <View style={[styles.poster, styles.posterVacio]}>
        <Text style={styles.posterVacioTexto}>No se pudo cargar</Text>
      </View>
    );
  }

  return (
    <>
      <Image
        source={{ uri }}
        style={styles.poster}
        contentFit="cover"
        cachePolicy="memory-disk"
        transition={150}
        onLoadEnd={() => setEstado((actual) => (actual === "cargando" ? "listo" : actual))}
        onError={() => setEstado("error")}
      />
      {estado === "cargando" ? (
        <View style={[styles.poster, styles.posterCargando]}>
          <ActivityIndicator size="small" color="#fff" />
        </View>
      ) : null}
    </>
  );
}

// ------------------------------------------------------------
// COMPONENTE: MovieCard — chip naranja para estrenos, chip de vidrio
// (BlurView) para preventas/próximamente.
// NUEVO: envuelta en TouchableOpacity, navega a /about al tocarla.
// ------------------------------------------------------------
function MovieCard({ pelicula }: { pelicula: Pelicula }) {
  const router = useRouter();
  const esChipNaranja = pelicula.tipo === "ESTRENO";

  let textoChip = pelicula.clasificacion ?? "";
  if (pelicula.tipo === "PREVENTA" && pelicula.fecha_estreno) {
    textoChip = formatearFecha(pelicula.fecha_estreno);
  } else if (pelicula.tipo === "PROXIMAMENTE") {
    textoChip = "PRONTO";
  }

  return (
    <TouchableOpacity
      style={styles.tarjeta}
      activeOpacity={0.8}
      onPress={() =>
        router.push({ pathname: "/about", params: { slug: pelicula.slug } })
      }
    >
      <View style={styles.posterContenedor}>
        {pelicula.cover_image_url ? (
          <PosterPelicula uri={pelicula.cover_image_url} />
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
    </TouchableOpacity>
  );
}

// ------------------------------------------------------------
// PANTALLA PRINCIPAL
// ------------------------------------------------------------
export default function PantallaInicio() {
  // Para cuando esta pantalla se monta, el splash (en _layout.tsx) ya
  // esperó a que la cartelera terminara de cargar — así que `cargando`
  // acá prácticamente nunca es true. Lo dejamos como resguardo defensivo
  // (ej. si el usuario reabre la app con datos ya en memoria pero algo
  // dispara un refetch), no como el flujo normal.
  const { peliculas, cargando, error } = useCartelera();

  // ----------------------------------------------------------
  // Sin early returns: el header (CinemaHeader) siempre se monta.
  // Solo el contenido debajo de él cambia según el estado.
  // ----------------------------------------------------------
  let contenido: JSX.Element;

  if (cargando) {
    contenido = (
      <View style={styles.centrado}>
        <ActivityIndicator size="large" color="#fff" />
        <Text style={styles.textoAyuda}>Cargando cartelera...</Text>
      </View>
    );
  } else if (error) {
    contenido = (
      <View style={styles.centrado}>
        <Text style={styles.textoError}>No se pudo conectar al backend</Text>
        <Text style={styles.textoAyuda}>{error}</Text>
        <Text style={styles.textoAyuda}>
          Revisa que el backend esté corriendo con --host 0.0.0.0{"\n"}
          y que la IP en API_URL sea correcta.
        </Text>
      </View>
    );
  } else if (peliculas.length > 0) {
    contenido = (
      <FlatList
        data={peliculas}
        keyExtractor={(pelicula) => pelicula.slug}
        numColumns={2}
        contentContainerStyle={styles.grid}
        columnWrapperStyle={styles.fila}
        ListHeaderComponent={<TituloSeccion />}
        renderItem={({ item }) => <MovieCard pelicula={item} />}
        // Todas las películas ya están precargadas (datos + posters) antes
        // de llegar acá, así que no hace falta ser conservador con cuántas
        // se pintan de una: mostrarlas todas de entrada evita el "pop-in"
        // de tarjetas apareciendo mientras se hace scroll rápido.
        initialNumToRender={peliculas.length}
        // Las tarjetas fuera de pantalla no necesitan quedarse montadas
        // (cada una tiene un BlurView en preventa/próximamente, que es
        // relativamente costoso); desmontarlas libera memoria y trabajo
        // de composición sin afectar la fluidez, porque sus imágenes ya
        // están en caché (memory-disk) y vuelven a pintar al instante.
        removeClippedSubviews
      />
    );
  } else {
    contenido = (
      <View style={styles.centrado}>
        <Text style={styles.textoAyuda}>No hay películas disponibles.</Text>
      </View>
    );
  }

  return (
    <View style={styles.contenedor}>
      {/* CinemaHeader (con el logo) va primero en el árbol para que se
          monte/pinte antes que la grilla — junto con el elevation de
          barraFixedContainer, evita que el logo "aparezca al final". */}
      <CinemaHeader />
      {contenido}
    </View>
  );
}

// ------------------------------------------------------------
// ESTILOS
// ------------------------------------------------------------
const styles = StyleSheet.create({
  contenedor: {
    // Color oscuro forzado para evitar parpadeos blancos entre estados
    // (cargando / error / con datos / sin datos).
    flex: 1,
    backgroundColor: "#0F1420",
  },
  centrado: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    // Sin backgroundColor propio: hereda el fondo oscuro de "contenedor"
    // para que no haya parpadeo al cambiar de estado.
    paddingTop: 108, // deja libre el alto del CinemaHeader (absoluto)
    paddingHorizontal: 20,
  },
  barraFixedContainer: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 108,
    zIndex: 10,
    // "elevation" es necesario en Android: ahí zIndex solo no garantiza
    // que este header (con el logo) quede pintado por encima de la
    // grilla (FlatList) y de los BlurView de las tarjetas. Sin esto,
    // en algunos frames el header queda por debajo hasta el próximo
    // repintado, dando la sensación de que "el logo carga al final".
    elevation: 10,
  },
  blurFondo: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: COLORES.vidrio,
  },
  logo: {
    width: 85,
    height: 85,
  },
  contenidoHeader: {
    position: "absolute",
    top: 44,
    left: 0,
    right: 0,
    height: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
  },
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
  grid: {
    paddingHorizontal: 16,
    paddingTop: 124,
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
  posterCargando: {
    position: "absolute",
    top: 0,
    left: 0,
    backgroundColor: "#333",
    justifyContent: "center",
    alignItems: "center",
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