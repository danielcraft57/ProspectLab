import { useEffect, useRef } from 'react';
import { fetchAppNetworkSnapshot, subscribeAppNetwork, type AppNetworkSnapshot } from './appNetworkState';

/**
 * Exécute `effect` quand le réseau passe d’inutilisable à utilisable pour l’API
 * (reconnexion Wi‑Fi/4G, fin de mode avion, etc.). Ne déclenche pas au premier
 * rendu si l’app démarre déjà en ligne.
 */
export function useOnBecameOnline(effect: () => void, enabled: boolean = true): void {
  const cbRef = useRef(effect);
  cbRef.current = effect;
  const prevUsableRef = useRef<boolean | null>(null);
  const initializedRef = useRef(false);
  const seenOfflineRef = useRef(false);

  useEffect(() => {
    if (!enabled) {
      prevUsableRef.current = null;
      initializedRef.current = false;
      seenOfflineRef.current = false;
      return;
    }

    const consume = (snap: AppNetworkSnapshot) => {
      const usable = snap.usableForApi;
      const prev = prevUsableRef.current;
      if (!initializedRef.current) {
        initializedRef.current = true;
        seenOfflineRef.current = !usable;
        prevUsableRef.current = usable;
        return;
      }
      if (!usable) {
        seenOfflineRef.current = true;
      }
      prevUsableRef.current = usable;
      if (usable && seenOfflineRef.current && prev !== true) {
        seenOfflineRef.current = false;
        cbRef.current();
      }
    };

    void fetchAppNetworkSnapshot().then(consume).catch(() => undefined);
    const sub = subscribeAppNetwork(consume);

    return () => {
      sub();
    };
  }, [enabled]);
}
