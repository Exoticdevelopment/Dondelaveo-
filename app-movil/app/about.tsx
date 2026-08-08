import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ImageBackground,
  TouchableOpacity,
  StatusBar,
  SafeAreaView,
  ActivityIndicator,
} from "react-native";
import { useRouter, useLocalSearchParams, Stack } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { WebView } from "react-native-webview";
import * as WebBrowser from "expo-web-browser";

// ------------------------------------------------------------
// CONFIGURACIÓN: misma dirección de backend que index.tsx.
// TODO (futuro, no urgente): mover a un solo archivo compartido
// (ej. constants/api.ts) para no tener que actualizar la IP en dos sitios.
// ------------------------------------------------------------
const API_URL = "http://192.168.1.13:8000";

// ------------------------------------------------------------
// TIPO: coincide con el modelo `Pelicula` que devuelve el backend
// (backend/app/schemas.py) en GET /peliculas/{slug}.
// ------------------------------------------------------------
type Pelicula = {
  id: number;
  nombre: string;
  slug: string;
  duracion_min: number | null;
  clasificacion: string | null;
  genero: string | null;
  cover_image_url: string | null;
  sinopsis: string | null;
  director: string | null;
  actores: string | null;
  trailer_url: string | null;
};

type Tab = "sipnosis" | "funciones";

// "145" -> "02:25"
function formatearDuracion(minutos: number | null): string | null {
  if (minutos == null) return null;
  const horas = Math.floor(minutos / 60);
  const mins = minutos % 60;
  return `${String(horas).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
}

// "https://www.youtube.com/watch?v=o8EccyRIwQQ" -> "o8EccyRIwQQ"
// (trailer_url en la base siempre es un link de YouTube, nunca un .mp4 directo,
// por eso lo embebemos con el iframe player en vez de usar expo-video)
function extraerYoutubeId(url: string): string | null {
  const match = url.match(/(?:v=|\/embed\/|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
  return match ? match[1] : null;
}

export default function PeliculaDetalle() {
  const router = useRouter();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const [tab, setTab] = useState<Tab>("sipnosis");

  // El trailer arranca muteado a propósito: iOS y Android solo permiten
  // autoplay real si el video empieza en silencio. El usuario puede
  // activar el sonido con el botón de bocina.
  const [muted, setMuted] = useState(true);

  // Algunos trailers NO se pueden embeber (el dueño del video lo restringe,
  // YouTube devuelve error 101/150/153). Si eso pasa, dejamos de mostrar
  // el WebView y caemos al póster + botón "Ver en YouTube".
  const [embedError, setEmbedError] = useState(false);

  const [pelicula, setPelicula] = useState<Pelicula | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) {
      setError("No se recibió el slug de la película");
      setCargando(false);
      return;
    }

    setCargando(true);
    setError(null);

    fetch(`${API_URL}/peliculas/${slug}`)
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error(`El backend respondió con error ${respuesta.status}`);
        }
        return respuesta.json();
      })
      .then((datos) => setPelicula(datos))
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, [slug]);

  // ------------------------------------------------------------
  // Estado: cargando
  // ------------------------------------------------------------
  if (cargando) {
    return (
      <SafeAreaView style={styles.contenedorCentrado}>
        <StatusBar barStyle="light-content" />
        <ActivityIndicator size="large" color="#fff" />
        <Text style={styles.textoAyuda}>Cargando película...</Text>
      </SafeAreaView>
    );
  }

  // ------------------------------------------------------------
  // Estado: error
  // ------------------------------------------------------------
  if (error || !pelicula) {
    return (
      <SafeAreaView style={styles.contenedorCentrado}>
        <StatusBar barStyle="light-content" />
        <TouchableOpacity
          onPress={() => router.back()}
          style={styles.botonVolverError}
          accessibilityLabel="Volver"
        >
          <Ionicons name="chevron-back" size={24} color="#637394" />
        </TouchableOpacity>
        <Text style={styles.textoError}>No se pudo cargar la película</Text>
        <Text style={styles.textoAyuda}>{error ?? "Respuesta vacía"}</Text>
        <Text style={styles.textoAyuda}>
          Revisa que el backend esté corriendo con --host 0.0.0.0{"\n"}
          y que la IP en API_URL sea correcta.
        </Text>
      </SafeAreaView>
    );
  }

  // ------------------------------------------------------------
  // Datos ya listos: armamos la lista de detalles a mostrar,
  // saltándonos cualquiera que venga vacío desde el backend.
  // ------------------------------------------------------------
  const youtubeId = pelicula.trailer_url
    ? extraerYoutubeId(pelicula.trailer_url)
    : null;

  // Usamos la YouTube IFrame API dentro de un HTML propio (en vez de cargar
  // directo la URL de embed) por dos razones:
  // 1. Nos deja escuchar el evento onError (video 101/150/153 = embed
  //    bloqueado por el dueño) y reaccionar mostrando el fallback.
  // 2. Le da a YouTube un contexto de página real, en vez de una URL de
  //    embed "pelada" cargada directo en el WebView.
  const embedHtml = youtubeId
    ? `<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1"><style>html,body{margin:0;padding:0;background:#000;height:100%;overflow:hidden;}#player{width:100%;height:100%;}</style></head>
<body>
<div id="player"></div>
<script src="https://www.youtube.com/iframe_api"></script>
<script>
  function onYouTubeIframeAPIReady() {
    new YT.Player('player', {
      videoId: '${youtubeId}',
      playerVars: {
        autoplay: 1,
        mute: ${muted ? 1 : 0},
        playsinline: 1,
        controls: 1,
        modestbranding: 1,
        rel: 0
      },
      events: {
        onError: function (e) {
          window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'error', code: e.data }));
        }
      }
    });
  }
</script>
</body></html>`
    : null;

  const duracion = formatearDuracion(pelicula.duracion_min);
  const detalles: { label: string; value: string }[] = [
    ...(duracion ? [{ label: "Duración", value: duracion }] : []),
    ...(pelicula.genero ? [{ label: "Género", value: pelicula.genero }] : []),
    ...(pelicula.director ? [{ label: "Director", value: pelicula.director }] : []),
    ...(pelicula.actores ? [{ label: "Reparto", value: pelicula.actores }] : []),
  ];

  return (
    <SafeAreaView style={styles.contenedor}>
      <Stack.Screen options={{ headerShown: false }} />
      <StatusBar barStyle="light-content" />

      {/* Header: volver + título + tabs */}
      <View style={styles.header}>
        <View style={styles.filaTitulo}>
          <TouchableOpacity
            onPress={() => router.back()}
            style={styles.botonVolver}
            accessibilityLabel="Volver"
          >
            <Ionicons name="chevron-back" size={24} color="#637394" />
          </TouchableOpacity>
          <Text style={styles.titulo} numberOfLines={1}>
            {pelicula.nombre}
          </Text>
          <View style={styles.espacioVolver} />
        </View>

        <View style={styles.filaTabs}>
          {(
            [
              { id: "sipnosis" as Tab, label: "Sipnosis" },
              { id: "funciones" as Tab, label: "Funciones" },
            ] as const
          ).map((item) => {
            const activo = tab === item.id;
            return (
              <TouchableOpacity
                key={item.id}
                style={styles.tab}
                onPress={() => setTab(item.id)}
              >
                <Text style={[styles.tabTexto, activo && styles.tabTextoActivo]}>
                  {item.label}
                </Text>
                <View style={[styles.tabLinea, activo && styles.tabLineaActiva]} />
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContenido}>
        {/* Trailer: si hay trailer_url, se reproduce solo (muteado) embebiendo
            el iframe player de YouTube. Si no hay trailer, mostramos el
            póster como fondo, igual que antes. */}
        <View style={styles.imagenFondo}>
          {youtubeId && !embedError ? (
            <>
              <WebView
                key={muted ? "muted" : "sonido"}
                source={{ html: embedHtml! }}
                style={styles.trailerWebview}
                allowsInlineMediaPlayback
                mediaPlaybackRequiresUserAction={false}
                javaScriptEnabled
                domStorageEnabled
                startInLoadingState
                onMessage={(evento) => {
                  try {
                    const datos = JSON.parse(evento.nativeEvent.data);
                    if (datos.type === "error") {
                      setEmbedError(true);
                    }
                  } catch {
                    // Mensaje no era el JSON que esperábamos: lo ignoramos.
                  }
                }}
                renderLoading={() => (
                  <View style={styles.trailerCargando}>
                    <ActivityIndicator size="small" color="#fff" />
                  </View>
                )}
              />
              <TouchableOpacity
                style={styles.botonSonido}
                accessibilityLabel={muted ? "Activar sonido" : "Silenciar"}
                onPress={() => setMuted((valorAnterior) => !valorAnterior)}
              >
                <Ionicons
                  name={muted ? "volume-mute" : "volume-high"}
                  size={20}
                  color="#FFFFFF"
                />
              </TouchableOpacity>
            </>
          ) : (
            <ImageBackground
              source={
                pelicula.cover_image_url
                  ? { uri: pelicula.cover_image_url }
                  : undefined
              }
              style={styles.imagenFondoCompleto}
            >
              {youtubeId && embedError ? (
                // Este trailer específico no se puede embeber (YouTube lo
                // bloqueó): dejamos ver el póster y abrir el video en YouTube.
                <TouchableOpacity
                  style={styles.botonVerYoutube}
                  accessibilityLabel="Ver tráiler en YouTube"
                  onPress={() => WebBrowser.openBrowserAsync(pelicula.trailer_url!)}
                >
                  <Ionicons name="logo-youtube" size={20} color="#FFFFFF" />
                  <Text style={styles.botonVerYoutubeTexto}>Ver en YouTube</Text>
                </TouchableOpacity>
              ) : null}
            </ImageBackground>
          )}
        </View>

        {/* Contenido según tab activo */}
        <View style={styles.contenidoTab}>
          {tab === "sipnosis" ? (
            <>
              {pelicula.sinopsis ? (
                <Text style={styles.sinopsisTexto}>{pelicula.sinopsis}</Text>
              ) : (
                <Text style={styles.funcionesPlaceholder}>
                  Todavía no tenemos sinopsis para esta película.
                </Text>
              )}

              <View style={styles.detallesLista}>
                {pelicula.clasificacion ? (
                  <View style={styles.detalleFila}>
                    <Text style={styles.detalleLabel}>Clasificación</Text>
                    <View style={styles.certificadoBadge}>
                      <Text style={styles.certificadoTexto}>
                        {pelicula.clasificacion}
                      </Text>
                    </View>
                  </View>
                ) : null}

                {detalles.map((d) => (
                  <View key={d.label} style={styles.detalleFila}>
                    <Text style={styles.detalleLabel}>{d.label}</Text>
                    <Text style={styles.detalleValor}>{d.value}</Text>
                  </View>
                ))}
              </View>
            </>
          ) : (
            <Text style={styles.funcionesPlaceholder}>
              Muy pronto vas a ver aquí los horarios y precios de esta
              película en los cines cercanos.
            </Text>
          )}
        </View>
      </ScrollView>

      {/* Footer con botón principal */}
      <View style={styles.footer}>
        <TouchableOpacity style={styles.botonPrincipal}>
          <Text style={styles.botonPrincipalTexto}>
            Busquemos la función más barata!
          </Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

// Colores tomados directo del diseño de Figma exportado:
// fondo oscuro, texto muted gris-azulado, acento naranja del botón principal.
const COLOR_FONDO = "#0F1420";
const COLOR_HEADER = "rgba(26, 32, 46, 0.7)";
const COLOR_MUTED = "#637394";
const COLOR_BORDE = "rgba(255, 255, 255, 0.1)";
const COLOR_PRIMARIO = "#FF8036";

const styles = StyleSheet.create({
  contenedor: {
    flex: 1,
    backgroundColor: COLOR_FONDO,
  },
  contenedorCentrado: {
    flex: 1,
    backgroundColor: COLOR_FONDO,
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  botonVolverError: {
    position: "absolute",
    top: 44,
    left: 8,
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  textoError: {
    color: "#e74c3c",
    fontSize: 16,
    fontWeight: "bold",
    marginBottom: 8,
    textAlign: "center",
  },
  textoAyuda: {
    color: COLOR_MUTED,
    fontSize: 13,
    marginTop: 8,
    textAlign: "center",
  },
  header: {
    backgroundColor: COLOR_HEADER,
  },
  filaTitulo: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  botonVolver: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  espacioVolver: {
    width: 40,
  },
  titulo: {
    flex: 1,
    textAlign: "center",
    fontSize: 18,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  filaTabs: {
    flexDirection: "row",
  },
  tab: {
    flex: 1,
    alignItems: "center",
  },
  tabTexto: {
    height: 48,
    lineHeight: 48,
    fontSize: 16,
    fontWeight: "700",
    color: COLOR_MUTED,
  },
  tabTextoActivo: {
    color: COLOR_PRIMARIO,
  },
  tabLinea: {
    height: 2,
    width: "100%",
    backgroundColor: COLOR_BORDE,
  },
  tabLineaActiva: {
    backgroundColor: COLOR_PRIMARIO,
  },
  scrollContenido: {
    paddingBottom: 24,
  },
  imagenFondo: {
    height: 210,
    width: "100%",
    position: "relative",
    backgroundColor: "#D3D3D3",
    overflow: "hidden",
  },
  imagenFondoCompleto: {
    height: "100%",
    width: "100%",
  },
  trailerWebview: {
    height: "100%",
    width: "100%",
    backgroundColor: "#000",
  },
  trailerCargando: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#000",
  },
  botonSonido: {
    position: "absolute",
    bottom: 10,
    right: 10,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(0,0,0,0.55)",
    alignItems: "center",
    justifyContent: "center",
  },
  botonVerYoutube: {
    position: "absolute",
    bottom: 12,
    right: 12,
    left: 12,
    flexDirection: "row",
    gap: 8,
    height: 40,
    borderRadius: 8,
    backgroundColor: "rgba(0,0,0,0.65)",
    alignItems: "center",
    justifyContent: "center",
  },
  botonVerYoutubeTexto: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  contenidoTab: {
    padding: 16,
    gap: 16,
  },
  sinopsisTexto: {
    fontSize: 14,
    lineHeight: 20,
    color: "#FFFFFF",
  },
  detallesLista: {
    gap: 12,
    marginTop: 12,
  },
  detalleFila: {
    flexDirection: "row",
    gap: 16,
  },
  detalleLabel: {
    width: 90,
    fontSize: 14,
    color: COLOR_MUTED,
  },
  detalleValor: {
    flex: 1,
    fontSize: 14,
    fontWeight: "500",
    color: "#FFFFFF",
  },
  certificadoBadge: {
    borderWidth: 1,
    borderColor: COLOR_BORDE,
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    alignSelf: "flex-start",
  },
  certificadoTexto: {
    fontSize: 14,
    fontWeight: "500",
    color: "#FFFFFF",
  },
  funcionesPlaceholder: {
    fontSize: 14,
    lineHeight: 20,
    color: COLOR_MUTED,
  },
  footer: {
    backgroundColor: COLOR_HEADER,
    padding: 16,
  },
  botonPrincipal: {
    height: 56,
    borderRadius: 8,
    backgroundColor: COLOR_PRIMARIO,
    alignItems: "center",
    justifyContent: "center",
  },
  botonPrincipalTexto: {
    fontSize: 18,
    fontWeight: "700",
    color: "#FFFFFF",
  },
});