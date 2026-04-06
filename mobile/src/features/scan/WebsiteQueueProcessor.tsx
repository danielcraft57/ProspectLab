import { useCallback, useEffect, useRef } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import { ProspectLabApi } from '../prospectlab/prospectLabApi';
import { useApiToken } from '../prospectlab/useToken';
import { watchWebsiteAnalysisReport } from '../../lib/analysis/websiteAnalysisWatch';
import { useOnBecameOnline } from '../../lib/net/useOnBecameOnline';
import { loadWebsiteQueue, saveWebsiteQueue } from '../../lib/offline/websiteAnalysisQueue';
import { presentLocalNotification } from '../../lib/notifications/localNotify';

async function flushQueue(apiToken: string): Promise<void> {
  let items = await loadWebsiteQueue();
  const todo = items.filter((x) => x.status === 'queued_offline' || x.status === 'error');
  if (!todo.length) return;

  for (const item of todo) {
    items = items.map((x) => (x.id === item.id ? { ...x, status: 'syncing' as const } : x));
    await saveWebsiteQueue(items);

    try {
      await ProspectLabApi.launchWebsiteAnalysis(apiToken, item.website, false);
      items = items.map((x) =>
        x.id === item.id
          ? { ...x, status: 'synced' as const, syncedAt: Date.now(), errorMessage: undefined }
          : x,
      );
      await saveWebsiteQueue(items);
      void watchWebsiteAnalysisReport(apiToken, item.website);
      await presentLocalNotification(
        'Envoyé au serveur',
        `Analyse lancée pour ${item.label}. Tu seras notifié quand le rapport sera prêt.`,
        { type: 'website_analysis_sent', website: item.website },
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      items = items.map((x) =>
        x.id === item.id ? { ...x, status: 'error' as const, errorMessage: msg } : x,
      );
      await saveWebsiteQueue(items);
    }
  }

  const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
  items = items.filter((x) => x.status !== 'synced' || (x.syncedAt ?? 0) > cutoff);
  await saveWebsiteQueue(items);
}

/**
 * Traite la file hors-ligne quand l'app revient au premier plan et qu'un token API est présent.
 */
export function WebsiteQueueProcessor() {
  const { token, loading } = useApiToken();
  const busyRef = useRef(false);

  const run = useCallback(async () => {
    if (!token || loading || busyRef.current) return;
    busyRef.current = true;
    try {
      await ProspectLabApi.getTokenInfo(token, { skipCache: true });
      await flushQueue(token);
    } catch {
      /* hors ligne ou token invalide */
    } finally {
      busyRef.current = false;
    }
  }, [token, loading]);

  useEffect(() => {
    void run();
  }, [run]);

  useOnBecameOnline(
    useCallback(() => {
      void run();
    }, [run]),
    !!token && !loading,
  );

  useEffect(() => {
    const sub = AppState.addEventListener('change', (s: AppStateStatus) => {
      if (s === 'active') void run();
    });
    return () => sub.remove();
  }, [run]);

  return null;
}
