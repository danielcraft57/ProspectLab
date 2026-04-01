import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Image, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import { ProspectLabApi } from '../../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../../src/features/prospectlab/useToken';
import { Card, FadeIn, H2, Mono, Muted, MutedText, Screen } from '../../../src/ui/components';
import { useTheme } from '../../../src/ui/theme';
import { useDetailScreenHeader } from '../../../src/ui/useDetailScreenHeader';

type DetailKind = 'website' | 'email' | 'phone' | 'id';

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

function isImageUri(s: string) {
  const v = s.toLowerCase();
  return (
    v.startsWith('data:image/') ||
    v.endsWith('.png') ||
    v.endsWith('.jpg') ||
    v.endsWith('.jpeg') ||
    v.endsWith('.webp') ||
    v.endsWith('.gif')
  );
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

function normalizeEntreprise(raw: any) {
  const ent = raw?.entreprise ?? raw;
  return {
    id: typeof ent?.id === 'number' ? ent.id : undefined,
    nom: typeof ent?.nom === 'string' ? ent.nom : typeof ent?.name === 'string' ? ent.name : undefined,
    website: typeof ent?.website === 'string' ? ent.website : typeof ent?.url === 'string' ? ent.url : undefined,
    secteur: typeof ent?.secteur === 'string' ? ent.secteur : undefined,
    statut: typeof ent?.statut === 'string' ? ent.statut : undefined,
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

export default function EntrepriseDetailsScreen() {
  const t = useTheme();
  const { token, loading: tokenLoading } = useApiToken();
  const params = useLocalSearchParams<{ kind?: string; value?: string }>();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [emails, setEmails] = useState<any[] | null>(null);
  const [phones, setPhones] = useState<any[] | null>(null);
  const [phonesApi, setPhonesApi] = useState<any[] | null>(null);
  const [campagnes, setCampagnes] = useState<any[] | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ seo: true, technical: false, pentest: false, osint: false, raw: false });

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

      setLoading(true);
      setError(null);
      const c = { skipCache: opts?.skipCache };
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

        const tasks: Array<Promise<void>> = [];

        if (website) {
          tasks.push(
            ProspectLabApi.getWebsiteAnalysis(token, website, true, c)
              .then((r) => setReport(r?.data ?? r))
              .catch(() => setReport(null)),
          );
        } else {
          setReport(null);
        }

        if (entrepriseId) {
          tasks.push(
            ProspectLabApi.listEntrepriseEmailsAll(token, entrepriseId, true, c)
              .then((r) => setEmails((r?.data ?? r) as any[]))
              .catch(() => {}),
          );
          tasks.push(
            ProspectLabApi.listEntreprisePhones(token, entrepriseId, true, c)
              .then((r) => setPhonesApi((r?.data ?? r) as any[]))
              .catch(() => setPhonesApi(null)),
          );
          tasks.push(
            ProspectLabApi.listCampagnesByEntreprise(token, entrepriseId, { limit: 50, offset: 0 }, c)
              .then((r) => setCampagnes((r?.data ?? r) as any[]))
              .catch(() => setCampagnes(null)),
          );
        } else {
          setCampagnes(null);
          setPhonesApi(null);
        }

        await Promise.all(tasks);
      } catch (e: any) {
        setError(e?.message ?? 'Erreur lors du chargement des details.');
      } finally {
        setLoading(false);
      }
    },
    [token, kind, value],
  );

  useEffect(() => {
    load();
  }, [load]);

  const entreprise = useMemo(() => (raw ? normalizeEntreprise(raw) : null), [raw]);
  const phonesList = useMemo(() => phonesApi ?? phones ?? [], [phonesApi, phones]);
  const displayTitle = entreprise?.nom ?? entreprise?.website ?? '';
  useDetailScreenHeader({
    title: displayTitle,
    fallbackTitle: 'Entreprise',
    listPath: '/(tabs)/entreprises',
  });
  const images = useMemo(() => findImageUris(report, 6), [report]);

  const reportParsed = useMemo(() => {
    if (!report || typeof report !== 'object') return report;
    const r: any = report;
    const seoLatest = tryParseJson(r?.seo?.latest?.seo_details ?? r?.seo?.latest?.lighthouse_json ?? r?.seo?.latest?.issues_json ?? r?.seo?.latest);
    const pentestLatest = tryParseJson(r?.pentest?.latest?.pentest_details ?? r?.pentest?.latest);
    const technicalLatest = tryParseJson(r?.technical?.latest);
    const osintLatest = tryParseJson(r?.osint?.latest);
    return { ...r, seoLatest, pentestLatest, technicalLatest, osintLatest };
  }, [report]);

  return (
    <Screen>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={() => load({ skipCache: true })} tintColor={t.colors.primary} />
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
              {loading && (
                <View style={styles.loading}>
                  <ActivityIndicator size="large" color={t.colors.primary} />
                  <MutedText style={{ marginTop: 10 }}>Chargement...</MutedText>
                </View>
              )}

              {!loading && !!error && <MutedText style={styles.error}>{error}</MutedText>}

              {!loading && !error && (
                <>
                  <View style={[styles.section, { borderTopColor: t.colors.border }]}>
                    <View style={styles.rowIcon}>
                      <MaterialCommunityIcons name="office-building-outline" size={18} color={t.colors.primary} />
                      <H2>Identite</H2>
                    </View>

                    {!!entreprise?.website && (
                      <View style={styles.row}>
                        <FontAwesome6 name="globe" size={12} color={t.colors.primary} />
                        <Mono>{entreprise.website}</Mono>
                      </View>
                    )}
                    {!!entreprise?.secteur && (
                      <View style={styles.row}>
                        <FontAwesome6 name="briefcase" size={12} color={t.colors.primary} />
                        <Muted>Secteur: {entreprise.secteur}</Muted>
                      </View>
                    )}
                    {!!entreprise?.statut && (
                      <View style={styles.row}>
                        <FontAwesome6 name="gavel" size={12} color={t.colors.primary} />
                        <Muted>Statut: {entreprise.statut}</Muted>
                      </View>
                    )}
                  </View>

                  <View style={[styles.section, { borderTopColor: t.colors.border }]}>
                    <View style={styles.rowIcon}>
                      <FontAwesome6 name="users" size={14} color={t.colors.primary} />
                      <H2>Contacts</H2>
                    </View>

                    {!!entreprise?.email_principal && (
                      <View style={styles.row}>
                        <FontAwesome6 name="envelope" size={12} color={t.colors.primary} />
                        <Muted>Email: {entreprise.email_principal}</Muted>
                      </View>
                    )}
                    {!!entreprise?.telephone && (
                      <View style={styles.row}>
                        <FontAwesome6 name="phone" size={12} color={t.colors.primary} />
                        <Muted>Tel: {entreprise.telephone}</Muted>
                      </View>
                    )}

                    {!!emails?.length && (
                      <View style={{ marginTop: 10 }}>
                        <MutedText>Emails connus: {emails.length}</MutedText>
                        <View style={{ marginTop: 6, gap: 6 }}>
                          {emails.slice(0, 6).map((it, i) => (
                            <Mono key={i}>{String((it as any)?.email ?? it)}</Mono>
                          ))}
                          {emails.length > 6 && <MutedText>+ {emails.length - 6} autres...</MutedText>}
                        </View>
                      </View>
                    )}

                    {!!phonesList.length && (
                      <View style={{ marginTop: 10 }}>
                        <MutedText>Telephones connus: {phonesList.length}</MutedText>
                        <View style={{ marginTop: 6, gap: 6 }}>
                          {phonesList.slice(0, 6).map((it, i) => (
                            <Mono key={i}>
                              {String((it as any)?.phone ?? (it as any)?.phone_e164 ?? it)}
                              {(it as any)?.source ? ` (${String((it as any).source)})` : ''}
                            </Mono>
                          ))}
                          {phonesList.length > 6 && <MutedText>+ {phonesList.length - 6} autres...</MutedText>}
                        </View>
                      </View>
                    )}
                  </View>

                  <View style={[styles.section, { borderTopColor: t.colors.border }]}>
                    <View style={styles.rowIcon}>
                      <MaterialCommunityIcons name="chart-box-outline" size={18} color={t.colors.primary} />
                      <H2>Analyses</H2>
                    </View>

                    {!reportParsed && (
                      <MutedText>
                        Aucune analyse complete disponible pour ce website. Tu peux la lancer depuis l'onglet Scan.
                      </MutedText>
                    )}

                    {!!reportParsed && (
                      <>
                        {!!images.length && (
                          <View style={{ marginTop: 10, gap: 10 }}>
                            <MutedText>Images / screenshots</MutedText>
                            {images.map((uri, idx) => (
                              <Image
                                key={idx}
                                source={{ uri }}
                                style={{ width: '100%', height: 180, borderRadius: 14, borderWidth: 1, borderColor: t.colors.border }}
                                resizeMode="cover"
                              />
                            ))}
                          </View>
                        )}

                        <View style={{ marginTop: 12, gap: 10 }}>
                          <AnalysisSection
                            title="SEO"
                            icon="chart-line"
                            expanded={!!expanded.seo}
                            onToggle={() => setExpanded((s) => ({ ...s, seo: !s.seo }))}
                            summary={reportParsed?.seo?.status}
                            payload={reportParsed?.seoLatest ?? reportParsed?.seo}
                          />
                          <AnalysisSection
                            title="Technique"
                            icon="tools"
                            expanded={!!expanded.technical}
                            onToggle={() => setExpanded((s) => ({ ...s, technical: !s.technical }))}
                            summary={reportParsed?.technical?.status}
                            payload={reportParsed?.technicalLatest ?? reportParsed?.technical}
                          />
                          <AnalysisSection
                            title="Pentest"
                            icon="shield-halved"
                            expanded={!!expanded.pentest}
                            onToggle={() => setExpanded((s) => ({ ...s, pentest: !s.pentest }))}
                            summary={reportParsed?.pentest?.status}
                            payload={reportParsed?.pentestLatest ?? reportParsed?.pentest}
                          />
                          <AnalysisSection
                            title="OSINT"
                            icon="magnifying-glass"
                            expanded={!!expanded.osint}
                            onToggle={() => setExpanded((s) => ({ ...s, osint: !s.osint }))}
                            summary={reportParsed?.osint?.status}
                            payload={reportParsed?.osintLatest ?? reportParsed?.osint}
                          />
                        </View>
                      </>
                    )}
                  </View>

                  {!!campagnes?.length && (
                    <View style={[styles.section, { borderTopColor: t.colors.border }]}>
                      <View style={styles.rowIcon}>
                        <MaterialCommunityIcons name="email-multiple-outline" size={18} color={t.colors.primary} />
                        <H2>Campagnes</H2>
                      </View>
                      <MutedText>Campagnes liees: {campagnes.length}</MutedText>
                    </View>
                  )}

                  <View style={[styles.section, { borderTopColor: t.colors.border }]}>
                    <View style={styles.rowIcon}>
                      <MaterialCommunityIcons name="code-json" size={18} color={t.colors.primary} />
                      <H2>Tout (raw)</H2>
                    </View>
                    <Pressable onPress={() => setExpanded((s) => ({ ...s, raw: !s.raw }))} style={{ marginTop: 6 }}>
                      <MutedText style={{ color: t.colors.primary }}>{expanded.raw ? 'Masquer' : 'Afficher'} les donnees brutes</MutedText>
                    </Pressable>
                    {expanded.raw && (
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

function AnalysisSection({
  title,
  icon,
  expanded,
  onToggle,
  summary,
  payload,
}: {
  title: string;
  icon: any;
  expanded: boolean;
  onToggle: () => void;
  summary?: string;
  payload: any;
}) {
  const t = useTheme();
  return (
    <View style={{ borderWidth: 1, borderColor: t.colors.border, borderRadius: 14, overflow: 'hidden' }}>
      <Pressable onPress={onToggle} style={{ padding: 12, flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <FontAwesome6 name={icon} size={14} color={t.colors.primary} />
        <View style={{ flex: 1 }}>
          <MutedText style={{ color: t.colors.text, fontWeight: '800' } as any}>{title}</MutedText>
          <MutedText style={{ marginTop: 2 }}>{summary ? `Statut: ${summary}` : 'Statut: ?'}</MutedText>
        </View>
        <FontAwesome6 name={expanded ? 'chevron-up' : 'chevron-down'} size={12} color={t.colors.muted} />
      </Pressable>
      {expanded && (
        <View style={{ padding: 12, paddingTop: 0 }}>
          <Mono>{payload ? JSON.stringify(payload, null, 2) : 'Aucune donnee'}</Mono>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  loading: { alignItems: 'center', paddingVertical: 20 },
  error: { marginTop: 6 },
  section: { marginTop: 6, paddingTop: 12, borderTopWidth: 1 },
  rowIcon: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 },
});

