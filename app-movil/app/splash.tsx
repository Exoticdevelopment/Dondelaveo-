// ============================================================
// SPLASH SCREEN — sincronizado con el diseño de Figma "Splash Screen"
// ============================================================
// Fondo: captura de la app difuminada (blur 40 + overlay de vidrio),
// con el logo "¿Dónde la Veo?" centrado (242x242).
// ============================================================

import { View, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { BlurView } from "expo-blur";

const COLORES = {
  fondo: "#1A2232",
  vidrio: "rgba(31,41,61,0.7)",
};

export default function SplashScreen() {
  return (
    <View style={styles.contenedor}>
      <Image
        source={require("../assets/images/splash-background.png")}
        style={styles.fondo}
        contentFit="cover"
        cachePolicy="memory-disk"
        transition={0}
      />

      <BlurView intensity={90} tint="dark" style={styles.overlay} />

      <View style={styles.centrado}>
        <Image
          source={require("../assets/images/splash-logo.png")}
          style={styles.logo}
          contentFit="contain"
          cachePolicy="memory-disk"
          transition={0}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  contenedor: {
    flex: 1,
    backgroundColor: COLORES.fondo,
  },
  fondo: {
    ...StyleSheet.absoluteFillObject,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: COLORES.vidrio,
  },
  centrado: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  logo: {
    width: 242,
    height: 242,
  },
});