import { useEffect } from 'react';
import { Tabs, usePathname, useRouter } from 'expo-router';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import { useApiToken } from '../../src/features/prospectlab/useToken';
import { useTheme } from '../../src/ui/theme';

export default function TabsLayout() {
  const t = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const { token, loading } = useApiToken();

  useEffect(() => {
    if (loading) return;
    if (token) return;
    if (pathname === '/(tabs)/settings') return;
    // Autoriser l'écran de scan token même sans token configure
    if (pathname.includes('token-ocr')) return;
    if (pathname.includes('website-scan')) return;
    // Dans un navigator Tabs, `replace()` declenche une action REPLACE non supportee.
    // `push()` bascule correctement vers l'onglet Reglages sans warning.
    router.push('/(tabs)/settings');
  }, [loading, pathname, router, token]);

  /** Sous-pages détail : pas d’onglets en bas pour éviter la confusion de contexte (guidelines iOS/Material). */
  const hideTabBar = pathname.includes('/details');
  const hideHeader = pathname.includes('/details');

  return (
    <Tabs
      screenOptions={{
        headerTitleAlign: 'center',
        headerStyle: { backgroundColor: t.colors.card },
        // Sur les écrans "details", on évite le header natif de Tabs (sinon doublon avec `useDetailScreenHeader`).
        headerShown: !hideHeader,
        headerShadowVisible: false,
        headerTintColor: t.colors.text,
        headerTitleStyle: { color: t.colors.text, fontWeight: '700' },
        tabBarStyle: {
          backgroundColor: t.colors.card,
          borderTopColor: t.colors.border,
          ...(hideTabBar ? { display: 'none' as const } : {}),
        },
        tabBarActiveTintColor: t.colors.primary,
        tabBarInactiveTintColor: t.colors.muted,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Dashboard',
          tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name="view-dashboard-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="entreprises"
        options={{
          title: 'Entreprises',
          tabBarIcon: ({ color, size }) => <FontAwesome6 name="building" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="campagnes"
        options={{
          title: 'Campagnes',
          tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name="email-multiple-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="website"
        options={{
          title: 'Sites',
          tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name="web" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="carte"
        options={{
          title: 'Carte',
          tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name="map-marker-radius-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="token-ocr"
        options={{
          href: null,
          title: 'Token API',
        }}
      />
      <Tabs.Screen
        name="website-scan"
        options={{
          href: null,
          title: 'Caméra',
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          href: null,
          title: 'Reglages',
          tabBarIcon: ({ color, size }) => <FontAwesome6 name="gear" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
