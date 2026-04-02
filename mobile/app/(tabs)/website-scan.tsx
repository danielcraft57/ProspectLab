import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { CameraView, useCameraPermissions, type BarcodeScanningResult } from 'expo-camera';
import { useRouter } from 'expo-router';
import { watchWebsiteAnalysisReport } from '../../src/lib/analysis/websiteAnalysisWatch';
import { checkUrlReachable } from '../../src/lib/net/checkUrlReachable';
import { enqueueWebsiteAnalysis } from '../../src/lib/offline/websiteAnalysisQueue';
import { presentLocalNotification } from '../../src/lib/notifications/localNotify';
import {
  extractWebsiteCandidates,
  normalizeWebsiteDomainForAnalysis,
} from '../../src/lib/parsing/extractWebsiteCandidates';
import { clearWebsiteScanDiscovered } from '../../src/lib/scan/websiteScanMemory';
import { recognizeImageText } from '../../src/lib/ocr/recognizeImageText';
import { ProspectLabApi } from '../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../src/features/prospectlab/useToken';
import { useCameraScanAssist } from '../../src/lib/camera/useCameraScanAssist';
import { ScanTorchFab } from '../../src/lib/camera/ScanTorchFab';
import { useScanCameraFocused } from '../../src/lib/camera/useScanCameraFocused';
import { useTheme } from '../../src/ui/theme';

type CheckState =
  | { phase: 'idle' }
  | { phase: 'checking' }
  | { phase: 'done'; ok: boolean; detail?: string };

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

export default function WebsiteScanScreen() {
  const t = useTheme();
  const { height: winH } = useWindowDimensions();
  const panelMaxH = Math.min(320, Math.round(winH * 0.42));
  const { isFocused, sessionReady, onCameraReady } = useScanCameraFocused();
  const cameraAssist = useCameraScanAssist();
  const router = useRouter();
  const { token: apiToken } = useApiToken();
  const cameraRef = useRef<CameraView | null>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [recognizedText, setRecognizedText] = useState('');
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pictureSize, setPictureSize] = useState<string | undefined>(undefined);
  const [torchOn, setTorchOn] = useState(false);
  const [checkByUrl, setCheckByUrl] = useState<Record<string, CheckState>>({});
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [sending, setSending] = useState(false);
  /** Domaines cumulés pendant que l’écran est affiché (OCR + QR), sans persistance disque. */
  const [discoveredDomains, setDiscoveredDomains] = useState<Set<string>>(() => new Set());
  const checkSeqRef = useRef(0);

  /** Ancienne version : fichier résiduel ; une fois au lancement de l’app. */
  useEffect(() => {
    void clearWebsiteScanDiscovered();
  }, []);

  /** Hors de cet écran : tout effacer (la liste ne doit pas survivre au changement de page). */
  useEffect(() => {
    if (isFocused) return;
    checkSeqRef.current += 1;
    setDiscoveredDomains(new Set());
    setRecognizedText('');
    setCheckByUrl({});
    setSelected(new Set());
    setError(null);
    void clearWebsiteScanDiscovered();
  }, [isFocused]);

  const sortedDomainsKey = useMemo(() => [...discoveredDomains].sort().join('|'), [discoveredDomains]);
  const debouncedDomainsKey = useDebounced(sortedDomainsKey, 550);
  const debouncedCandidates = useMemo(() => {
    if (discoveredDomains.size === 0) return [];
    const key = debouncedDomainsKey;
    return key ? key.split('|').filter(Boolean) : [];
  }, [discoveredDomains.size, debouncedDomainsKey]);

  useEffect(() => {
    if (!recognizedText.trim()) return;
    setDiscoveredDomains((prev) => {
      const next = new Set(prev);
      for (const raw of extractWebsiteCandidates(recognizedText)) {
        const d = normalizeWebsiteDomainForAnalysis(raw);
        if (d) next.add(d);
      }
      return next;
    });
  }, [recognizedText]);

  const handleBarcodeScanned = useCallback((result: BarcodeScanningResult) => {
    const data = (result.data ?? '').trim();
    if (!data) return;
    const domain = normalizeWebsiteDomainForAnalysis(data);
    if (!domain) return;
    setDiscoveredDomains((prev) => new Set(prev).add(domain));
    setError(null);
  }, []);

  const configureCamera = useCallback(async () => {
    if (!cameraRef.current) return;
    try {
      const sizes = await cameraRef.current.getAvailablePictureSizesAsync();
      const best = [...sizes]
        .map((s) => {
          const m = /^(\d+)\s*x\s*(\d+)$/i.exec(String(s).trim());
          const w = m ? Number(m[1]) : 0;
          const h = m ? Number(m[2]) : 0;
          return { s, px: w * h };
        })
        .sort((a, b) => b.px - a.px)[0]?.s;
      if (best) setPictureSize(best);
    } catch {
      /* ignore */
    }
  }, []);

  const scanOnce = useCallback(async () => {
    if (!cameraRef.current || isBusy || sending) return;
    setIsBusy(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.72,
        shutterSound: false,
        skipProcessing: true,
      });
      if (!photo?.uri) return;
      const text = await recognizeImageText(photo.uri);
      setRecognizedText(text);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsBusy(false);
    }
  }, [isBusy, sending]);

  useEffect(() => {
    if (!isFocused) {
      setTorchOn(false);
    }
  }, [isFocused]);

  useEffect(() => {
    if (!permission) return;
    if (!permission.granted) {
      requestPermission().catch(() => undefined);
    }
  }, [permission, requestPermission]);

  useEffect(() => {
    if (!sessionReady || !isFocused) return;
    configureCamera().catch(() => undefined);
  }, [configureCamera, sessionReady, isFocused]);

  useEffect(() => {
    if (!isFocused || !permission?.granted) return;
    const id = setInterval(() => {
      scanOnce().catch(() => undefined);
    }, 1800);
    return () => clearInterval(id);
  }, [isFocused, permission?.granted, scanOnce]);

  useEffect(() => {
    const seq = ++checkSeqRef.current;
    const urls = [...debouncedCandidates];
    setSelected((prev) => {
      const n = new Set<string>();
      for (const u of prev) {
        if (urls.includes(u)) n.add(u);
      }
      return n;
    });
    setCheckByUrl(() => {
      const next: Record<string, CheckState> = {};
      for (const u of urls) {
        next[u] = { phase: 'idle' };
      }
      return next;
    });

    (async () => {
      for (const url of urls) {
        if (seq !== checkSeqRef.current) return;
        setCheckByUrl((prev) => ({ ...prev, [url]: { phase: 'checking' } }));
        const r = await checkUrlReachable(url);
        if (seq !== checkSeqRef.current) return;
        setCheckByUrl((prev) => ({
          ...prev,
          [url]: {
            phase: 'done',
            ok: r.ok,
            detail: r.ok ? `HTTP ${r.status ?? '—'}` : r.error ?? 'Inaccessible',
          },
        }));
        if (r.ok) {
          setSelected((prev) => new Set(prev).add(url));
        }
      }
    })().catch(() => undefined);
  }, [debouncedCandidates.join('|')]);

  const rows = useMemo(
    () =>
      debouncedCandidates.map((url) => ({
        url,
        host: shortHost(url),
        state: checkByUrl[url] ?? { phase: 'idle' },
      })),
    [debouncedCandidates, checkByUrl],
  );

  const reachableCount = rows.filter((r) => r.state.phase === 'done' && r.state.ok).length;

  const onToggle = useCallback((url: string) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(url)) n.delete(url);
      else n.add(url);
      return n;
    });
  }, []);

  const onSend = useCallback(async () => {
    if (!apiToken) {
      Alert.alert('Token manquant', 'Configure ton token API dans Réglages.');
      return;
    }
    const urls = [...selected].filter((u) => {
      const c = checkByUrl[u];
      return c?.phase === 'done' && c.ok === true;
    });
    if (!urls.length) {
      Alert.alert('Aucune URL valide', 'Sélectionne au moins un site joignable (coche verte).');
      return;
    }

    setSending(true);
    try {
      let online = false;
      try {
        await ProspectLabApi.getTokenInfo(apiToken, { skipCache: true });
        online = true;
      } catch {
        online = false;
      }

      if (!online) {
        for (const website of urls) {
          await enqueueWebsiteAnalysis({
            id: newQueueId(),
            website,
            label: shortHost(website),
            createdAt: Date.now(),
          });
        }
        await presentLocalNotification(
          'Hors ligne',
          `${urls.length} analyse(s) mise(s) en file. Envoi automatique à la reconnexion.`,
          { type: 'website_queue_offline', count: urls.length },
        );
        router.back();
        return;
      }

      for (const website of urls) {
        try {
          await ProspectLabApi.launchWebsiteAnalysis(apiToken, website, false);
          void watchWebsiteAnalysisReport(apiToken, website);
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : String(e);
          Alert.alert('Erreur', `${shortHost(website)} : ${msg}`);
        }
      }

      await presentLocalNotification(
        'Demandes envoyées',
        `${urls.length} analyse(s) lancée(s) sur le serveur. Tu seras notifié à la fin du traitement.`,
        { type: 'website_batch_sent', count: urls.length },
      );
      router.back();
    } finally {
      setSending(false);
    }
  }, [apiToken, checkByUrl, router, selected]);

  if (Platform.OS === 'web') {
    return (
      <View style={[styles.centered, { backgroundColor: t.colors.bg }]}>
        <Text style={[styles.title, { color: t.colors.text }]}>Scan non disponible</Text>
        <Text style={[styles.subtitle, { color: t.colors.muted }]}>Utilise l&apos;app Android ou iOS.</Text>
        <Pressable style={[styles.actionBtn, { backgroundColor: t.colors.primary }]} onPress={() => router.back()}>
          <Text style={[styles.actionLabel, { color: t.colors.primaryText }]}>Retour</Text>
        </Pressable>
      </View>
    );
  }

  if (!apiToken) {
    return (
      <View style={[styles.centered, { backgroundColor: t.colors.bg }]}>
        <Text style={[styles.title, { color: t.colors.text }]}>Token API requis</Text>
        <Text style={[styles.subtitle, { color: t.colors.muted }]}>Configure le token dans Réglages pour lancer une analyse.</Text>
        <Pressable style={[styles.actionBtn, { backgroundColor: t.colors.primary }]} onPress={() => router.replace('/(tabs)/settings')}>
          <Text style={[styles.actionLabel, { color: t.colors.primaryText }]}>Réglages</Text>
        </Pressable>
      </View>
    );
  }

  if (!permission?.granted) {
    return (
      <View style={[styles.centered, { backgroundColor: t.colors.bg }]}>
        <Text style={[styles.title, { color: t.colors.text }]}>Accès caméra</Text>
        <Text style={[styles.subtitle, { color: t.colors.muted }]}>
          Indispensable pour lire un QR code ou une adresse sur papier ou écran.
        </Text>
        <Pressable style={[styles.actionBtn, { backgroundColor: t.colors.primary }]} onPress={() => requestPermission()}>
          <Text style={[styles.actionLabel, { color: t.colors.primaryText }]}>Autoriser</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={styles.cameraSlot}>
        {isFocused ? (
          <>
            <CameraView
              ref={cameraRef}
              style={StyleSheet.absoluteFill}
              facing="back"
              animateShutter={false}
              active={isFocused}
              autofocus={cameraAssist.autofocus}
              pictureSize={pictureSize}
              zoom={cameraAssist.zoom}
              flash={torchOn ? 'off' : cameraAssist.flash}
              enableTorch={isFocused && torchOn}
              onCameraReady={onCameraReady}
              barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
              onBarcodeScanned={handleBarcodeScanned}
            />

            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Prendre une photo pour détecter des liens"
              disabled={isBusy || sending}
              onPress={() => void scanOnce()}
              style={[StyleSheet.absoluteFill, styles.cameraTapLayer]}
            />
            <View style={styles.overlay} pointerEvents="none">
              <View style={styles.topShade} />
              <View style={styles.middleRow}>
                <View style={styles.sideShade} />
                <View style={[styles.frame, { borderColor: reachableCount > 0 ? t.colors.success : t.colors.warning }]}>
                  <Text style={styles.frameHint}>Texte ou QR — tape n’importe où sur la vue</Text>
                </View>
                <View style={styles.sideShade} />
              </View>
              <View style={styles.bottomShade} />
            </View>
            <ScanTorchFab enabled={torchOn} onToggle={() => setTorchOn((v) => !v)} />
          </>
        ) : (
          <View style={[StyleSheet.absoluteFill, styles.cameraPaused]} />
        )}
      </View>

      <View
        style={[
          styles.bottomPanel,
          {
            backgroundColor: t.colors.card,
            borderTopColor: t.colors.border,
            maxHeight: panelMaxH,
          },
        ]}
      >
        <View style={styles.panelGrab} />
        <Text style={[styles.panelTitle, { color: t.colors.text }]}>Liens repérés</Text>
        <Text style={[styles.hint, { color: t.colors.muted }]} numberOfLines={rows.length > 0 ? 2 : 3}>
          {rows.length > 0
            ? 'Coche les sites joignables puis lance l’analyse.'
            : 'Vise un QR ou une URL dans le cadre. Chaque capture peut ajouter des liens.'}
        </Text>

        {rows.length === 0 ? (
          <Text style={[styles.empty, { color: t.colors.muted }]} numberOfLines={2}>
            Scan actif — place le lien dans le cadre au-dessus.
          </Text>
        ) : (
          <FlatList
            data={rows}
            keyExtractor={(item) => item.url}
            style={styles.list}
            nestedScrollEnabled
            renderItem={({ item }) => {
              const sel = selected.has(item.url);
              const st = item.state;
              const doneOk = st.phase === 'done' && st.ok;
              const doneBad = st.phase === 'done' && !st.ok;
              return (
                <Pressable
                  onPress={() => doneOk && onToggle(item.url)}
                  style={[
                    styles.row,
                    {
                      borderColor: doneOk ? (sel ? t.colors.success : t.colors.border) : t.colors.border,
                      opacity: doneOk ? 1 : 0.72,
                    },
                  ]}
                >
                  <View style={[styles.dot, { backgroundColor: doneOk ? t.colors.success : doneBad ? t.colors.danger : t.colors.warning }]} />
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={[styles.host, { color: t.colors.text }]} numberOfLines={1}>
                      {item.host}
                    </Text>
                    {st.phase === 'checking' && (
                      <Text style={[styles.meta, { color: t.colors.muted }]}>Test de joignabilité…</Text>
                    )}
                    {st.phase === 'done' && (
                      <Text style={[styles.meta, { color: doneOk ? t.colors.success : t.colors.danger }]} numberOfLines={1}>
                        {doneOk ? (sel ? 'Sélectionné — envoi prévu' : 'Joignable — appuie pour cocher') : (st as { detail?: string }).detail}
                      </Text>
                    )}
                  </View>
                  {st.phase === 'checking' && <ActivityIndicator size="small" color={t.colors.primary} />}
                  {doneOk && (
                    <Text style={[styles.check, { color: sel ? t.colors.success : t.colors.muted }]}>{sel ? '✓' : '○'}</Text>
                  )}
                </Pressable>
              );
            }}
          />
        )}

        {!!error && <Text style={[styles.error, { color: t.colors.danger }]}>{error}</Text>}

        <View style={styles.actions}>
          <Pressable
            style={[styles.secondaryBtn, { borderColor: t.colors.border, backgroundColor: t.colors.bg }]}
            disabled={sending}
            onPress={() => router.back()}
          >
            <Text style={[styles.secondaryLabel, { color: t.colors.text }]}>Fermer</Text>
          </Pressable>
          <Pressable
            style={[styles.actionBtn, { backgroundColor: selected.size && apiToken && !sending ? t.colors.primary : t.colors.border }]}
            disabled={!selected.size || !apiToken || sending}
            onPress={() => void onSend()}
          >
            <Text style={[styles.actionLabel, { color: selected.size && apiToken ? t.colors.primaryText : t.colors.muted }]}>
              {sending ? 'Envoi…' : `Analyser (${selected.size})`}
            </Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  cameraSlot: { flex: 1, overflow: 'hidden' },
  cameraPaused: { backgroundColor: '#000' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 22, gap: 10 },
  title: { fontSize: 20, fontWeight: '800', textAlign: 'center' },
  subtitle: { fontSize: 14, textAlign: 'center' },
  cameraTapLayer: { zIndex: 1 },
  overlay: { ...StyleSheet.absoluteFillObject, zIndex: 2 },
  topShade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.52)' },
  middleRow: { height: 188, flexDirection: 'row' },
  sideShade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.52)' },
  frame: {
    width: 278,
    borderWidth: 3,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingBottom: 6,
    backgroundColor: 'rgba(20,20,20,0.12)',
  },
  frameHint: { color: '#fff', fontWeight: '700', fontSize: 10, textAlign: 'center', paddingHorizontal: 6 },
  bottomShade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.52)' },
  bottomPanel: {
    flexShrink: 0,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    paddingHorizontal: 14,
    paddingTop: 6,
    paddingBottom: 10,
    gap: 6,
    elevation: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  panelGrab: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: 'rgba(128,128,128,0.45)',
    marginBottom: 2,
  },
  panelTitle: { fontWeight: '800', fontSize: 13 },
  hint: { fontSize: 11, lineHeight: 14 },
  empty: { fontSize: 12, paddingVertical: 6 },
  list: { flexGrow: 0, maxHeight: 128 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 6,
  },
  dot: { width: 7, height: 7, borderRadius: 4 },
  host: { fontWeight: '700', fontSize: 12 },
  meta: { fontSize: 10, marginTop: 1 },
  check: { fontSize: 16, fontWeight: '900' },
  error: { fontSize: 11 },
  actions: { flexDirection: 'row', gap: 8, marginTop: 2 },
  actionBtn: {
    flex: 1,
    minHeight: 42,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionLabel: { fontWeight: '800', fontSize: 13 },
  secondaryBtn: {
    flex: 1,
    minHeight: 42,
    borderWidth: 1,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryLabel: { fontWeight: '700', fontSize: 13 },
});
