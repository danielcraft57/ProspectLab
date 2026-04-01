import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { CameraView, useCameraPermissions, type BarcodeScanningResult } from 'expo-camera';
import { ProspectLabApi } from '../src/features/prospectlab/prospectLabApi';
import { extractApiTokenFromOcrText } from '../src/lib/ocr/extractApiToken';
import { recognizeImageText } from '../src/lib/ocr/recognizeImageText';
import { useTheme } from '../src/ui/theme';

export default function TokenOcrScreen() {
  const t = useTheme();
  const router = useRouter();
  const cameraRef = useRef<CameraView | null>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [recognizedText, setRecognizedText] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pictureSize, setPictureSize] = useState<string | undefined>(undefined);
  const [ready, setReady] = useState(false);
  const [stableToken, setStableToken] = useState<string | null>(null);
  const stableCountRef = useRef(0);
  const prevExtractedTokenRef = useRef<string | null>(null);
  const verifySeqRef = useRef(0);
  const apiVerifiedOkRef = useRef(false);
  const verifyLoadingRef = useRef(false);
  const tokenRef = useRef<string | null>(null);
  const [verify, setVerify] = useState<
    | null
    | { loading: true }
    | { ok: true; status: 200 }
    | { ok: false; status: number; message: string }
  >(null);

  const token = useMemo(() => extractApiTokenFromOcrText(recognizedText), [recognizedText]);

  tokenRef.current = token;

  useEffect(() => {
    if (!token) {
      setVerify(null);
      return;
    }
    const seq = ++verifySeqRef.current;
    setVerify({ loading: true });
    const tid = setTimeout(() => {
      ProspectLabApi.validateToken(token).then((r) => {
        if (seq !== verifySeqRef.current) return;
        setVerify(r);
      });
    }, 450);
    return () => clearTimeout(tid);
  }, [token]);

  useEffect(() => {
    apiVerifiedOkRef.current = !!(verify && 'ok' in verify && verify.ok);
    verifyLoadingRef.current = !!(verify && 'loading' in verify && verify.loading);
  }, [verify]);

  const handleBarcodeScanned = useCallback((result: BarcodeScanningResult) => {
    const data = (result?.data ?? '').trim();
    if (!data) return;
    const extracted =
      extractApiTokenFromOcrText(data) ?? (/^[a-f0-9]{48,128}$/i.test(data) ? data : null);
    if (!extracted) return;
    setRecognizedText(data);
    setError(null);
  }, []);

  const configureCamera = useCallback(async () => {
    if (!cameraRef.current) return;
    try {
      const sizes = await cameraRef.current.getAvailablePictureSizesAsync();
      // On prend la plus grande taille disponible (souvent "1920x1080" ou "4032x3024")
      // pour maximiser les chances OCR sur un texte petit.
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
      // Si l'API n'est pas dispo sur l'appareil, on garde les defaults.
    }
  }, []);

  const scanOnce = useCallback(async () => {
    if (!cameraRef.current || isBusy) return;
    if (stableToken) return;
    // Ne pas écraser le token avec du bruit OCR une fois l'API OK (sinon plus de "Valider").
    if (apiVerifiedOkRef.current) return;
    // Pendant la requête de validation, garder le dernier texte reconnu.
    if (verifyLoadingRef.current && tokenRef.current) return;
    setIsBusy(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.75,
        shutterSound: false,
        skipProcessing: true,
      });
      if (!photo?.uri) return;
      const text = await recognizeImageText(photo.uri);
      setRecognizedText(text);
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setIsBusy(false);
    }
  }, [isBusy, stableToken]);

  useEffect(() => {
    if (!permission) return;
    if (!permission.granted) {
      requestPermission().catch(() => undefined);
      return;
    }
    setIsScanning(true);
  }, [permission, requestPermission]);

  useEffect(() => {
    if (!ready) return;
    configureCamera().catch(() => undefined);
  }, [configureCamera, ready]);

  useEffect(() => {
    if (!isScanning || !permission?.granted) return;
    if (stableToken) return;
    const interval = setInterval(() => {
      scanOnce().catch(() => undefined);
    }, 1700);
    return () => clearInterval(interval);
  }, [isScanning, permission?.granted, scanOnce, stableToken]);

  useEffect(() => {
    if (!token) {
      stableCountRef.current = 0;
      prevExtractedTokenRef.current = null;
      setStableToken(null);
      return;
    }
    if (prevExtractedTokenRef.current !== token) {
      stableCountRef.current = 0;
      prevExtractedTokenRef.current = token;
    }
    // 3 detections consecutives identiques (evite les faux positifs / OCR bruité).
    if (stableToken === token) return;
    stableCountRef.current += 1;
    if (stableCountRef.current >= 3) {
      setStableToken(token);
      stableCountRef.current = 0;
    }
  }, [stableToken, token]);

  /** 3 lectures OCR stables, ou token confirmé par l'API (ex. scan QR puis OCR qui efface le texte). */
  const canValidate =
    !!token && (stableToken !== null || !!(verify && 'ok' in verify && verify.ok));

  const tokenToSave = stableToken ?? token;

  const displayToken = stableToken ?? token;

  if (!permission?.granted) {
    return (
      <View style={[styles.centered, { backgroundColor: t.colors.bg }]}>
        <Text style={[styles.title, { color: t.colors.text }]}>Autorisation caméra requise</Text>
        <Text style={[styles.subtitle, { color: t.colors.muted }]}>Active l'accès caméra pour scanner ton token.</Text>
        <Pressable style={[styles.actionBtn, { backgroundColor: t.colors.primary }]} onPress={() => requestPermission()}>
          <Text style={[styles.actionLabel, { color: t.colors.primaryText }]}>Autoriser</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing="back"
        animateShutter={false}
        // `on` = une mise au point puis verrouillage (mauvais pour texte OCR). `off` = continu.
        autofocus="off"
        pictureSize={pictureSize}
        zoom={0.1}
        onCameraReady={() => setReady(true)}
        barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={handleBarcodeScanned}
      />

      <View style={styles.overlay}>
        <View style={styles.topShade} />
        <View style={styles.middleRow}>
          <View style={styles.sideShade} />
          <View style={[styles.frame, { borderColor: token ? t.colors.success : t.colors.warning }]}>
            <Text style={styles.frameHint}>QR code ou texte du token dans le cadre</Text>
          </View>
          <View style={styles.sideShade} />
        </View>
        <View style={styles.bottomShade} />
      </View>

      <View style={[styles.bottomPanel, { backgroundColor: t.colors.card, borderColor: t.colors.border }]}>
        <Text style={[styles.panelTitle, { color: t.colors.text }]}>Token détecté</Text>
        <View style={[styles.resultBox, { borderColor: displayToken ? t.colors.success : t.colors.border, backgroundColor: t.colors.bg }]}>
          <Text style={[styles.resultToken, { color: displayToken ? t.colors.text : t.colors.muted }]} selectable>
            {displayToken ?? '—'}
          </Text>
          <View style={styles.verifyRow}>
            {!token && <Text style={[styles.verifyLine, { color: t.colors.muted }]}>En attente du scan…</Text>}
            {!!token && (!verify || ('loading' in verify && verify.loading)) && (
              <>
                <ActivityIndicator size="small" color={t.colors.primary} />
                <Text style={[styles.verifyLine, { color: t.colors.muted }]}> Vérification API…</Text>
              </>
            )}
            {!!token && verify && 'ok' in verify && verify.ok && (
              <Text style={[styles.verifyLine, { color: t.colors.success }]}>HTTP {verify.status} — token accepté</Text>
            )}
            {!!token && verify && 'ok' in verify && !verify.ok && (
              <Text
                style={[
                  styles.verifyLine,
                  { color: verify.status === 401 ? t.colors.danger : t.colors.warning },
                ]}
              >
                HTTP {verify.status}
                {verify.status === 401 ? ' — refusé (token invalide)' : ` — ${verify.message}`}
              </Text>
            )}
          </View>
        </View>
        {!!error && <Text style={[styles.error, { color: t.colors.danger }]}>{error}</Text>}
        <View style={styles.actions}>
          <Pressable style={[styles.secondaryBtn, { borderColor: t.colors.border, backgroundColor: t.colors.bg }]} onPress={() => router.back()}>
            <Text style={[styles.secondaryLabel, { color: t.colors.text }]}>Annuler</Text>
          </Pressable>
          <Pressable
            style={[styles.actionBtn, { backgroundColor: canValidate ? t.colors.primary : t.colors.border }]}
            disabled={!canValidate}
            onPress={() => {
              if (!canValidate || !tokenToSave) return;
              router.replace(`/(tabs)/settings?ocrToken=${encodeURIComponent(tokenToSave)}`);
            }}
          >
            <Text style={[styles.actionLabel, { color: canValidate ? t.colors.primaryText : t.colors.muted }]}>Valider</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  title: { fontSize: 20, fontWeight: '800' },
  subtitle: { marginTop: 8, textAlign: 'center' },
  overlay: { ...StyleSheet.absoluteFillObject },
  topShade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  middleRow: { height: 220, flexDirection: 'row' },
  sideShade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  frame: {
    width: 300,
    borderWidth: 3,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingBottom: 10,
    backgroundColor: 'rgba(20,20,20,0.14)',
  },
  frameHint: { color: '#fff', fontWeight: '700', fontSize: 12 },
  bottomShade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  bottomPanel: {
    position: 'absolute',
    left: 12,
    right: 12,
    bottom: 20,
    borderWidth: 1,
    borderRadius: 16,
    padding: 12,
    gap: 8,
  },
  panelTitle: { fontWeight: '800', fontSize: 14 },
  resultBox: { borderWidth: 1, borderRadius: 12, padding: 10, gap: 8 },
  resultToken: { fontFamily: 'monospace', fontSize: 12, fontWeight: '700' },
  verifyRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', minHeight: 22 },
  verifyLine: { fontSize: 12, fontWeight: '600' },
  error: { fontSize: 12 },
  actions: { flexDirection: 'row', gap: 10, marginTop: 4 },
  actionBtn: {
    flex: 1,
    minHeight: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 14,
  },
  actionLabel: { fontWeight: '800' },
  secondaryBtn: {
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 14,
  },
  secondaryLabel: { fontWeight: '700' },
});
