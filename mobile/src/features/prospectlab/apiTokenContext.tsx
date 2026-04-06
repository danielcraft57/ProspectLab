import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { clearProspectLabApiCache } from '../../lib/http/apiMemoryCache';
import { SecureTokenStore } from '../../lib/storage/tokenStore';

export type ApiTokenContextValue = {
  token: string | null;
  loading: boolean;
  refresh: () => Promise<void>;
  save: (nextToken: string) => Promise<void>;
  clear: () => Promise<void>;
};

const ApiTokenContext = createContext<ApiTokenContextValue | null>(null);

export function ApiTokenProvider({ children }: PropsWithChildren) {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const stored = await SecureTokenStore.get();
      setToken(stored?.token ?? null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const save = useCallback(
    async (nextToken: string) => {
      await SecureTokenStore.set(nextToken);
      await refresh();
    },
    [refresh],
  );

  const clear = useCallback(async () => {
    await SecureTokenStore.clear();
    clearProspectLabApiCache();
    await refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ token, loading, refresh, save, clear }),
    [token, loading, refresh, save, clear],
  );

  return <ApiTokenContext.Provider value={value}>{children}</ApiTokenContext.Provider>;
}

export function useApiToken(): ApiTokenContextValue {
  const ctx = useContext(ApiTokenContext);
  if (!ctx) {
    throw new Error('useApiToken doit etre utilise dans un ApiTokenProvider');
  }
  return ctx;
}
