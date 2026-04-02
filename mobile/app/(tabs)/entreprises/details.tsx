import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  LayoutAnimation,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  UIManager,
  Text,
  View,
  useWindowDimensions,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import { ProspectLabApi } from '../../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../../src/features/prospectlab/useToken';
import { ReportImageGallery } from '../../../src/ui/analysis/ReportImageGallery';
import { WebsiteAnalysisSection, type AnalysisKind } from '../../../src/ui/analysis/WebsiteAnalysisViews';
import { Card, FadeIn, H2, Mono, MutedText, Screen } from '../../../src/ui/components';
import { MaterialAsyncLoader } from '../../../src/ui/MaterialAsyncLoader';
import { useTheme } from '../../../src/ui/theme';
import { useDetailScreenHeader } from '../../../src/ui/useDetailScreenHeader';

type DetailKind = 'website' | 'email' | 'phone' | 'id';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

function decodeParam(v: unknown): string | null {
  const s = Array.isArray(v) ? v[0] : v;
  if (typeof s !== 'string') return null;
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

function tryParseJson(v: unknown): unknown {
  if (typeof v !== 'string') return v;
  const s = v.trim();
  if (!s) return v;
  if (!(s.startsWith('{') || s.startsWith('['))) return v;
  try {
    return JSON.parse(s);
  } catch {
    return v;
  }
}

const IMAGE_PATH_EXT = /\.(png|jpe?g|webp|gif|avif|svg)(\?.*)?$/i;

function isImageUri(s: string) {
  const v = s.trim();
  if (!v) return false;
  const lower = v.toLowerCase();
  if (lower.startsWith('data:image/')) return true;
  if (lower.startsWith('http://') || lower.startsWith('https://')) {
    try {
      const path = new URL(v).pathname.toLowerCase();
      return IMAGE_PATH_EXT.test(path);
    } catch {
      return false;
    }
  }
  if (v.startsWith('/')) {
    const path = v.split('?')[0].toLowerCase();
    return IMAGE_PATH_EXT.test(path);
  }
  return false;
}

function findImageUris(obj: unknown, limit = 6): string[] {
  const out: string[] = [];
  const seen = new Set<string>();

  function walk(x: unknown) {
    if (out.length >= limit) return;
    if (!x) return;
    if (typeof x === 'string') {
      const s = x.trim();
      if (s && isImageUri(s) && !seen.has(s)) {
        seen.add(s);
        out.push(s);
      }
      return;
    }
    if (Array.isArray(x)) {
      for (const it of x) walk(it);
      return;
    }
    if (typeof x === 'object') {
      for (const k of Object.keys(x as any)) walk((x as any)[k]);
    }
  }

  walk(obj);
  return out;
}

function numFromApi(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim() !== '' && !Number.isNaN(Number(v))) return Number(v);
  return undefined;
}

function normalizeEntreprise(raw: any) {
  const ent = raw?.entreprise ?? raw;
  return {
    id: typeof ent?.id === 'number' ? ent.id : undefined,
    nom: typeof ent?.nom === 'string' ? ent.nom : typeof ent?.name === 'string' ? ent.name : undefined,
    website: typeof ent?.website === 'string' ? ent.website : typeof ent?.url === 'string' ? ent.url : undefined,
    secteur: typeof ent?.secteur === 'string' ? ent.secteur : undefined,
    statut: typeof ent?.statut === 'string' ? ent.statut : undefined,
    opportunite: typeof ent?.opportunite === 'string' ? ent.opportunite : undefined,
    score_seo: numFromApi(ent?.score_seo),
    score_pentest: numFromApi(ent?.score_pentest),
    score_securite: numFromApi(ent?.score_securite),
    performance_score: numFromApi(ent?.performance_score),
    email_principal:
      typeof ent?.email_principal === 'string'
        ? ent.email_principal
        : typeof ent?.email === 'string'
          ? ent.email
          : undefined,
    telephone: typeof ent?.telephone === 'string' ? ent.telephone : typeof ent?.phone === 'string' ? ent.phone : undefined,
    raw: ent,
  };
}

type EntrepriseNorm = ReturnType<typeof normalizeEntreprise>;

function fmtShortDate(d: unknown): string | undefined {
  if (d == null) return undefined;
  const s = String(d);
  return s.length >= 10 ? s.slice(0, 10) : s;
}

function hintOpportunite(ent: EntrepriseNorm | null): string | undefined {
  if (!ent?.opportunite) return undefined;
  return `Opportunité · ${ent.opportunite}`;
}

function seoSubtitle(report: any, ent: EntrepriseNorm | null): string {
  const st = report?.seo?.status;
  const row = report?.seo?.latest;
  const opp = hintOpportunite(ent);
  if (st === 'never') {
    if (ent?.score_seo != null) return `Réf. fiche · score SEO ${ent.score_seo}${opp ? ` · ${opp}` : ''}`;
    return opp ?? 'Pas encore d’analyse enregistrée sur ce site';
  }
  if (st === 'done') {
    const parts: string[] = [];
    if (row && typeof row.score === 'number') parts.push(`Dernière analyse · score ${row.score}`);
    else if (ent?.score_seo != null) parts.push(`Fiche · score SEO ${ent.score_seo}`);
    const d = fmtShortDate(row?.date_analyse);
    if (d) parts.push(d);
    if (opp) parts.push(opp);
    return parts.join(' · ') || 'Analyse disponible';
  }
  return opp ?? '—';
}

function technicalSubtitle(report: any, ent: EntrepriseNorm | null): string {
  const st = report?.technical?.status;
  const row = report?.technical?.latest;
  const opp = hintOpportunite(ent);
  if (st === 'never') {
    if (ent?.score_securite != null) return `Réf. fiche · score sécurité ${ent.score_securite}${opp ? ` · ${opp}` : ''}`;
    return opp ?? 'Pas d’analyse technique en base';
  }
  if (st === 'done') {
    const parts: string[] = ['Dernière analyse technique'];
    const d = fmtShortDate(row?.date_analyse);
    if (d) parts.push(d);
    if (ent?.score_securite != null) parts.push(`fiche · sécurité ${ent.score_securite}`);
    if (opp) parts.push(opp);
    return parts.join(' · ');
  }
  return opp ?? '—';
}

function pentestSubtitle(report: any, ent: EntrepriseNorm | null): string {
  const st = report?.pentest?.status;
  const row = report?.pentest?.latest;
  const opp = hintOpportunite(ent);
  if (st === 'never') {
    if (ent?.score_pentest != null) return `Réf. fiche · risque pentest ${ent.score_pentest}${opp ? ` · ${opp}` : ''}`;
    return opp ?? 'Pas de pentest enregistré';
  }
  if (st === 'done') {
    const parts: string[] = [];
    if (row && typeof row.risk_score === 'number') parts.push(`Risque ${row.risk_score}/100`);
    else if (ent?.score_pentest != null) parts.push(`Fiche · risque ${ent.score_pentest}`);
    const d = fmtShortDate(row?.date_analyse);
    if (d) parts.push(d);
    if (opp) parts.push(opp);
    return parts.join(' · ') || 'Rapport pentest disponible';
  }
  return opp ?? '—';
}

function osintSubtitle(report: any, ent: EntrepriseNorm | null): string {
  const st = report?.osint?.status;
  const row = report?.osint?.latest;
  const opp = hintOpportunite(ent);
  if (st === 'never') return opp ?? 'Pas d’OSINT en base';
  if (st === 'done') {
    const parts: string[] = ['Collecte disponible'];
    const d = fmtShortDate(row?.date_analyse);
    if (d) parts.push(d);
    if (opp) parts.push(opp);
    return parts.join(' · ');
  }
  return opp ?? '—';
}

export default function EntrepriseDetailsScreen() {
  const t = useTheme();
  const { token, loading: tokenLoading } = useApiToken();
  const params = useLocalSearchParams<{ kind?: string; value?: string }>();

  const [loadingEntreprise, setLoadingEntreprise] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [campagnesLoading, setCampagnesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [emails, setEmails] = useState<any[] | null>(null);
  const [phones, setPhones] = useState<any[] | null>(null);
  const [phonesApi, setPhonesApi] = useState<any[] | null>(null);
  const [campagnes, setCampagnes] = useState<any[] | null>(null);
  const [openAnalysis, setOpenAnalysis] = useState<AnalysisKind | null>(null);
  const [rawExpanded, setRawExpanded] = useState(false);
  const { width: windowWidth } = useWindowDimensions();

  const kind = useMemo(() => {
    const k = params.kind;
    const s = Array.isArray(k) ? k[0] : k;
    if (s === 'website' || s === 'email' || s === 'phone' || s === 'id') return s;
    return null;
  }, [params.kind]);

  const value = useMemo(() => decodeParam(params.value), [params.value]);

  const load = useCallback(
    async (opts?: { skipCache?: boolean }) => {
      if (!token) return;
      if (!kind || !value) return;

      const skipCache = !!opts?.skipCache;
      const c = { skipCache };

      if (skipCache) {
        setRefreshing(true);
      } else {
        setLoadingEntreprise(true);
        setError(null);
        setRaw(null);
        setReport(null);
        setCampagnes(null);
        setPhonesApi(null);
        setReportLoading(false);
        setContactsLoading(false);
        setCampagnesLoading(false);
      }

      try {
        let res: any;
        if (kind === 'id') {
          const id = parseInt(String(value || ''), 10);
          if (!Number.isFinite(id)) {
            setError('Identifiant entreprise invalide.');
            return;
          }
          res = await ProspectLabApi.getEntreprise(token, id, c);
        } else if (kind === 'website') res = await ProspectLabApi.findEntrepriseByWebsite(token, value, c);
        else if (kind === 'email') res = await ProspectLabApi.findEntrepriseByEmail(token, value, true, c);
        else res = await ProspectLabApi.findEntrepriseByPhone(token, value, true, c);

        const base = res?.data ?? res;
        setRaw(base);

        if (Array.isArray(base?.emails)) setEmails(base.emails);
        else setEmails(null);
        if (Array.isArray(base?.phones)) setPhones(base.phones);
        else setPhones(null);

        const ent = normalizeEntreprise(base);
        const entrepriseId = ent.id;
        const website = (ent.website || '').trim();

        setLoadingEntreprise(false);

        const pending: Promise<unknown>[] = [];

        if (website) {
          setReportLoading(true);
          pending.push(
            ProspectLabApi.getWebsiteAnalysis(token, website, true, c)
              .then((r) => setReport(r?.data ?? r))
              .catch(() => setReport(null))
              .finally(() => setReportLoading(false)),
          );
        } else {
          setReport(null);
        }

        if (entrepriseId) {
          setContactsLoading(true);
          pending.push(
            Promise.all([
              ProspectLabApi.listEntrepriseEmailsAll(token, entrepriseId, true, c)
                .then((r) => setEmails((r?.data ?? r) as any[]))
                .catch(() => {}),
              ProspectLabApi.listEntreprisePhones(token, entrepriseId, true, c)
                .then((r) => setPhonesApi((r?.data ?? r) as any[]))
                .catch(() => setPhonesApi(null)),
            ]).finally(() => setContactsLoading(false)),
          );

          setCampagnesLoading(true);
          pending.push(
            ProspectLabApi.listCampagnesByEntreprise(token, entrepriseId, { limit: 50, offset: 0 }, c)
              .then((r) => setCampagnes((r?.data ?? r) as any[]))
              .catch(() => setCampagnes(null))
              .finally(() => setCampagnesLoading(false)),
          );
        } else {
          setCampagnes(null);
          setPhonesApi(null);
        }

        if (skipCache && pending.length) {
          await Promise.all(pending);
        }
      } catch (e: any) {
        setError(e?.message ?? 'Erreur lors du chargement des details.');
      } finally {
        setLoadingEntreprise(false);
        if (skipCache) setRefreshing(false);
      }
    },
    [token, kind, value],
  );

  useEffect(() => {
    load();
  }, [load]);

  const entreprise = useMemo(() => (raw ? normalizeEntreprise(raw) : null), [raw]);
  const phonesList = useMemo(() => phonesApi ?? phones ?? [], [phonesApi, phones]);
  const displayTitle = entreprise?.nom ?? '';
  useDetailScreenHeader({
    title: displayTitle,
    fallbackTitle: 'Entreprise',
    listPath: '/(tabs)/entreprises',
  });

  const reportParsed = useMemo(() => {
    if (!report || typeof report !== 'object') return report;
    const r: any = report;
    const seoLatest = tryParseJson(r?.seo?.latest?.seo_details ?? r?.seo?.latest?.lighthouse_json ?? r?.seo?.latest?.issues_json ?? r?.seo?.latest);
    const pentestLatest = tryParseJson(r?.pentest?.latest?.pentest_details ?? r?.pentest?.latest);
    const technicalLatest = tryParseJson(r?.technical?.latest);
    const osintLatest = tryParseJson(r?.osint?.latest);
    return { ...r, seoLatest, pentestLatest, technicalLatest, osintLatest };
  }, [report]);

  const galleryWidth = Math.max(0, windowWidth - 32);
  const images = useMemo(() => findImageUris(report, 40), [report]);

  const analysisSubtitles = useMemo(() => {
    if (!reportParsed) return null;
    return {
      seo: seoSubtitle(reportParsed, entreprise),
      technical: technicalSubtitle(reportParsed, entreprise),
      pentest: pentestSubtitle(reportParsed, entreprise),
      osint: osintSubtitle(reportParsed, entreprise),
    };
  }, [reportParsed, entreprise]);

  const toggleAnalysis = useCallback((k: AnalysisKind) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setOpenAnalysis((cur) => (cur === k ? null : k));
  }, []);

  return (
    <Screen>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => load({ skipCache: true })} tintColor={t.colors.primary} />
        }
      >
        {!token && !tokenLoading && (
          <FadeIn>
            <Card>
              <H2>Token requis</H2>
              <MutedText style={{ marginTop: 6 }}>Va dans Reglages et colle ton token API.</MutedText>
            </Card>
          </FadeIn>
        )}

        {!!token && (
          <FadeIn>
            <Card style={{ borderLeftWidth: 3, borderLeftColor: t.colors.primary }}>
              {loadingEntreprise && !raw && (
                <MaterialAsyncLoader
                  visible
                  icon="database-sync-outline"
                  message="Chargement de la fiche entreprise…"
                />
              )}

              {!loadingEntreprise && !!error && <MutedText style={styles.error}>{error}</MutedText>}

              {!error && raw && (
                <>
                  <View
                    style={[
                      styles.subCard,
                      {
                        borderColor: t.colors.border,
                        backgroundColor: `${t.colors.primary}0C`,
                      },
                    ]}
                  >
                    <View style={styles.rowIcon}>
                      <View style={[styles.iconBadge, { backgroundColor: `${t.colors.primary}22` }]}>
                        <MaterialCommunityIcons name="office-building-outline" size={20} color={t.colors.primary} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <H2>Identité</H2>
                        <MutedText style={{ marginTop: 2 }}>Fiche synthétique</MutedText>
                      </View>
                    </View>

                    {(entreprise?.score_seo != null ||
                      entreprise?.performance_score != null ||
                      entreprise?.score_securite != null ||
                      entreprise?.score_pentest != null) && (
                      <View style={styles.chipRow}>
                        {entreprise?.score_seo != null && (
                          <View style={[styles.metricChip, { borderColor: t.colors.border }]}>
                            <MutedText style={styles.metricChipLabel}>SEO</MutedText>
                            <Text style={[styles.metricChipVal, { color: t.colors.text, fontFamily: 'monospace' }]}>
                              {entreprise.score_seo}
                            </Text>
                          </View>
                        )}
                        {entreprise?.performance_score != null && (
                          <View style={[styles.metricChip, { borderColor: t.colors.border }]}>
                            <MutedText style={styles.metricChipLabel}>Perf.</MutedText>
                            <Text style={[styles.metricChipVal, { color: t.colors.text, fontFamily: 'monospace' }]}>
                              {entreprise.performance_score}
                            </Text>
                          </View>
                        )}
                        {entreprise?.score_securite != null && (
                          <View style={[styles.metricChip, { borderColor: t.colors.border }]}>
                            <MutedText style={styles.metricChipLabel}>Sécu.</MutedText>
                            <Text style={[styles.metricChipVal, { color: t.colors.text, fontFamily: 'monospace' }]}>
                              {entreprise.score_securite}
                            </Text>
                          </View>
                        )}
                        {entreprise?.score_pentest != null && (
                          <View style={[styles.metricChip, { borderColor: t.colors.border }]}>
                            <MutedText style={styles.metricChipLabel}>Pentest</MutedText>
                            <Text style={[styles.metricChipVal, { color: t.colors.text, fontFamily: 'monospace' }]}>
                              {entreprise.score_pentest}
                            </Text>
                          </View>
                        )}
                      </View>
                    )}

                    {!!entreprise?.website && (
                      <View style={[styles.kvBlock, { borderColor: t.colors.border, backgroundColor: t.colors.card }]}>
                        <View style={styles.row}>
                          <FontAwesome6 name="globe" size={13} color={t.colors.primary} />
                          <Text
                            selectable
                            style={{ flex: 1, fontSize: 14, fontFamily: 'monospace', color: t.colors.muted }}
                          >
                            {entreprise.website}
                          </Text>
                        </View>
                      </View>
                    )}
                    {!!entreprise?.secteur && (
                      <View style={styles.kvLine}>
                        <MutedText style={styles.kvKey}>Secteur</MutedText>
                        <MutedText style={styles.kvVal}>{entreprise.secteur}</MutedText>
                      </View>
                    )}
                    {!!entreprise?.statut && (
                      <View style={styles.kvLine}>
                        <MutedText style={styles.kvKey}>Statut</MutedText>
                        <View style={[styles.statusPill, { backgroundColor: `${t.colors.primary}18`, borderColor: t.colors.border }]}>
                          <Text style={{ fontWeight: '700', color: t.colors.text, fontSize: 13 }}>{entreprise.statut}</Text>
                        </View>
                      </View>
                    )}
                    {!!entreprise?.opportunite && (
                      <View style={[styles.oppBanner, { borderColor: t.colors.border, backgroundColor: `${t.colors.warning}14` }]}>
                        <FontAwesome6 name="lightbulb" size={12} color={t.colors.warning} />
                        <MutedText style={{ flex: 1 }}>{entreprise.opportunite}</MutedText>
                      </View>
                    )}
                  </View>

                  <View
                    style={[
                      styles.subCard,
                      {
                        marginTop: 4,
                        borderColor: t.colors.border,
                        backgroundColor: `${t.colors.primary}08`,
                      },
                    ]}
                  >
                    {(!!entreprise?.email_principal || !!entreprise?.telephone) && (
                      <View style={{ gap: 10 }}>
                        {!!entreprise?.email_principal && (
                          <View style={[styles.contactCard, { borderColor: t.colors.border, backgroundColor: t.colors.card }]}>
                            <View style={styles.row}>
                              <FontAwesome6 name="envelope" size={14} color={t.colors.primary} />
                              <MutedText style={styles.contactLabel}>E-mail principal</MutedText>
                            </View>
                            <Text
                              selectable
                              style={[styles.contactValue, { color: t.colors.muted, fontFamily: 'monospace' }]}
                            >
                              {entreprise.email_principal}
                            </Text>
                          </View>
                        )}
                        {!!entreprise?.telephone && (
                          <View style={[styles.contactCard, { borderColor: t.colors.border, backgroundColor: t.colors.card }]}>
                            <View style={styles.row}>
                              <FontAwesome6 name="phone" size={14} color={t.colors.primary} />
                              <MutedText style={styles.contactLabel}>Téléphone principal</MutedText>
                            </View>
                            <Text
                              selectable
                              style={[styles.contactValue, { color: t.colors.muted, fontFamily: 'monospace' }]}
                            >
                              {entreprise.telephone}
                            </Text>
                          </View>
                        )}
                      </View>
                    )}

                    <MaterialAsyncLoader
                      visible={contactsLoading}
                      compact
                      icon="account-sync-outline"
                      message="Synchronisation des emails et téléphones…"
                    />

                    {!!emails?.length && (
                      <View style={{ marginTop: 12 }}>
                        <MutedText style={styles.listHeading}>E-mails connus ({emails.length})</MutedText>
                        <View style={{ marginTop: 8, gap: 8 }}>
                          {emails.slice(0, 6).map((it, i) => (
                            <View
                              key={i}
                              style={[styles.listItem, { borderColor: t.colors.border, backgroundColor: t.colors.card }]}
                            >
                              <Text
                                selectable
                                style={{ fontFamily: 'monospace', fontSize: 13, color: t.colors.muted }}
                              >
                                {String((it as any)?.email ?? it)}
                              </Text>
                            </View>
                          ))}
                          {emails.length > 6 && <MutedText>+ {emails.length - 6} autres…</MutedText>}
                        </View>
                      </View>
                    )}

                    {!!phonesList.length && (
                      <View style={{ marginTop: 12 }}>
                        <MutedText style={styles.listHeading}>Téléphones connus ({phonesList.length})</MutedText>
                        <View style={{ marginTop: 8, gap: 8 }}>
                          {phonesList.slice(0, 6).map((it, i) => (
                            <View
                              key={i}
                              style={[styles.listItem, { borderColor: t.colors.border, backgroundColor: t.colors.card }]}
                            >
                              <Text
                                selectable
                                style={{ fontFamily: 'monospace', fontSize: 13, color: t.colors.muted }}
                              >
                                {String((it as any)?.phone ?? (it as any)?.phone_e164 ?? it)}
                                {(it as any)?.source ? ` · ${String((it as any).source)}` : ''}
                              </Text>
                            </View>
                          ))}
                          {phonesList.length > 6 && <MutedText>+ {phonesList.length - 6} autres…</MutedText>}
                        </View>
                      </View>
                    )}
                  </View>

                  {!!images.length && !!reportParsed && (
                    <View style={[styles.section, { borderTopColor: t.colors.border }]}>
                      <View style={styles.rowIcon}>
                        <MaterialCommunityIcons name="image-multiple-outline" size={18} color={t.colors.primary} />
                        <H2>Captures</H2>
                      </View>
                      <MutedText style={{ marginBottom: 10 }}>Appuie sur une image pour l’agrandir et zoomer.</MutedText>
                      <ReportImageGallery uris={images} containerWidth={galleryWidth} />
                    </View>
                  )}

                  <View style={[styles.section, { borderTopColor: t.colors.border }]}>
                    <View style={styles.rowIcon}>
                      <MaterialCommunityIcons name="chart-box-outline" size={18} color={t.colors.primary} />
                      <H2>Analyses</H2>
                    </View>

                    {!!entreprise?.website && reportLoading && !report && (
                      <MaterialAsyncLoader
                        visible
                        icon="chart-box-outline"
                        message="Chargement du rapport d’analyse (SEO, technique, pentest, OSINT)…"
                      />
                    )}

                    {!!entreprise?.website && !reportLoading && !report && (
                      <MutedText>
                        Aucune analyse complète disponible pour ce site. Tu peux en lancer une depuis l’onglet Scan.
                      </MutedText>
                    )}

                    {!entreprise?.website && (
                      <MutedText>Pas de site web renseigné — analyses indisponibles.</MutedText>
                    )}

                    {!!reportParsed && (
                      <View style={{ marginTop: 12, gap: 10 }}>
                        <WebsiteAnalysisSection
                          kind="seo"
                          title="SEO"
                          icon="chart-line"
                          expanded={openAnalysis === 'seo'}
                          onToggle={() => toggleAnalysis('seo')}
                          subtitle={analysisSubtitles?.seo}
                          envelope={reportParsed?.seo}
                          parsed={reportParsed?.seoLatest}
                        />
                        <WebsiteAnalysisSection
                          kind="technical"
                          title="Technique"
                          icon="tools"
                          expanded={openAnalysis === 'technical'}
                          onToggle={() => toggleAnalysis('technical')}
                          subtitle={analysisSubtitles?.technical}
                          envelope={reportParsed?.technical}
                          parsed={reportParsed?.technicalLatest}
                        />
                        <WebsiteAnalysisSection
                          kind="pentest"
                          title="Pentest"
                          icon="shield-halved"
                          expanded={openAnalysis === 'pentest'}
                          onToggle={() => toggleAnalysis('pentest')}
                          subtitle={analysisSubtitles?.pentest}
                          envelope={reportParsed?.pentest}
                          parsed={reportParsed?.pentestLatest}
                        />
                        <WebsiteAnalysisSection
                          kind="osint"
                          title="OSINT"
                          icon="magnifying-glass"
                          expanded={openAnalysis === 'osint'}
                          onToggle={() => toggleAnalysis('osint')}
                          subtitle={analysisSubtitles?.osint}
                          envelope={reportParsed?.osint}
                          parsed={reportParsed?.osintLatest}
                        />
                      </View>
                    )}
                  </View>

                  {!!entreprise?.id && (campagnesLoading || Array.isArray(campagnes)) && (
                    <View style={[styles.section, { borderTopColor: t.colors.border }]}>
                      <View style={styles.rowIcon}>
                        <MaterialCommunityIcons name="email-multiple-outline" size={18} color={t.colors.primary} />
                        <H2>Campagnes</H2>
                      </View>
                      {campagnesLoading ? (
                        <MaterialAsyncLoader compact icon="email-sync-outline" message="Chargement des campagnes…" visible />
                      ) : (
                        <MutedText>Campagnes liees: {campagnes?.length ?? 0}</MutedText>
                      )}
                    </View>
                  )}

                  <View style={[styles.section, { borderTopColor: t.colors.border }]}>
                    <View style={styles.rowIcon}>
                      <MaterialCommunityIcons name="code-json" size={18} color={t.colors.primary} />
                      <H2>Tout (raw)</H2>
                    </View>
                    <Pressable onPress={() => setRawExpanded((v) => !v)} style={{ marginTop: 6 }}>
                      <MutedText style={{ color: t.colors.primary }}>
                        {rawExpanded ? 'Masquer' : 'Afficher'} les données brutes
                      </MutedText>
                    </Pressable>
                    {rawExpanded && (
                      <View style={{ marginTop: 10 }}>
                        <Mono>{JSON.stringify({ entreprise: entreprise?.raw, lookup: raw, report }, null, 2)}</Mono>
                      </View>
                    )}
                  </View>
                </>
              )}
            </Card>
          </FadeIn>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  error: { marginTop: 6 },
  section: { marginTop: 6, paddingTop: 12, borderTopWidth: 1 },
  rowIcon: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 },
  subCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
  },
  iconBadge: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  metricChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
  },
  metricChipLabel: { fontSize: 11, marginBottom: 0 },
  metricChipVal: { fontSize: 13, fontWeight: '700' },
  kvBlock: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    marginTop: 4,
  },
  kvLine: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 10,
    gap: 12,
  },
  kvKey: { fontSize: 12, opacity: 0.85 },
  kvVal: { fontSize: 13, fontWeight: '600', flex: 1, textAlign: 'right' },
  statusPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
  },
  oppBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginTop: 12,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  contactCard: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 12,
    marginTop: 4,
  },
  contactLabel: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.4, opacity: 0.8 },
  contactValue: { marginTop: 8, fontSize: 15 },
  listHeading: { fontSize: 12, fontWeight: '700' },
  listItem: {
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
});

