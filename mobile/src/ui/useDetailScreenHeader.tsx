import { useLayoutEffect } from 'react';
import { useNavigation } from '@react-navigation/native';
import { useRouter } from 'expo-router';
import { Platform, Pressable, Text } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme } from './theme';

export type DetailScreenHeaderOptions = {
  /** Titre affiché dans la barre de navigation (ex. nom entreprise / campagne). */
  title: string;
  /** Titre si `title` est vide (chargement, erreur). */
  fallbackTitle: string;
  /** Route liste à ouvrir si l’historique ne permet pas `goBack` (deep link). */
  listPath: '/(tabs)/entreprises' | '/(tabs)/campagnes';
};

/**
 * Configure le header natif : retour explicite + titre dynamique.
 * Aligné sur les habitudes iOS/Android (un seul « retour » en haut, pas de doublon dans le contenu).
 */
export function useDetailScreenHeader({ title, fallbackTitle, listPath }: DetailScreenHeaderOptions) {
  const navigation = useNavigation();
  const router = useRouter();
  const t = useTheme();

  const resolved = (title && title.trim()) || fallbackTitle;

  useLayoutEffect(() => {
    navigation.setOptions({
      title: resolved,
      headerShown: true,
      headerTitleAlign: 'center',
      headerStyle: {
        backgroundColor: t.colors.card,
      },
      headerShadowVisible: false,
      headerTintColor: t.colors.primary,
      headerTitleStyle: {
        color: t.colors.text,
        fontWeight: '700',
        fontSize: 17,
      },
      ...(Platform.OS === 'ios' ? { headerBackTitleVisible: false } : {}),
      headerLeft: () => (
        <Pressable
          onPress={() => {
            if (navigation.canGoBack()) {
              navigation.goBack();
            } else {
              router.replace(listPath);
            }
          }}
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            paddingVertical: 8,
            paddingRight: 12,
            marginLeft: Platform.OS === 'ios' ? 4 : 0,
          }}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel="Retour"
        >
          <MaterialCommunityIcons name="chevron-left" size={28} color={t.colors.primary} />
          {Platform.OS === 'android' ? (
            <Text style={{ color: t.colors.primary, fontWeight: '700', fontSize: 16 }}>Retour</Text>
          ) : null}
        </Pressable>
      ),
    });
  }, [navigation, router, resolved, listPath, t.colors.card, t.colors.primary, t.colors.text]);
}
