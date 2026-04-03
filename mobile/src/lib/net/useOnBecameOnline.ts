import { useEffect, useRef } from 'react';
import { subscribeAppNetwork, type AppNetworkSnapshot } from './appNetworkState';

/**
 * Exécute `effect` quand le réseau passe d’inutilisable à utilisable pour l’API
 * (reconnexion Wi‑Fi/4G, fin de mode avion, etc.). Ne déclenche pas au premier
 * rendu si l’app démarre déjà en ligne.
 */
export function useOnBecameOnline(effect: () => void, enabled: boolean = true): void {
  const cbRef = useRef(effect);
  cbRef.current = effect;
  const prevUsableRef = useRef<boolean | null>(null);

  useEffect(() => {
    if (!enabled) {
      prevUsableRef.current = null;
      return;
    }

    const sub = subscribeAppNetwork((snap: AppNetworkSnapshot) => {
      const usable = snap.usableForApi;
      const prev = prevUsableRef.current;
      prevUsableRef.current = usable;
      if (prev === false && usable) {
        cbRef.current();
      }
    });

    return () => {
      sub();
    };
  }, [enabled]);
}
