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
    if (pathname === '/token-ocr') return;
    // Dans un navigator Tabs, `replace()` declenche une action REPLACE non supportee.
    // `push()` bascule correctement vers l'onglet Reglages sans warning.
    router.push('/(tabs)/settings');
  }, [loading, pathname, router, token]);

  /** Sous-pages détail : pas d’onglets en bas pour éviter la confusion de contexte (guidelines iOS/Material). */
  const hideTabBar = pathname.includes('/details');

  return (
    <Tabs
      screenOptions={{
        headerTitleAlign: 'center',
        headerStyle: { backgroundColor: t.colors.card },
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
        name="entreprises/details"
        options={{
          href: null,
          title: 'Entreprise',
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
        name="campagnes/details"
        options={{
          href: null,
          title: 'Campagne',
        }}
      />
      <Tabs.Screen
        name="scan"
        options={{
          title: 'Scan',
          tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name="text-recognition" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Reglages',
          tabBarIcon: ({ color, size }) => <FontAwesome6 name="gear" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}

