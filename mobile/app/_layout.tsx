import 'react-native-gesture-handler';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import type { PropsWithChildren } from 'react';
import { WebsiteQueueProcessor } from '../src/features/scan/WebsiteQueueProcessor';
import { ApiTokenProvider } from '../src/features/prospectlab/apiTokenContext';
import { useExpoPushRegistration } from '../src/features/prospectlab/useExpoPushRegistration';
import { NotificationDeepLink } from '../src/lib/notifications/NotificationDeepLink';

function ExpoPushBridge({ children }: PropsWithChildren) {
  useExpoPushRegistration();
  return children;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <ApiTokenProvider>
        <WebsiteQueueProcessor />
        <ExpoPushBridge>
          <NotificationDeepLink />
          <StatusBar style="auto" />
          <Stack screenOptions={{ headerShown: false }} />
        </ExpoPushBridge>
      </ApiTokenProvider>
    </GestureHandlerRootView>
  );
}

