type Listener = () => void;

const listeners = new Set<Listener>();

export function subscribeNetworkRefreshIntent(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Appelé quand l'utilisateur force un refresh (pull-to-refresh / bouton). */
export function emitNetworkRefreshIntent(): void {
  for (const l of listeners) l();
}
