import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { CameraView, useCameraPermissions, type BarcodeScanningResult } from 'expo-camera';
import { ProspectLabApi } from '../../src/features/prospectlab/prospectLabApi';
import { extractApiTokenFromOcrText } from '../../src/lib/ocr/extractApiToken';
import { recognizeImageText } from '../../src/lib/ocr/recognizeImageText';
import { useCameraScanAssist } from '../../src/lib/camera/useCameraScanAssist';
import { ScanTorchFab } from '../../src/lib/camera/ScanTorchFab';
import { useScanCameraFocused } from '../../src/lib/camera/useScanCameraFocused';
import { useTheme } from '../../src/ui/theme';

export default function TokenOcrScreen() {
  const t = useTheme();
  const { height: winH } = useWindowDimensions();
  const { isFocused, sessionReady, onCameraReady } = useScanCameraFocused();
  const cameraAssist = useCameraScanAssist();
  const panelMaxH = Math.min(236, Math.round(winH * 0.34));
  const router = useRouter();
  const cameraRef = useRef<CameraView | null>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [recognizedText, setRecognizedText] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pictureSize, setPictureSize] = useState<string | undefined>(undefined);
  const [torchOn, setTorchOn] = useState(false);
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

  useFocusEffect(
    useCallback(() => {
      return () => {
        verifySeqRef.current += 1;
        stableCountRef.current = 0;
        prevExtractedTokenRef.current = null;
        apiVerifiedOkRef.current = false;
        verifyLoadingRef.current = false;
        tokenRef.current = null;
        setRecognizedText('');
        setStableToken(null);
        setError(null);
        setVerify(null);
        setIsBusy(false);
        setTorchOn(false);
      };
    }, []),
  );

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
    if (!isFocused) {
      setTorchOn(false);
    }
  }, [isFocused]);

  useEffect(() => {
    if (!permission) return;
    if (!permission.granted) {
      requestPermission().catch(() => undefined);
      return;
    }
    setIsScanning(true);
  }, [permission, requestPermission]);

  useEffect(() => {
    if (!sessionReady || !isFocused) return;
    configureCamera().catch(() => undefined);
  }, [configureCamera, sessionReady, isFocused]);

  useEffect(() => {
    if (!isFocused || !isScanning || !permission?.granted) return;
    if (stableToken) return;
    const interval = setInterval(() => {
      scanOnce().catch(() => undefined);
    }, 1700);
    return () => clearInterval(interval);
  }, [isFocused, isScanning, permission?.granted, scanOnce, stableToken]);

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
              accessibilityLabel="Prendre une photo pour analyse OCR"
              disabled={isBusy || !!stableToken}
              onPress={() => void scanOnce()}
              style={[StyleSheet.absoluteFill, styles.cameraTapLayer]}
            />
            <View style={styles.overlay} pointerEvents="none">
              <View style={styles.topShade} />
              <View style={styles.middleRow}>
                <View style={styles.sideShade} />
                <View style={[styles.frame, { borderColor: token ? t.colors.success : t.colors.warning }]}>
                  <Text style={styles.frameHint}>QR ou texte — tape n’importe où sur la vue</Text>
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
        <Text style={[styles.panelTitle, { color: t.colors.text }]}>Token détecté</Text>
        <View style={[styles.resultBox, { borderColor: displayToken ? t.colors.success : t.colors.border, backgroundColor: t.colors.bg }]}>
          <Text
            style={[styles.resultToken, { color: displayToken ? t.colors.text : t.colors.muted }]}
            selectable
            numberOfLines={1}
            ellipsizeMode="middle"
          >
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
              <Text style={[styles.verifyLine, { color: t.colors.success }]} numberOfLines={1}>
                HTTP {verify.status} — accepté
              </Text>
            )}
            {!!token && verify && 'ok' in verify && !verify.ok && (
              <Text
                style={[
                  styles.verifyLine,
                  { color: verify.status === 401 ? t.colors.danger : t.colors.warning },
                ]}
                numberOfLines={2}
              >
                HTTP {verify.status}
                {verify.status === 401 ? ' — refusé' : ` — ${verify.message}`}
              </Text>
            )}
          </View>
        </View>
        {!!error && (
          <Text style={[styles.error, { color: t.colors.danger }]} numberOfLines={2}>
            {error}
          </Text>
        )}
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
  cameraSlot: { flex: 1, overflow: 'hidden' },
  cameraPaused: { backgroundColor: '#000' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  title: { fontSize: 20, fontWeight: '800' },
  subtitle: { marginTop: 8, textAlign: 'center' },
  cameraTapLayer: { zIndex: 1 },
  overlay: { ...StyleSheet.absoluteFillObject, zIndex: 2 },
  topShade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  middleRow: { height: 200, flexDirection: 'row' },
  sideShade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  frame: {
    width: 280,
    borderWidth: 3,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingBottom: 8,
    backgroundColor: 'rgba(20,20,20,0.14)',
  },
  frameHint: { color: '#fff', fontWeight: '700', fontSize: 11 },
  bottomShade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
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
    shadowOpacity: 0.35,
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
  panelTitle: { fontWeight: '800', fontSize: 12 },
  resultBox: { borderWidth: 1, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 6, gap: 4 },
  resultToken: { fontFamily: 'monospace', fontSize: 11, fontWeight: '700' },
  verifyRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', minHeight: 18 },
  verifyLine: { fontSize: 11, fontWeight: '600' },
  error: { fontSize: 11 },
  actions: { flexDirection: 'row', gap: 8, marginTop: 2 },
  actionBtn: {
    flex: 1,
    minHeight: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 12,
  },
  actionLabel: { fontWeight: '800', fontSize: 13 },
  secondaryBtn: {
    flex: 1,
    minHeight: 40,
    borderWidth: 1,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 12,
  },
  secondaryLabel: { fontWeight: '700', fontSize: 13 },
});
