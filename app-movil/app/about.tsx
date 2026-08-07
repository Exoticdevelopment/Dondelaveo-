import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ImageBackground,
  TouchableOpacity,
  StatusBar,
  SafeAreaView,
} from "react-native";
import { useRouter, useLocalSearchParams, Stack } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

// TODO: cuando el backend exponga el detalle de película, reemplazar esto
// por un fetch usando el `id` de useLocalSearchParams(), en vez de datos fijos.
const PELICULA = {
  titulo: "The Batman",
  imagenFondo:
    "https://api.builder.io/api/v1/image/assets/TEMP/8e2825d7606cc847fcccf8d1c166853d8623d0b5?width=750",
  ratings: [
    { label: "IMDB", value: "8.3" },
    { label: "Kinopoisk", value: "7.9" },
  ],
  sinopsis:
    "When the Riddler, a sadistic serial killer, begins murdering key political figures in Gotham, Batman is forced to investigate the city's hidden corruption and question his family's involvement.",
  certificado: "16+",
  detalles: [
    { label: "Runtime", value: "02:56" },
    { label: "Release", value: "2022" },
    { label: "Genre", value: "Action, Crime, Drama" },
    { label: "Director", value: "Matt Reeves" },
    {
      label: "Cast",
      value:
        "Robert Pattinson, Zoë Kravitz, Jeffrey Wright, Colin Farrell, Paul Dano, John Turturro, Andy Serkis, Peter Sarsgaard",
    },
  ],
};

type Tab = "sipnosis" | "funciones";

export default function PeliculaDetalle() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  // TODO: usar `id` para pedirle al backend los datos reales de esta película
  // (por ahora seguimos mostrando los datos fijos de PELICULA, arriba).
  const [tab, setTab] = useState<Tab>("sipnosis");

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
            {PELICULA.titulo}
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
        {/* Imagen de fondo con botón de play */}
        <ImageBackground
          source={{ uri: PELICULA.imagenFondo }}
          style={styles.imagenFondo}
        >
          <TouchableOpacity
            style={styles.botonPlay}
            accessibilityLabel="Reproducir tráiler"
          >
            <Ionicons name="play" size={24} color="#FFFFFF" />
          </TouchableOpacity>
        </ImageBackground>

        {/* Ratings */}
        <View style={styles.filaRatings}>
          {PELICULA.ratings.map((r, i) => (
            <View key={r.label} style={styles.ratingItem}>
              {i > 0 && <View style={styles.ratingDivisor} />}
              <Text style={styles.ratingValor}>{r.value}</Text>
              <Text style={styles.ratingLabel}>{r.label}</Text>
            </View>
          ))}
        </View>

        {/* Contenido según tab activo */}
        <View style={styles.contenidoTab}>
          {tab === "sipnosis" ? (
            <>
              <Text style={styles.sinopsisTexto}>{PELICULA.sinopsis}</Text>

              <View style={styles.detallesLista}>
                <View style={styles.detalleFila}>
                  <Text style={styles.detalleLabel}>Certificate</Text>
                  <View style={styles.certificadoBadge}>
                    <Text style={styles.certificadoTexto}>
                      {PELICULA.certificado}
                    </Text>
                  </View>
                </View>

                {PELICULA.detalles.map((d) => (
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
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#D3D3D3",
  },
  botonPlay: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "rgba(255,255,255,0.1)",
    alignItems: "center",
    justifyContent: "center",
  },
  filaRatings: {
    flexDirection: "row",
  },
  ratingItem: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  ratingDivisor: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    width: 1,
    backgroundColor: COLOR_BORDE,
  },
  ratingValor: {
    fontSize: 20,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  ratingLabel: {
    fontSize: 14,
    color: COLOR_MUTED,
    marginTop: 4,
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
    width: 74,
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