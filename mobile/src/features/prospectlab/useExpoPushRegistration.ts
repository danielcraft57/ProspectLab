import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { useEffect, useRef } from 'react';
import { Platform } from 'react-native';
import { getOrCreateInstallationId } from '../../lib/storage/installationId';
import { ProspectLabApi } from './prospectLabApi';
import { useApiToken } from './useToken';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

/**
 * Enregistre le jeton Expo Push auprès de ProspectLab quand un token API est présent,
 * et le retire à la déconnexion (effacement du token).
 */
export function useExpoPushRegistration() {
  const { token: apiToken, loading } = useApiToken();
  const lastPushRef = useRef<string | null>(null);
  const prevApiRef = useRef<string | null>(null);

  useEffect(() => {
    if (loading || Platform.OS === 'web') return;

    let cancelled = false;

    (async () => {
      const prev = prevApiRef.current;

      if (prev && !apiToken && lastPushRef.current) {
        try {
          await ProspectLabApi.unregisterExpoPush(prev, lastPushRef.current);
        } catch {
          // déjà révoqué / hors-ligne
        }
        lastPushRef.current = null;
      }

      prevApiRef.current = apiToken;

      if (!apiToken || cancelled) return;

      const projectId = Constants.expoConfig?.extra?.eas?.projectId as string | undefined;
      if (!projectId) {
        if (__DEV__) {
          console.warn(
            '[push] ID projet EAS manquant: définis EXPO_PUBLIC_EAS_PROJECT_ID (voir eas init / expo.dev).',
          );
        }
        return;
      }

      const { status: existing } = await Notifications.getPermissionsAsync();
      let final = existing;
      if (existing !== 'granted') {
        const asked = await Notifications.requestPermissionsAsync();
        final = asked.status;
      }
      if (final !== 'granted' || cancelled) return;

      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'ProspectLab',
          importance: Notifications.AndroidImportance.DEFAULT,
        });
      }

      let pushStr: string;
      try {
        const expoRes = await Notifications.getExpoPushTokenAsync({ projectId });
        pushStr = expoRes.data;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        const fcmMissing =
          Platform.OS === 'android' &&
          (/FirebaseApp|not initialized|fcm-credentials|google-services/i.test(msg) ||
            msg.includes('com.google.firebase'));
        if (fcmMissing) {
          if (__DEV__) {
            const pkg =
              (Constants.expoConfig?.android?.package as string | undefined) ?? 'expo.android.package';
            console.warn(
              `[push] Android sans FCM : ajoute google-services.json (Firebase → appli Android, package ${pkg}), android.googleServicesFile dans app.json, puis rebuild natif. Voir https://docs.expo.dev/push-notifications/fcm-credentials/`,
            );
          }
          return;
        }
        throw e;
      }

      if (cancelled) return;

      lastPushRef.current = pushStr;

      const installationId = await getOrCreateInstallationId();
      if (cancelled) return;

      await ProspectLabApi.registerExpoPush(apiToken, {
        expoPushToken: pushStr,
        platform: Platform.OS,
        installationId,
      });
    })().catch((e) => {
      if (__DEV__) console.warn('[push] synchronisation', e);
    });

    return () => {
      cancelled = true;
    };
  }, [apiToken, loading]);
}
