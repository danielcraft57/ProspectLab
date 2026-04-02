import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { watchWebsiteAnalysisReport } from '../../src/lib/analysis/websiteAnalysisWatch';
import { checkUrlReachable } from '../../src/lib/net/checkUrlReachable';
import {
  enqueueWebsiteAnalysis,
  loadWebsiteQueue,
  pendingQueueCount,
} from '../../src/lib/offline/websiteAnalysisQueue';
import { presentLocalNotification } from '../../src/lib/notifications/localNotify';
import { normalizeWebsiteDomainForAnalysis } from '../../src/lib/parsing/extractWebsiteCandidates';
import { ProspectLabApi } from '../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../src/features/prospectlab/useToken';
import { Card, FadeIn, H2, MutedText, PrimaryButton, Screen } from '../../src/ui/components';
import { useTheme } from '../../src/ui/theme';

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function newQueueId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === 'function') return c.randomUUID();
  return `q-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

function shortHost(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url.length > 42 ? `${url.slice(0, 40)}…` : url;
  }
}

type ReachState =
  | { phase: 'idle' }
  | { phase: 'checking' }
  | { phase: 'done'; ok: boolean; detail?: string };

export default function WebsiteScreen() {
  const t = useTheme();
  const router = useRouter();
  const { token } = useApiToken();
  const [urlInput, setUrlInput] = useState('');
  const [reach, setReach] = useState<ReachState>({ phase: 'idle' });
  const [analyzeBusy, setAnalyzeBusy] = useState(false);
  const checkSeqRef = useRef(0);
  const [queuePending, setQueuePending] = useState(0);

  const debouncedUrl = useDebounced(urlInput.trim(), 520);
  const normalizedWebsite = useMemo(
    () => (debouncedUrl ? normalizeWebsiteDomainForAnalysis(debouncedUrl) : null),
    [debouncedUrl],
  );

  const refreshQueue = useCallback(() => {
    void loadWebsiteQueue().then((q) => setQueuePending(pendingQueueCount(q)));
  }, []);

  useFocusEffect(
    useCallback(() => {
      refreshQueue();
    }, [refreshQueue]),
  );

  useLayoutEffect(() => {
    if (!normalizedWebsite) {
      setReach({ phase: 'idle' });
      return;
    }
    setReach({ phase: 'checking' });
  }, [normalizedWebsite]);

  useEffect(() => {
    if (!normalizedWebsite) return;
    const seq = ++checkSeqRef.current;
    void checkUrlReachable(normalizedWebsite).then((r) => {
      if (seq !== checkSeqRef.current) return;
      setReach({
        phase: 'done',
        ok: r.ok,
        detail: r.ok ? `Réponse ${r.status ?? '—'}` : r.error ?? 'Site injoignable',
      });
    });
  }, [normalizedWebsite]);

  const canLaunchFromUrl =
    !!token && reach.phase === 'done' && reach.ok === true && !!normalizedWebsite && !analyzeBusy;

  const launchWebsiteAnalysisFlow = useCallback(
    async (website: string) => {
      if (!token) {
        Alert.alert('Connexion requise', 'Ajoute ton token API dans Réglages pour lancer une analyse.');
        return;
      }
      setAnalyzeBusy(true);
      try {
        let online = false;
        try {
          await ProspectLabApi.getTokenInfo(token, { skipCache: true });
          online = true;
        } catch {
          online = false;
        }

        const label = shortHost(website);

        if (!online) {
          await enqueueWebsiteAnalysis({
            id: newQueueId(),
            website,
            label,
            createdAt: Date.now(),
          });
          await presentLocalNotification(
            'Hors ligne',
            `${label} est en file : envoi automatique dès que le réseau revient.`,
            { type: 'website_queue_offline', count: 1 },
          );
          refreshQueue();
          setUrlInput('');
          setReach({ phase: 'idle' });
          return;
        }

        await ProspectLabApi.launchWebsiteAnalysis(token, website, false);
        void watchWebsiteAnalysisReport(token, website);
        await presentLocalNotification(
          'Analyse lancée',
          `On s’occupe de ${label}. Tu recevras une notif quand le rapport est prêt.`,
          { type: 'website_batch_sent', count: 1 },
        );
        setUrlInput('');
        setReach({ phase: 'idle' });
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        Alert.alert('Impossible d’envoyer', msg);
      } finally {
        setAnalyzeBusy(false);
      }
    },
    [refreshQueue, token],
  );

  const reachLabel = (() => {
    if (!urlInput.trim()) return null;
    if (urlInput.trim() !== debouncedUrl) {
      return { tone: 'muted' as const, text: 'Tu peux finir de taper — on vérifie juste après.' };
    }
    if (!normalizedWebsite) {
      return { tone: 'muted' as const, text: 'Adresse incomplète ou invalide — vérifie le domaine.' };
    }
    if (reach.phase === 'checking') {
      return { tone: 'muted' as const, text: 'On teste si le site répond…' };
    }
    if (reach.phase === 'done' && reach.ok) {
      return { tone: 'ok' as const, text: `Tout bon — ${reach.detail}. Tu peux lancer l’analyse.` };
    }
    if (reach.phase === 'done' && !reach.ok) {
      return { tone: 'bad' as const, text: `Le site ne répond pas comme prévu (${reach.detail}).` };
    }
    return null;
  })();

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <FadeIn>
          <Card style={queuePending > 0 ? { borderWidth: 1, borderColor: t.colors.warning } : undefined}>
            <View style={styles.row}>
              <MaterialCommunityIcons name="link-variant" size={18} color="#4f8cff" />
              <H2>Taper une adresse</H2>
            </View>
            <MutedText style={{ marginTop: 8 }}>
              Colle une URL ou un domaine (ex. exemple.fr). Après une courte pause, on ping le site pour confirmer
              qu’il répond.
            </MutedText>
            {queuePending > 0 && (
              <MutedText style={{ marginTop: 8, fontWeight: '700', color: t.colors.warning }}>
                {queuePending} demande{queuePending > 1 ? 's' : ''} en attente de réseau — envoi dès reconnexion.
              </MutedText>
            )}
            <TextInput
              value={urlInput}
              onChangeText={setUrlInput}
              placeholder="https://… ou monsite.com"
              placeholderTextColor={t.colors.muted}
              selectionColor={t.colors.primary}
              keyboardType="url"
              autoCapitalize="none"
              autoCorrect={false}
              style={[
                styles.urlField,
                {
                  borderColor: t.colors.border,
                  color: t.colors.text,
                  backgroundColor: t.colors.bg,
                },
              ]}
            />
            <View style={styles.reachRow}>
              {reach.phase === 'checking' && <ActivityIndicator size="small" color={t.colors.primary} />}
              {!!reachLabel && (
                <Text
                  style={[
                    styles.reachText,
                    {
                      color:
                        reachLabel.tone === 'ok'
                          ? t.colors.success
                          : reachLabel.tone === 'bad'
                            ? t.colors.danger
                            : t.colors.muted,
                    },
                  ]}
                >
                  {reachLabel.text}
                </Text>
              )}
            </View>
            <View style={{ marginTop: 10 }}>
              <PrimaryButton
                title={analyzeBusy ? 'Envoi…' : 'Lancer l’analyse pour ce site'}
                onPress={() => {
                  if (normalizedWebsite) void launchWebsiteAnalysisFlow(normalizedWebsite);
                }}
                disabled={!canLaunchFromUrl}
              />
            </View>
            {!token && (
              <MutedText style={{ marginTop: 8 }}>
                Connecte-toi avec un token API (Réglages) pour débloquer l’envoi.
              </MutedText>
            )}
          </Card>
        </FadeIn>

        <FadeIn delayMs={40}>
          <Card>
            <View style={styles.row}>
              <MaterialCommunityIcons name="camera-outline" size={18} color="#4f8cff" />
              <H2>Par la caméra</H2>
            </View>
            <MutedText style={{ marginTop: 8 }}>
              Vise un QR code, une URL sur une carte ou un écran : on extrait le lien, on teste la joignabilité, tu
              choisis quoi envoyer — comme pour la saisie manuelle.
            </MutedText>
            <View style={{ marginTop: 12 }}>
              <PrimaryButton
                title="Ouvrir la caméra"
                onPress={() => {
                  if (Platform.OS === 'web') {
                    Alert.alert('Pas sur le web', 'La caméra est disponible sur l’app Android ou iOS.');
                    return;
                  }
                  if (!token) {
                    Alert.alert('Token requis', 'Configure d’abord ton accès API dans Réglages.');
                    return;
                  }
                  router.push('/website-scan');
                }}
              />
            </View>
          </Card>
        </FadeIn>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  urlField: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    marginTop: 12,
    fontSize: 16,
  },
  reachRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 10,
    minHeight: 22,
  },
  reachText: { flex: 1, fontSize: 13, fontWeight: '600' },
});
