import NetInfo, { type NetInfoState, type NetInfoStateType, type NetInfoSubscription } from '@react-native-community/netinfo';

/** Transport physique / logique côté OS (Wi‑Fi, 4G, etc.). */
export type AppTransportKind = NetInfoStateType;

export type AppNetworkSnapshot = {
  transport: AppTransportKind;
  isConnected: boolean;
  /** `null` si l’OS n’a pas encore déterminé la joignabilité Internet. */
  isInternetReachable: boolean | null;
  /**
   * Suffisant pour tenter des appels API : connecté et pas marqué explicitement
   * « sans Internet » (ex. Wi‑Fi sans route, portail captif).
   */
  usableForApi: boolean;
};

export function snapshotFromNetInfo(state: NetInfoState): AppNetworkSnapshot {
  const isConnected = !!state.isConnected;
  const reachable = state.isInternetReachable;
  const usableForApi = isConnected && reachable !== false;
  return {
    transport: state.type,
    isConnected,
    isInternetReachable: reachable ?? null,
    usableForApi,
  };
}

export async function fetchAppNetworkSnapshot(): Promise<AppNetworkSnapshot> {
  const state = await NetInfo.fetch();
  return snapshotFromNetInfo(state);
}

export function subscribeAppNetwork(listener: (snapshot: AppNetworkSnapshot) => void): NetInfoSubscription {
  return NetInfo.addEventListener((state) => {
    listener(snapshotFromNetInfo(state));
  });
}
