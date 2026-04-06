import { useEffect, useRef, useState } from 'react';
import { FloatingAlert } from '../../ui/components';
import { useApiToken } from '../prospectlab/useToken';
import { useAppNetwork } from '../../lib/net/useAppNetwork';
import { subscribeNetworkRefreshIntent } from './networkToastBus';

/**
 * Toast global réseau: s'affiche quand la connexion devient inutilisable.
 * Reste fermable manuellement et s'auto-masque après quelques secondes.
 */
export function GlobalNetworkToast() {
  const { token } = useApiToken();
  const { usableForApi } = useAppNetwork();
  const [visible, setVisible] = useState(false);
  const [message, setMessage] = useState("Connexion perdue. L'app continue sur les données en cache.");
  const [tone, setTone] = useState<'warning' | 'success'>('warning');
  const prevUsableRef = useRef<boolean | null>(null);

  useEffect(() => {
    const prev = prevUsableRef.current;
    prevUsableRef.current = usableForApi;
    if (!token) return;
    if (prev === null) {
      if (!usableForApi) {
        setTone('warning');
        setMessage("Connexion perdue. L'app continue sur les données en cache.");
        setVisible(true);
      }
      return;
    }
    if (prev && !usableForApi) {
      setTone('warning');
      setMessage("Connexion perdue. L'app continue sur les données en cache.");
      setVisible(true);
    }
    if (!prev && usableForApi) {
      setTone('success');
      setMessage('Connexion retrouvée. Les données vont se rafraîchir.');
      setVisible(true);
    }
  }, [usableForApi, token]);

  useEffect(() => {
    const unsub = subscribeNetworkRefreshIntent(() => {
      if (!token || usableForApi) return;
      setTone('warning');
      setMessage("Toujours hors ligne. Impossible de rafraîchir pour l'instant.");
      setVisible(true);
    });
    return unsub;
  }, [token, usableForApi]);

  useEffect(() => {
    if (!visible) return;
    const tmr = setTimeout(() => setVisible(false), 5200);
    return () => clearTimeout(tmr);
  }, [visible]);

  return (
    <FloatingAlert
      visible={visible}
      message={message}
      onClose={() => setVisible(false)}
      placement="bottom"
      tone={tone}
    />
  );
}
