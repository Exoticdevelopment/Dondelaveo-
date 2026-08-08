import { DarkTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import 'react-native-reanimated';

import SplashScreen from './splash';

export const unstable_settings = {
  anchor: '(tabs)',
};

// Cuánto tiempo se muestra el Splash de Figma antes de pasar al Home.
const DURACION_SPLASH_MS = 2000;

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

export default function RootLayout() {
  const [mostrarSplash, setMostrarSplash] = useState(true);

  useEffect(() => {
    const temporizador = setTimeout(() => setMostrarSplash(false), DURACION_SPLASH_MS);
    return () => clearTimeout(temporizador);
  }, []);

  return (
    <ThemeProvider value={TEMA_APP}>
      {mostrarSplash ? (
        <SplashScreen />
      ) : (
        <Stack screenOptions={{ contentStyle: { backgroundColor: '#0F1420' } }}>
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
        </Stack>
      )}
      <StatusBar style="light" />
    </ThemeProvider>
  );
}