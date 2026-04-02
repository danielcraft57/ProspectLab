import { Stack } from 'expo-router';

/**
 * Pile liste → détail : le bouton retour Android remonte à la liste, pas au dashboard.
 * (Sans Stack, détail était un 2ᵉ écran d’onglets : retour = mauvais niveau de navigation.)
 */
export default function EntreprisesStackLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
