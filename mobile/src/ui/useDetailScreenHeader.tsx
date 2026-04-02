import { useLayoutEffect } from 'react';
import { useNavigation } from '@react-navigation/native';
import { Platform } from 'react-native';
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
 * Header Stack unique : titre dynamique + retour natif (pas de headerLeft custom = évite le doublon avec l’onglet Tabs).
 */
export function useDetailScreenHeader({ title, fallbackTitle, listPath: _listPath }: DetailScreenHeaderOptions) {
  const navigation = useNavigation();
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
    });
  }, [navigation, resolved, t.colors.card, t.colors.primary, t.colors.text]);
}
