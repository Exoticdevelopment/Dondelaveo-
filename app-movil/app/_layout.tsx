import { DarkTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { View, Image as RNImage } from 'react-native';
import { Image } from 'expo-image';
import 'react-native-reanimated';

import SplashScreen from './splash';
import { CarteleraProvider, useCartelera } from '../contexts/cartelera-context';

export const unstable_settings = {
  anchor: '(tabs)',
};

// Tiempo MÍNIMO que se muestra el Splash de Figma, para que no sea un
// parpadeo si el backend responde muy rápido. Si la cartelera tarda más
// que esto en cargar, el splash se queda hasta que esté lista (ver
// `mostrarSplash` abajo): así Home nunca llega a pintar su estado de
// "Cargando cartelera...".
const DURACION_SPLASH_MS = 2000;

// Tope MÁXIMO absoluto: pase lo que pase (backend caído, sin wifi, una
// imagen que nunca responde), el splash entra a la app igual después de
// este tiempo. Sin esto, cualquier fetch/prefetch colgado deja el splash
// pegado para siempre (fetch e Image.prefetch no tienen timeout propio).
const DURACION_SPLASH_MAX_MS = 8000;

// Toda la app usa el diseño oscuro de Figma (fondo #0F1420), sin importar
// si el celular está en modo claro u oscuro. Antes usábamos DefaultTheme
// (fondo blanco) cuando el sistema estaba en modo claro, y ese blanco se
// veía como un flash durante la animación de transición entre pantallas
// (React Navigation pinta el fondo del theme detrás de cada pantalla
// mientras se anima el push/pop).
const TEMA_APP = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: '#0F1420',
    card: '#0F1420',
  },
};

function RootLayoutInterno() {
  const [tiempoMinimoListo, setTiempoMinimoListo] = useState(false);
  const [tiempoMaximoSuperado, setTiempoMaximoSuperado] = useState(false);
  const [logoHeaderListo, setLogoHeaderListo] = useState(false);
  const { cargando: cargandoCartelera } = useCartelera();

  useEffect(() => {
    const temporizador = setTimeout(() => setTiempoMinimoListo(true), DURACION_SPLASH_MS);
    return () => clearTimeout(temporizador);
  }, []);

  useEffect(() => {
    const temporizador = setTimeout(() => setTiempoMaximoSuperado(true), DURACION_SPLASH_MAX_MS);
    return () => clearTimeout(temporizador);
  }, []);

  // Precarga del logo chiquito del header de Home (assets/images/logo.png).
  // En desarrollo (Expo Go/Metro), las imágenes locales via require() NO
  // van embebidas en el bundle: se piden por HTTP al servidor de Metro la
  // primera vez que se usan, igual que una imagen de red. Sin esto, esa
  // primera petición ocurre justo cuando se monta Home, y como ahí compite
  // con los posters, el logo del header se ve aparecer "al final". Acá la
  // adelantamos mientras se muestra el splash, y esperamos a que termine
  // antes de ocultarlo (a diferencia de solo dispararla sin esperar).
  useEffect(() => {
    let cancelado = false;
    const uri = RNImage.resolveAssetSource(require('../assets/images/logo.png')).uri;
    Promise.race([
      Image.prefetch(uri, "memory-disk"),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 4000)),
    ])
      .catch(() => {
        // Si falla o tarda demasiado la precarga puntual del logo, no
        // bloqueamos el arranque de la app por eso.
      })
      .finally(() => {
        if (!cancelado) setLogoHeaderListo(true);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  // El splash se queda mientras: no pasó el tiempo mínimo, O la cartelera
  // (lista + detalle + posters de cada película) todavía está cargando,
  // O el logo del header todavía no terminó de precargarse — PERO nunca
  // más allá del tope máximo, así nunca queda pegado.
  const mostrarSplash =
    !tiempoMaximoSuperado &&
    (!tiempoMinimoListo || cargandoCartelera || !logoHeaderListo);

  return (
    // View raíz con fondo oscuro: react-native-screens anima cada pantalla
    // como su propia vista nativa, y mientras se desliza (push a "about",
    // por ejemplo) queda un hueco que todavía no cubre ningún screen. Ese
    // hueco deja ver lo que haya "detrás" en el árbol de RN. Sin esta View,
    // lo que se ve detrás es la ventana nativa raíz, que es blanca por
    // defecto — y en Expo Go no podemos cambiar eso vía app.json porque
    // Expo Go corre un binario ya compilado por Expo. Esta View sí es JS,
    // así que aplica al instante sin rebuild nativo.
    <View style={{ flex: 1, backgroundColor: '#0F1420' }}>
      <ThemeProvider value={TEMA_APP}>
        {mostrarSplash ? (
          <SplashScreen />
        ) : (
          <Stack screenOptions={{ contentStyle: { backgroundColor: '#0F1420' } }}>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="about" options={{ headerShown: false }} />
            <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
          </Stack>
        )}
        <StatusBar style="light" />
      </ThemeProvider>
    </View>
  );
}

export default function RootLayout() {
  return (
    // El provider vive FUERA del gate del splash, para que el fetch de la
    // cartelera arranque de inmediato al abrir la app, en paralelo con el
    // timer mínimo del splash, y no después de que este termine.
    <CarteleraProvider>
      <RootLayoutInterno />
    </CarteleraProvider>
  );
}