import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ApiTokenProvider } from '../src/features/prospectlab/apiTokenContext';

export default function RootLayout() {
  return (
    <ApiTokenProvider>
      <StatusBar style="auto" />
      <Stack screenOptions={{ headerShown: false }} />
    </ApiTokenProvider>
  );
}

