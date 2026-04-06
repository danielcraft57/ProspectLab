import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const TOKEN_KEY = 'prospectlab_api_token_v1';

export type StoredToken = {
  token: string;
  savedAtIso: string;
};

export class SecureTokenStore {
  static async get(): Promise<StoredToken | null> {
    let raw: string | null = null;
    if (Platform.OS === 'web') {
      raw = globalThis.localStorage?.getItem(TOKEN_KEY) ?? null;
    } else {
      raw = await SecureStore.getItemAsync(TOKEN_KEY);
    }
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as StoredToken;
      if (!parsed?.token) return null;
      return parsed;
    } catch {
      return null;
    }
  }

  static async set(token: string): Promise<void> {
    const payload: StoredToken = { token: token.trim(), savedAtIso: new Date().toISOString() };
    if (Platform.OS === 'web') {
      globalThis.localStorage?.setItem(TOKEN_KEY, JSON.stringify(payload));
      return;
    }
    await SecureStore.setItemAsync(TOKEN_KEY, JSON.stringify(payload));
  }

  static async clear(): Promise<void> {
    if (Platform.OS === 'web') {
      globalThis.localStorage?.removeItem(TOKEN_KEY);
      return;
    }
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  }
}

