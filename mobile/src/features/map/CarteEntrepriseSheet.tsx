import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  Dimensions,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import Svg, { Rect } from 'react-native-svg';
import type { CarteMapMarker } from './carteMapTypes';
import { normalizeOpportunityLabel, scoreSecurityBucket } from './markerPalette';
import { ProspectLabApi } from '../prospectlab/prospectLabApi';
import { HttpError } from '../../lib/http/httpClient';
import { ReportImageGallery } from '../../ui/analysis/ReportImageGallery';
import { useTheme } from '../../ui/theme';

function securityLabel(bucket: string): string {
  if (bucket === 'crit') return 'Élevé (risque)';
  if (bucket === 'mid') return 'Moyen';
  if (bucket === 'ok') return 'Faible';
  return 'Non renseigné';
}

function pickNum(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim()) {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function extractAnalysisScores(report: unknown): {
  techSecurity: number | null;
  techPerformance: number | null;
  seo: number | null;
  pentestRisk: number | null;
  technicalDone: boolean;
  seoDone: boolean;
  pentestDone: boolean;
} {
  const out = {
    techSecurity: null as number | null,
    techPerformance: null as number | null,
    seo: null as number | null,
    pentestRisk: null as number | null,
    technicalDone: false,
    seoDone: false,
    pentestDone: false,
  };
  if (!report || typeof report !== 'object') return out;
  const r = report as Record<string, unknown>;
  const tech = r.technical as Record<string, unknown> | undefined;
  const seo = r.seo as Record<string, unknown> | undefined;
  const pent = r.pentest as Record<string, unknown> | undefined;
  const techLatest = tech?.latest as Record<string, unknown> | undefined;
  const seoLatest = seo?.latest as Record<string, unknown> | undefined;
  const pentLatest = pent?.latest as Record<string, unknown> | undefined;
  out.technicalDone = tech?.status === 'done';
  out.seoDone = seo?.status === 'done';
  out.pentestDone = pent?.status === 'done';
  out.techSecurity = pickNum(techLatest?.security_score);
  out.techPerformance = pickNum(techLatest?.performance_score);
  out.seo = pickNum(seoLatest?.score);
  out.pentestRisk = pickNum(pentLatest?.risk_score);
  return out;
}

function mergeGalleryUrls(
  apiImages: Array<Record<string, unknown>>,
  extra: Array<string | null | undefined>,
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  const push = (u: string | null | undefined) => {
    if (!u || typeof u !== 'string') return;
    const s = u.trim();
    if (!s || seen.has(s)) return;
    seen.add(s);
    out.push(s);
  };
  for (const im of apiImages) {
    push(typeof im.url === 'string' ? im.url : null);
  }
  for (const e of extra) push(e);
  return out;
}

function BarGauge({
  value,
  max,
  color,
  trackColor,
  label,
  suffix,
}: {
  value: number;
  max: number;
  color: string;
  trackColor: string;
  label: string;
  suffix?: string;
}) {
  const w = 260;
  const h = 10;
  const pct = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  const fillW = Math.max(0, w * pct);
  return (
    <View style={styles.gaugeBlock}>
      <Text style={styles.gaugeLabel}>{label}</Text>
      <Svg width={w} height={h}>
        <Rect x={0} y={0} width={w} height={h} rx={5} ry={5} fill={trackColor} />
        <Rect x={0} y={0} width={fillW} height={h} rx={5} ry={5} fill={color} />
      </Svg>
      <Text style={styles.gaugeValue}>
        {Math.round(value * 10) / 10}
        {suffix ?? ''}
      </Text>
    </View>
  );
}

function FadeIn({ children, show }: { children: ReactNode; show: boolean }) {
  const o = useRef(new Animated.Value(show ? 1 : 0)).current;
  useEffect(() => {
    Animated.timing(o, {
      toValue: show ? 1 : 0,
      duration: 280,
      useNativeDriver: true,
    }).start();
  }, [show, o]);
  return <Animated.View style={{ opacity: o }}>{children}</Animated.View>;
}

export function CarteEntrepriseSheet({
  visible,
  marker,
  token,
  onClose,
}: {
  visible: boolean;
  marker: CarteMapMarker | null;
  token: string | null;
  onClose: () => void;
}) {
  const t = useTheme();
  const slide = useRef(new Animated.Value(320)).current;
  const fade = useRef(new Animated.Value(0)).current;

  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailErr, setDetailErr] = useState<string | null>(null);
  const [entrepriseRow, setEntrepriseRow] = useState<Record<string, unknown> | null>(null);
  const [analysisReport, setAnalysisReport] = useState<unknown>(null);
  const [analysisFetchFailed, setAnalysisFetchFailed] = useState(false);
  const [galleryUris, setGalleryUris] = useState<string[]>([]);

  const winW = Dimensions.get('window').width;
  const galleryWidth = Math.max(280, winW - 40);

  useEffect(() => {
    if (visible) {
      slide.setValue(320);
      fade.setValue(0);
      Animated.parallel([
        Animated.spring(slide, { toValue: 0, useNativeDriver: true, friction: 9, tension: 65 }),
        Animated.timing(fade, { toValue: 1, duration: 220, useNativeDriver: true }),
      ]).start();
    }
  }, [visible, slide, fade]);

  useEffect(() => {
    if (!visible || !marker || !token) {
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    setDetailErr(null);
    setEntrepriseRow(null);
    setAnalysisReport(null);
    setAnalysisFetchFailed(false);
    setGalleryUris([]);

    (async () => {
      try {
        const entRes = await ProspectLabApi.getEntreprise(token, marker.id, { skipCache: true });
        if (cancelled) return;
        const row = (entRes?.data as Record<string, unknown> | undefined) ?? null;
        setEntrepriseRow(row);

        let imgs: Array<Record<string, unknown>> = [];
        try {
          const galRes = await ProspectLabApi.getEntrepriseGallery(token, marker.id, { skipCache: true });
          if (!cancelled && Array.isArray(galRes?.data?.images)) {
            imgs = galRes.data!.images as Array<Record<string, unknown>>;
          }
        } catch {
          /* Route /gallery absente, proxy 405, etc. — la fiche reste affichée avec og_image/logo. */
        }
        if (cancelled) return;
        const merged = mergeGalleryUrls(imgs, [
          row?.og_image as string | undefined,
          row?.logo as string | undefined,
        ]);
        setGalleryUris(merged);
      } catch (e: unknown) {
        if (!cancelled) {
          setDetailErr(e instanceof Error ? e.message : String(e));
        }
      }

      if (marker.website && !cancelled) {
        try {
          const rep = await ProspectLabApi.getWebsiteAnalysis(token, marker.website, false, { skipCache: true });
          if (!cancelled) {
            setAnalysisReport(rep);
            setAnalysisFetchFailed(false);
          }
        } catch (e: unknown) {
          if (!cancelled) {
            if (e instanceof HttpError && e.info.status === 404) {
              setAnalysisReport(null);
            } else {
              setAnalysisFetchFailed(true);
            }
          }
        }
      }

      if (!cancelled) setLoadingDetail(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [visible, token, marker?.id, marker?.website]);

  const scores = useMemo(() => extractAnalysisScores(analysisReport), [analysisReport]);

  if (!marker) return null;

  const bucket = scoreSecurityBucket(marker.score_securite ?? undefined);
  const secColor =
    bucket === 'crit' ? t.colors.danger : bucket === 'mid' ? t.colors.warning : t.colors.success;

  const str = (v: unknown) => (typeof v === 'string' && v.trim() ? v.trim() : '');
  const row = entrepriseRow;
  const email = str(row?.email_principal);
  const phone = str(row?.telephone);
  const addr1 = str(row?.address_1);
  const addr2 = str(row?.address_2);
  const pays = str(row?.pays);
  const resume = str(row?.resume);
  const cms = str(row?.cms);
  const framework = str(row?.framework);

  const openWebsite = () => {
    const w = marker.website;
    if (!w) return;
    const u = w.startsWith('http') ? w : `https://${w}`;
    void Linking.openURL(u).catch(() => {});
  };

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onClose}>
      <View style={styles.modalRoot}>
        <Animated.View style={[styles.backdrop, { opacity: fade }]}>
          <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        </Animated.View>
        <Animated.View
          style={[
            styles.sheet,
            {
              backgroundColor: t.colors.card,
              borderColor: t.colors.border,
              transform: [{ translateY: slide }],
            },
          ]}
        >
          <View style={styles.sheetHeaderSlot}>
            <View style={styles.grabberWrap}>
              <View style={[styles.grabber, { backgroundColor: t.colors.border }]} />
            </View>
            <Pressable
              onPress={onClose}
              hitSlop={12}
              accessibilityRole="button"
              accessibilityLabel="Fermer"
              style={({ pressed }) => [
                styles.closeIconWrap,
                {
                  backgroundColor: pressed ? t.colors.bg : 'transparent',
                  borderColor: t.colors.border,
                },
              ]}
            >
              <MaterialCommunityIcons name="close" size={22} color={t.colors.text} />
            </Pressable>
          </View>
          <ScrollView
            style={styles.scroll}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
          >
            <View style={styles.titleRow}>
              <View
                style={[
                  styles.titleIconCircle,
                  {
                    backgroundColor: marker.pinColor,
                    borderColor: '#ffffff',
                  },
                ]}
              >
                <MaterialCommunityIcons
                  name={marker.iconMaterial as 'domain'}
                  size={22}
                  color="#ffffff"
                />
              </View>
              <Text
                style={[styles.title, { color: t.colors.text, flex: 1 }]}
                numberOfLines={3}
                {...Platform.select({
                  android: { includeFontPadding: false },
                  default: {},
                })}
              >
                {marker.title}
              </Text>
            </View>
            {marker.website ? (
              <Pressable onPress={openWebsite}>
                <Text style={[styles.meta, { color: t.colors.primary }]} numberOfLines={2}>
                  {marker.website}
                </Text>
              </Pressable>
            ) : null}

            {!!detailErr && (
              <Text style={[styles.warnBanner, { color: t.colors.danger, backgroundColor: t.colors.bg }]}>
                {detailErr}
              </Text>
            )}

            {token && loadingDetail ? (
              <View style={[styles.inlineLoader, { marginTop: 12 }]}>
                <ActivityIndicator color={t.colors.primary} size="small" />
                <Text style={{ color: t.colors.muted, marginLeft: 10, flex: 1 }}>
                  Chargement détail, galerie et scores d’analyses…
                </Text>
              </View>
            ) : null}

            <View style={styles.badges}>
              {marker.secteur ? (
                <View style={[styles.badge, { backgroundColor: t.colors.bg, borderColor: t.colors.border }]}>
                  <Text style={[styles.badgeText, { color: t.colors.muted }]}>Secteur</Text>
                  <Text style={[styles.badgeVal, { color: t.colors.text }]}>{marker.secteur}</Text>
                </View>
              ) : null}
              {marker.statut ? (
                <View style={[styles.badge, { backgroundColor: t.colors.bg, borderColor: t.colors.border }]}>
                  <Text style={[styles.badgeText, { color: t.colors.muted }]}>Statut</Text>
                  <Text style={[styles.badgeVal, { color: t.colors.text }]}>{marker.statut}</Text>
                </View>
              ) : null}
              {email ? (
                <View style={[styles.badge, { backgroundColor: t.colors.bg, borderColor: t.colors.border }]}>
                  <Text style={[styles.badgeText, { color: t.colors.muted }]}>E-mail</Text>
                  <Text style={[styles.badgeVal, { color: t.colors.text }]} numberOfLines={2}>
                    {email}
                  </Text>
                </View>
              ) : null}
              {phone ? (
                <View style={[styles.badge, { backgroundColor: t.colors.bg, borderColor: t.colors.border }]}>
                  <Text style={[styles.badgeText, { color: t.colors.muted }]}>Téléphone</Text>
                  <Text style={[styles.badgeVal, { color: t.colors.text }]}>{phone}</Text>
                </View>
              ) : null}
            </View>

            {(addr1 || addr2 || pays) ? (
              <View style={[styles.addrCard, { borderColor: t.colors.border, backgroundColor: t.colors.bg }]}>
                <Text style={[styles.sectionTitle, { color: t.colors.text, marginBottom: 6 }]}>Adresse</Text>
                {addr1 ? <Text style={{ color: t.colors.text }}>{addr1}</Text> : null}
                {addr2 ? <Text style={{ color: t.colors.text }}>{addr2}</Text> : null}
                {pays ? <Text style={{ color: t.colors.muted, marginTop: 4 }}>{pays}</Text> : null}
              </View>
            ) : null}

            {(cms || framework) ? (
              <View style={[styles.addrCard, { borderColor: t.colors.border, backgroundColor: t.colors.bg }]}>
                <Text style={[styles.sectionTitle, { color: t.colors.text, marginBottom: 6 }]}>Stack (fiche)</Text>
                {cms ? (
                  <Text style={{ color: t.colors.muted }}>
                    CMS : <Text style={{ color: t.colors.text, fontWeight: '700' }}>{cms}</Text>
                  </Text>
                ) : null}
                {framework ? (
                  <Text style={{ color: t.colors.muted, marginTop: 4 }}>
                    Framework : <Text style={{ color: t.colors.text, fontWeight: '700' }}>{framework}</Text>
                  </Text>
                ) : null}
              </View>
            ) : null}

            {resume ? (
              <View style={[styles.addrCard, { borderColor: t.colors.border, backgroundColor: t.colors.bg }]}>
                <Text style={[styles.sectionTitle, { color: t.colors.text, marginBottom: 6 }]}>Résumé</Text>
                <Text style={{ color: t.colors.text, lineHeight: 22 }}>{resume}</Text>
              </View>
            ) : null}

            <View style={[styles.levelCard, { borderColor: t.colors.border, backgroundColor: t.colors.bg }]}>
              <Text style={[styles.sectionTitle, { color: t.colors.text }]}>Niveaux</Text>
              <Text style={{ color: t.colors.muted, marginBottom: 8 }}>
                Opportunité :{' '}
                <Text style={{ color: t.colors.text, fontWeight: '700' }}>
                  {normalizeOpportunityLabel(marker.opportunite)}
                </Text>
              </Text>
              <Text style={{ color: t.colors.muted }}>
                Sécurité (score) :{' '}
                <Text style={{ color: secColor, fontWeight: '800' }}>{securityLabel(bucket)}</Text>
                {marker.score_securite != null ? ` · ${marker.score_securite}/100` : ''}
              </Text>
            </View>

            <Text style={[styles.sectionTitle, { color: t.colors.text, marginTop: 16 }]}>Galerie</Text>
            {!token ? (
              <Text style={{ color: t.colors.muted, marginTop: 6 }}>
                Connecte un jeton API pour charger les visuels de la fiche.
              </Text>
            ) : !loadingDetail && galleryUris.length > 0 ? (
              <FadeIn show>
                <ReportImageGallery uris={galleryUris} containerWidth={galleryWidth} />
              </FadeIn>
            ) : !loadingDetail ? (
              <Text style={{ color: t.colors.muted, marginTop: 6 }}>Aucune image indexée pour cette fiche.</Text>
            ) : null}

            <Text style={[styles.sectionTitle, { color: t.colors.text, marginTop: 18 }]}>Scores analyses web</Text>
            {!token ? (
              <Text style={{ color: t.colors.muted, marginTop: 6 }}>
                Connecte un jeton API pour afficher les scores technique, SEO et pentest.
              </Text>
            ) : !loadingDetail ? (
              <FadeIn show>
                {!marker.website ? (
                  <Text style={{ color: t.colors.muted }}>Pas de site web sur la fiche — analyses indisponibles.</Text>
                ) : analysisFetchFailed ? (
                  <Text style={{ color: t.colors.muted }}>Analyses web indisponibles (erreur réseau ou serveur).</Text>
                ) : analysisReport == null ? (
                  <Text style={{ color: t.colors.muted }}>
                    Aucun rapport d’analyse enregistré pour ce domaine. Lance une analyse depuis l’onglet Site web.
                  </Text>
                ) : (
                  <View>
                    <Text style={[styles.hint, { color: t.colors.muted }]}>
                      Dernières analyses connues pour le domaine (technique, SEO, pentest).
                    </Text>
                    {scores.techSecurity != null ? (
                      <BarGauge
                        label="Technique — sécurité (0–100)"
                        value={scores.techSecurity}
                        max={100}
                        color={t.colors.warning}
                        trackColor={t.colors.border}
                      />
                    ) : (
                      <Text style={{ color: t.colors.muted, marginTop: 8 }}>
                        Technique — sécurité : {scores.technicalDone ? 'non renseigné' : 'pas d’analyse'}
                      </Text>
                    )}
                    {scores.techPerformance != null ? (
                      <BarGauge
                        label="Technique — performance (0–100)"
                        value={scores.techPerformance}
                        max={100}
                        color={t.colors.primary}
                        trackColor={t.colors.border}
                      />
                    ) : (
                      <Text style={{ color: t.colors.muted, marginTop: 10 }}>
                        Technique — performance : {scores.technicalDone ? 'non renseigné' : 'pas d’analyse'}
                      </Text>
                    )}
                    {scores.seo != null ? (
                      <BarGauge
                        label="SEO (0–100)"
                        value={scores.seo}
                        max={100}
                        color="#7c3aed"
                        trackColor={t.colors.border}
                      />
                    ) : (
                      <Text style={{ color: t.colors.muted, marginTop: 10 }}>
                        SEO : {scores.seoDone ? 'non renseigné' : 'pas d’analyse'}
                      </Text>
                    )}
                    {scores.pentestRisk != null ? (
                      <>
                        <BarGauge
                          label="Pentest — indice de risque (0–100)"
                          value={scores.pentestRisk}
                          max={100}
                          color={scores.pentestRisk >= 60 ? t.colors.danger : t.colors.warning}
                          trackColor={t.colors.border}
                        />
                        <Text style={[styles.hint, { color: t.colors.muted, marginTop: 4 }]}>
                          Plus la valeur est élevée, plus des vulnérabilités ou expositions ont été signalées.
                        </Text>
                      </>
                    ) : (
                      <Text style={{ color: t.colors.muted, marginTop: 10 }}>
                        Pentest : {scores.pentestDone ? 'non renseigné' : 'pas d’analyse'}
                      </Text>
                    )}
                  </View>
                )}
              </FadeIn>
            ) : null}

            <Text style={[styles.sectionTitle, { color: t.colors.text, marginTop: 16 }]}>Graphiques</Text>
            {marker.score_securite != null ? (
              <BarGauge
                label="Score sécurité fiche (0–100)"
                value={marker.score_securite}
                max={100}
                color={secColor}
                trackColor={t.colors.border}
              />
            ) : (
              <Text style={{ color: t.colors.muted, marginTop: 8 }}>Score sécurité : non renseigné</Text>
            )}
            {marker.note_google != null ? (
              <BarGauge
                label="Note Google (0–5)"
                value={marker.note_google}
                max={5}
                color={t.colors.primary}
                trackColor={t.colors.border}
                suffix={marker.nb_avis_google != null ? ` · ${marker.nb_avis_google} avis` : ''}
              />
            ) : (
              <Text style={{ color: t.colors.muted, marginTop: 10 }}>Note Google : non renseignée</Text>
            )}
          </ScrollView>
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalRoot: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  sheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderWidth: StyleSheet.hairlineWidth,
    maxHeight: '85%',
    paddingBottom: Platform.OS === 'ios' ? 28 : 20,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: -4 },
        shadowOpacity: 0.15,
        shadowRadius: 12,
      },
      android: { elevation: 16 },
      default: {},
    }),
  },
  sheetHeaderSlot: {
    position: 'relative',
    paddingTop: 10,
    marginBottom: 4,
    minHeight: 36,
  },
  grabberWrap: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  grabber: {
    width: 40,
    height: 4,
    borderRadius: 2,
  },
  closeIconWrap: {
    position: 'absolute',
    right: 10,
    top: 4,
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scroll: { maxHeight: '100%' },
  scrollContent: { paddingHorizontal: 20, paddingBottom: 24 },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  titleIconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.12,
    shadowRadius: 2,
    elevation: 2,
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    letterSpacing: -0.3,
    lineHeight: 28,
    flexShrink: 1,
  },
  meta: { fontSize: 14, marginTop: 6 },
  warnBanner: {
    marginTop: 10,
    padding: 10,
    borderRadius: 10,
    fontSize: 13,
  },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 14 },
  badge: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 12,
    paddingVertical: 8,
    paddingHorizontal: 12,
    minWidth: '45%',
    flexGrow: 1,
  },
  badgeText: { fontSize: 11, fontWeight: '600', textTransform: 'uppercase', marginBottom: 4 },
  badgeVal: { fontSize: 15, fontWeight: '700' },
  addrCard: {
    marginTop: 12,
    padding: 14,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
  },
  levelCard: {
    marginTop: 16,
    padding: 14,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
  },
  sectionTitle: { fontSize: 15, fontWeight: '800', marginBottom: 10 },
  hint: { fontSize: 12, lineHeight: 18, marginBottom: 6 },
  gaugeBlock: { marginTop: 12 },
  gaugeLabel: { fontSize: 12, fontWeight: '600', marginBottom: 6, opacity: 0.85 },
  gaugeValue: { fontSize: 12, marginTop: 6, fontWeight: '600', opacity: 0.8 },
  inlineLoader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 4,
  },
});
