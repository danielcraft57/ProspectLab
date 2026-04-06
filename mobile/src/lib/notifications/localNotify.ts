import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';

async function ensureAndroidChannel() {
  if (Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync('default', {
    name: 'ProspectLab',
    importance: Notifications.AndroidImportance.HIGH,
  });
}

/** Notification locale immédiate (hors push serveur). */
export async function presentLocalNotification(title: string, body: string, data?: Record<string, unknown>) {
  await ensureAndroidChannel();
  await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: data ?? undefined,
      sound: 'default',
    },
    trigger: null,
  });
}
