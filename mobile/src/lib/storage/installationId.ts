import * as SecureStore from 'expo-secure-store';

const KEY = 'prospectlab_installation_id';

function randomId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === 'function') return c.randomUUID();
  return `pl-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

/** Identifiant stable par installation (SecureStore), pour remplacer un ancien jeton Expo sur le serveur. */
export async function getOrCreateInstallationId(): Promise<string> {
  const existing = await SecureStore.getItemAsync(KEY);
  if (existing) return existing;
  const next = randomId();
  await SecureStore.setItemAsync(KEY, next);
  return next;
}
