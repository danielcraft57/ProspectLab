import { useCallback, useEffect, useState } from 'react';
import { clearProspectLabApiCache } from '../../lib/http/apiMemoryCache';
import { SecureTokenStore } from '../../lib/storage/tokenStore';

export function useApiToken() {
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

  const save = useCallback(async (nextToken: string) => {
    await SecureTokenStore.set(nextToken);
    await refresh();
  }, [refresh]);

  const clear = useCallback(async () => {
    await SecureTokenStore.clear();
    clearProspectLabApiCache();
    await refresh();
  }, [refresh]);

  return { token, loading, refresh, save, clear };
}

