import { NetInfoStateType } from '@react-native-community/netinfo';
import { useCallback, useEffect, useState } from 'react';
import { fetchAppNetworkSnapshot, subscribeAppNetwork, type AppNetworkSnapshot } from './appNetworkState';

const OFFLINE_DEFAULT: AppNetworkSnapshot = {
  transport: NetInfoStateType.none,
  isConnected: false,
  isInternetReachable: null,
  usableForApi: false,
};

/**
 * État réseau courant (NetInfo) + rafraîchissement manuel.
 * Tant que le premier snapshot n’est pas reçu, `usableForApi` vaut `false` (prudent pour le mode hors ligne).
 */
export function useAppNetwork(): AppNetworkSnapshot & { refresh: () => Promise<void> } {
  const [snap, setSnap] = useState<AppNetworkSnapshot | null>(null);

  const refresh = useCallback(async () => {
    const s = await fetchAppNetworkSnapshot();
    setSnap(s);
  }, []);

  useEffect(() => {
    let alive = true;
    void fetchAppNetworkSnapshot().then((s) => {
      if (alive) setSnap(s);
    });
    const sub = subscribeAppNetwork((s) => setSnap(s));
    return () => {
      alive = false;
      sub();
    };
  }, []);

  return {
    ...(snap ?? OFFLINE_DEFAULT),
    refresh,
  };
}

/** Libellé court pour l’UI (bandeau, aide). */
export function formatNetworkTransportLabel(transport: AppNetworkSnapshot['transport'], usableForApi: boolean): string {
  if (!usableForApi) return 'Hors ligne';
  switch (transport) {
    case 'wifi':
      return 'Wi‑Fi';
    case 'cellular':
      return 'Données mobiles';
    case 'ethernet':
      return 'Ethernet';
    case 'vpn':
      return 'VPN';
    case 'bluetooth':
    case 'wimax':
    case 'other':
      return 'Réseau';
    case 'none':
      return 'Sans réseau';
    default:
      return 'En ligne';
  }
}
