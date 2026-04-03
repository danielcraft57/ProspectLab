import { useEffect } from 'react';
import { runAppCacheMaintenance } from '../../lib/cache/appCacheStore';

/** Exécuté une fois au démarrage : purge TTL listes/dashboard + budget disque sur les détails. */
export function AppCacheMaintenance() {
  useEffect(() => {
    void runAppCacheMaintenance();
  }, []);
  return null;
}
