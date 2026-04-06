import * as Notifications from 'expo-notifications';
import { useRouter } from 'expo-router';
import { Platform } from 'react-native';
import { useEffect, useRef } from 'react';
import { navigateFromAnalysisNotificationData } from './navigateFromAnalysisNotification';

/**
 * Au tap sur une notif (analyse prête), ouvre directement la fiche entreprise.
 * Gère l’ouverture à froid via getLastNotificationResponseAsync.
 */
export function NotificationDeepLink() {
  const router = useRouter();
  const handledIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    function handleResponse(response: Notifications.NotificationResponse | null | undefined) {
      if (!response?.notification) return;
      const id = response.notification.request.identifier;
      if (handledIdsRef.current.has(id)) return;
      handledIdsRef.current.add(id);
      const raw = response.notification.request.content.data;
      if (!raw || typeof raw !== 'object') return;
      navigateFromAnalysisNotificationData(router, raw as Record<string, unknown>);
    }

    // Sur `web`, certaines APIs de `expo-notifications` n'existent pas.
    // On évite l'appel à `getLastNotificationResponseAsync` pour supprimer le crash.
    const sub = (() => {
      try {
        return Notifications.addNotificationResponseReceivedListener(handleResponse);
      } catch {
        return null;
      }
    })();

    if (
      Platform.OS !== 'web' &&
      typeof (Notifications as any).getLastNotificationResponseAsync === 'function'
    ) {
      void (Notifications as any).getLastNotificationResponseAsync().then(handleResponse);
    }

    return () => {
      try {
        sub?.remove?.();
      } catch {
        /* ignore */
      }
    };
  }, [router]);

  return null;
}
