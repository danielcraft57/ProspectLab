import { useEffect } from 'react';
import { runAppCacheMaintenance } from '../../lib/cache/appCacheStore';

/** Exécuté une fois au démarrage : purge TTL (listes, dashboard, carte) + maintenance cache tuiles OSM + budget disque. */
export function AppCacheMaintenance() {
  useEffect(() => {
    void runAppCacheMaintenance();
  }, []);
  return null;
}
