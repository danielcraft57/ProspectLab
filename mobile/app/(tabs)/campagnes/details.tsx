import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Animated,
  Easing,
  LayoutAnimation,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  UIManager,
  View,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import { ProspectLabApi } from '../../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../../src/features/prospectlab/useToken';
import {
  campagneDetailCacheIsStale,
  readCampagneDetailCache,
  writeCampagneDetailCache,
} from '../../../src/lib/cache/repositories';
import { emitNetworkRefreshIntent } from '../../../src/features/network/networkToastBus';
import { useAppNetwork } from '../../../src/lib/net/useAppNetwork';
import { DonutChart, SegmentedBar, Sparkline } from '../../../src/ui/charts';
import { Card, FadeIn, H2, Mono, Muted, MutedText, PrimaryButton, Screen } from '../../../src/ui/components';
import type { AppTheme } from '../../../src/ui/theme';
import { useTheme } from '../../../src/ui/theme';
import { useDetailScreenHeader } from '../../../src/ui/useDetailScreenHeader';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

function safeNum(v: unknown): number {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim() !== '' && !Number.isNaN(Number(v))) return Number(v);
  return 0;
}

function fmtPct(v: number, digits = 1) {
  if (!Number.isFinite(v)) return '—';
  return `${v.toFixed(digits)} %`;
}

function statutCampagneStyle(statut: string | undefined, t: AppTheme) {
  const s = (statut || '').toLowerCase();
  if (s === 'completed') return { bg: t.colors.success + '33', fg: t.colors.success, label: 'Terminée' };
  if (s === 'running') return { bg: t.colors.primary + '33', fg: t.colors.primary, label: 'En cours' };
  if (s === 'scheduled') return { bg: t.colors.warning + '40', fg: t.colors.warning, label: 'Programmée' };
  if (s === 'failed') return { bg: t.colors.danger + '33', fg: t.colors.danger, label: 'Échec' };
  if (s === 'draft') return { bg: t.colors.border, fg: t.colors.muted, label: 'Brouillon' };
  return { bg: t.colors.border, fg: t.colors.text, label: statut || '—' };
}

function buildDailySendCounts(
  emails: Array<Record<string, unknown>>,
  days = 14,
): number[] {
  const keys: string[] = [];
  const now = new Date();
  for (let i = 0; i < days; i++) {
    const d = new Date(now);
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - (days - 1 - i));
    keys.push(d.toISOString().slice(0, 10));
  }
  const counts = new Map<string, number>();
  for (const k of keys) counts.set(k, 0);
  for (const e of emails) {
    const raw = e.date_envoi;
    if (typeof raw !== 'string' || raw.length < 10) continue;
    const key = raw.slice(0, 10);
    if (counts.has(key)) counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return keys.map((k) => counts.get(k) ?? 0);
}

function aggregateEmailStatuts(emails: Array<Record<string, unknown>>) {
  const m: Record<string, number> = {};
  for (const e of emails) {
    const st = String(e.statut || 'autre').toLowerCase();
    m[st] = (m[st] || 0) + 1;
  }
  return m;
}

function ScaleIn({ children, delayMs = 0 }: { children: ReactNode; delayMs?: number }) {
  const a = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const t = setTimeout(() => {
      Animated.spring(a, {
        toValue: 1,
        friction: 7,
        tension: 76,
        useNativeDriver: true,
      }).start();
    }, delayMs);
    return () => clearTimeout(t);
  }, [a, delayMs]);
  const style = {
    opacity: a,
    transform: [
      {
        scale: a.interpolate({
          inputRange: [0, 1],
          outputRange: [0.9, 1],
        }),
      },
    ],
  };
  return <Animated.View style={style}>{children}</Animated.View>;
}

function Kpi({
  label,
  value,
  hint,
  t,
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  t: AppTheme;
  icon: ReactNode;
}) {
  return (
    <View
      style={[
        styles.kpi,
        {
          backgroundColor: t.colors.card,
          borderColor: t.colors.border,
        },
      ]}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        {icon}
        <Text style={[styles.kpiLabel, { color: t.colors.muted }]} numberOfLines={2}>
          {label}
        </Text>
      </View>
      <Text style={[styles.kpiValue, { color: t.colors.text }]}>{value}</Text>
      {hint ? <MutedText style={{ marginTop: 4, fontSize: 11 }}>{hint}</MutedText> : null}
    </View>
  );
}

export default function CampagneDetailsScreen() {
  const t = useTheme();
  const { token, loading: tokenLoading } = useApiToken();
  const { usableForApi } = useAppNetwork();
  const params = useLocalSearchParams<{ id?: string }>();

  const campagneId = useMemo(() => {
    const raw = Array.isArray(params.id) ? params.id[0] : params.id;
    const n = parseInt(String(raw || ''), 10);
    return Number.isFinite(n) ? n : null;
  }, [params.id]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [campagne, setCampagne] = useState<Record<string, unknown> | null>(null);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [rawOpen, setRawOpen] = useState(false);
  const rawProgress = useRef(new Animated.Value(0)).current;

  const load = useCallback(
    async (opts?: { skipCache?: boolean }) => {
      if (!token || campagneId == null) return;
      const force = !!opts?.skipCache;
      let sqlRow: Awaited<ReturnType<typeof readCampagneDetailCache>> = null;
      if (!force) {
        sqlRow = await readCampagneDetailCache(campagneId);
        if (sqlRow) {
          setCampagne(sqlRow.campagne);
          setStats(sqlRow.stats);
        }
      }

      if (!usableForApi) {
        setLoading(false);
        if (!sqlRow) {
          setError('Hors ligne — pas de campagne en cache.');
          setCampagne(null);
          setStats(null);
        } else setError(null);
        return;
      }

      const blocking = force || !sqlRow || campagneDetailCacheIsStale(sqlRow.updatedAt);
      if (!blocking) {
        setError(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      const c = { skipCache: true };
      try {
        const settled = await Promise.allSettled([
          ProspectLabApi.getCampagne(token, campagneId, c),
          ProspectLabApi.getCampagneStatistics(token, campagneId, c),
        ]);
        const cg = settled[0].status === 'fulfilled' ? settled[0].value : null;
        const st = settled[1].status === 'fulfilled' ? settled[1].value : null;

        if (settled[0].status === 'rejected') {
          const reason = settled[0].reason as Error | undefined;
          if (!sqlRow) {
            setError(reason?.message ?? 'Campagne introuvable');
            setCampagne(null);
            setStats(null);
          }
          return;
        }

        const cgBody = cg as { success?: boolean; data?: Record<string, unknown>; error?: string } | null;
        if (cgBody && cgBody.success === false && !cgBody.data) {
          if (!sqlRow) {
            setError(cgBody.error ?? 'Campagne introuvable');
            setCampagne(null);
            setStats(null);
          }
          return;
        }
        const cgData = (cgBody?.data ?? null) as Record<string, unknown> | null;
        setCampagne(cgData);

        let statsData: Record<string, unknown> | null = null;
        if (settled[1].status === 'rejected') {
          setStats(null);
        } else {
          const stBody = st as { data?: Record<string, unknown> } | null;
          statsData = (stBody?.data ?? null) as Record<string, unknown> | null;
          setStats(statsData);
        }
        await writeCampagneDetailCache(campagneId, cgData, statsData);
      } catch (e: any) {
        if (!sqlRow) {
          setError(e?.message ?? 'Erreur chargement');
          setCampagne(null);
          setStats(null);
        }
      } finally {
        setLoading(false);
      }
    },
    [token, campagneId, usableForApi],
  );

  useEffect(() => {
    if (token && campagneId != null) load();
  }, [token, campagneId, load]);

  useEffect(() => {
    Animated.timing(rawProgress, {
      toValue: rawOpen ? 1 : 0,
      duration: 260,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();
  }, [rawOpen, rawProgress]);

  const nom = typeof campagne?.nom === 'string' ? campagne.nom : `Campagne #${campagneId ?? ''}`;
  useDetailScreenHeader({
    title: typeof campagne?.nom === 'string' ? campagne.nom : '',
    fallbackTitle: campagneId != null ? `Campagne #${campagneId}` : 'Campagne',
    listPath: '/(tabs)/campagnes',
  });
  const statut = typeof campagne?.statut === 'string' ? campagne.statut : undefined;
  const statStyle = statutCampagneStyle(statut, t);
  const sujet = typeof campagne?.sujet === 'string' ? campagne.sujet : null;

  const emails = useMemo(() => {
    const arr = stats?.emails;
    return Array.isArray(arr) ? (arr as Array<Record<string, unknown>>) : [];
  }, [stats]);

  const totalEmails = safeNum(stats?.total_emails);
  const totalOpens = safeNum(stats?.total_opens);
  const totalClicks = safeNum(stats?.total_clicks);
  const openRate = safeNum(stats?.open_rate);
  const clickRate = safeNum(stats?.click_rate);
  const totalBounced = safeNum(stats?.total_bounced);
  const deliv = safeNum(stats?.deliverability_rate_strict);
  const avgRead = stats?.avg_read_time;
  const totalDest = safeNum(stats?.total_destinataires);
  const totalReussis = safeNum(stats?.total_reussis);
  const totalDeliveredStrict = safeNum(stats?.total_delivered_strict);

  const dailyCounts = useMemo(() => buildDailySendCounts(emails), [emails]);
  const statutAgg = useMemo(() => aggregateEmailStatuts(emails), [emails]);
  const segParts = useMemo(() => {
    const palette = [t.colors.success, t.colors.warning, t.colors.danger, t.colors.primary, t.colors.muted];
    const entries = Object.entries(statutAgg).filter(([, v]) => v > 0);
    return entries.map(([k, v], i) => ({
      value: v,
      color: palette[i % palette.length],
      labelKey: k,
    }));
  }, [statutAgg, t]);

  const statsByType = stats?.stats_by_type as Record<string, { unique_emails?: number; total_events?: number }> | undefined;

  const rawMaxH = rawProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 640],
  });

  return (
    <Screen>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={() => {
              emitNetworkRefreshIntent();
              void load({ skipCache: true });
            }}
            tintColor={t.colors.primary}
          />
        }
      >
        {!tokenLoading && !token && (
          <FadeIn>
            <Card>
              <Muted>Token manquant.</Muted>
            </Card>
          </FadeIn>
        )}

        {campagneId == null && !!token && (
          <Card>
            <Muted>Identifiant campagne manquant.</Muted>
          </Card>
        )}

        {!!token && campagneId != null && loading && !campagne && !error && (
          <View style={{ paddingVertical: 32, alignItems: 'center' }}>
            <ActivityIndicator size="large" color={t.colors.primary} />
            <MutedText style={{ marginTop: 12 }}>Chargement de la campagne…</MutedText>
          </View>
        )}

        {!!error && (
          <FadeIn>
            <Card>
              <Mono>{error}</Mono>
              <View style={{ marginTop: 12 }}>
                <PrimaryButton
                  title="Réessayer"
                  onPress={() => {
                    emitNetworkRefreshIntent();
                    void load({ skipCache: true });
                  }}
                  disabled={loading}
                />
              </View>
            </Card>
          </FadeIn>
        )}

        {!!token && campagneId != null && !error && (
          <>
            <FadeIn delayMs={0}>
              <View
                style={[
                  styles.hero,
                  {
                    borderColor: statStyle.fg + '66',
                    backgroundColor: t.colors.card,
                  },
                ]}
              >
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
                  <View style={[styles.statutPill, { backgroundColor: statStyle.bg }]}>
                    <Text style={{ color: statStyle.fg, fontWeight: '800', fontSize: 12 }}>{statStyle.label}</Text>
                  </View>
                  <Mono>#{campagneId}</Mono>
                </View>
                <View style={{ marginTop: 12 }}>
                  <H2>{nom}</H2>
                </View>
                {!!sujet && (
                  <MutedText style={{ marginTop: 8, lineHeight: 20 }}>
                    <Text style={{ fontWeight: '700', color: t.colors.text }}>Objet : </Text>
                    {sujet}
                  </MutedText>
                )}
                {!!campagne?.date_creation && (
                  <View style={[styles.inlineIcon, { marginTop: 10 }]}>
                    <FontAwesome6 name="calendar" size={12} color={t.colors.primary} />
                    <MutedText>Créée : {String(campagne.date_creation)}</MutedText>
                  </View>
                )}
                {!!campagne?.date_programmation && (
                  <View style={[styles.inlineIcon, { marginTop: 6 }]}>
                    <MaterialCommunityIcons name="clock-outline" size={14} color={t.colors.warning} />
                    <MutedText>Programmée : {String(campagne.date_programmation)}</MutedText>
                  </View>
                )}
              </View>
            </FadeIn>

            <FadeIn delayMs={70}>
              <Text style={[styles.sectionTitle, { color: t.colors.muted }]}>Indicateurs</Text>
              <View style={styles.kpiGrid}>
                <Kpi
                  label="Destinataires"
                  value={String(totalDest || safeNum(campagne?.total_destinataires))}
                  t={t}
                  icon={<MaterialCommunityIcons name="account-multiple-outline" size={18} color={t.colors.primary} />}
                />
                <Kpi
                  label="Envoyés (suivi)"
                  value={String(totalEmails)}
                  hint={totalReussis ? `${totalReussis} réussis (camp.)` : undefined}
                  t={t}
                  icon={<FontAwesome6 name="paper-plane" size={14} color={t.colors.primary} />}
                />
                <Kpi
                  label="Taux d’ouverture"
                  value={fmtPct(openRate)}
                  hint={`${totalOpens} contact(s)`}
                  t={t}
                  icon={<MaterialCommunityIcons name="email-open-outline" size={18} color={t.colors.success} />}
                />
                <Kpi
                  label="Taux de clic"
                  value={fmtPct(clickRate)}
                  hint={`${totalClicks} contact(s)`}
                  t={t}
                  icon={<MaterialCommunityIcons name="cursor-default-click-outline" size={18} color={t.colors.warning} />}
                />
                <Kpi
                  label="Bounces"
                  value={String(totalBounced)}
                  t={t}
                  icon={<MaterialCommunityIcons name="email-remove-outline" size={18} color={t.colors.danger} />}
                />
                <Kpi
                  label="Délivrabilité"
                  value={fmtPct(deliv)}
                  hint={
                    totalDeliveredStrict
                      ? `${totalDeliveredStrict} délivrés (hors bounce)`
                      : undefined
                  }
                  t={t}
                  icon={<MaterialCommunityIcons name="shield-check-outline" size={18} color={t.colors.success} />}
                />
              </View>
              {avgRead != null && avgRead !== '' && (
                <MutedText style={{ marginTop: 8 }}>
                  Temps de lecture moyen (tracking) :{' '}
                  {typeof avgRead === 'number' ? `${avgRead.toFixed(1)} s` : String(avgRead)}
                </MutedText>
              )}
            </FadeIn>

            {!!statsByType && Object.keys(statsByType).length > 0 && (
              <FadeIn delayMs={120}>
                <Card style={{ borderWidth: 1, borderColor: t.colors.border }}>
                  <H2>Événements de tracking</H2>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 10 }}>
                    {Object.entries(statsByType).map(([k, v]) => (
                      <View
                        key={k}
                        style={{
                          paddingHorizontal: 12,
                          paddingVertical: 8,
                          borderRadius: t.radii.pill,
                          backgroundColor: t.isDark ? 'rgba(79,140,255,0.12)' : 'rgba(46,107,255,0.08)',
                          borderWidth: 1,
                          borderColor: t.colors.border,
                        }}
                      >
                        <Text style={{ color: t.colors.text, fontWeight: '800', textTransform: 'capitalize' }}>{k}</Text>
                        <MutedText style={{ fontSize: 11 }}>
                          {safeNum(v?.unique_emails)} contact · {safeNum(v?.total_events)} évts
                        </MutedText>
                      </View>
                    ))}
                  </View>
                </Card>
              </FadeIn>
            )}

            <FadeIn delayMs={160}>
              <Card style={{ borderWidth: 1, borderColor: t.colors.border }}>
                <H2>Graphiques</H2>
                <MutedText style={{ marginTop: 6, marginBottom: 12 }}>
                  Engagement et répartition des statuts d’envoi (emails suivis).
                </MutedText>

                <View style={styles.chartRow}>
                  <ScaleIn delayMs={40}>
                    <View style={styles.chartBlock}>
                      <MutedText style={{ marginBottom: 8, fontWeight: '700' }}>Ouvertures</MutedText>
                      {totalEmails > 0 ? (
                        <>
                          <DonutChart
                            size={132}
                            thickness={16}
                            slices={[
                              { value: totalOpens, color: t.colors.success },
                              { value: Math.max(0, totalEmails - totalOpens), color: t.colors.border },
                            ]}
                          />
                          <MutedText style={{ marginTop: 8, textAlign: 'center' }}>
                            {totalOpens} ouvert · {Math.max(0, totalEmails - totalOpens)} sans ouverture
                          </MutedText>
                        </>
                      ) : (
                        <Muted>Pas encore d’envois suivis.</Muted>
                      )}
                    </View>
                  </ScaleIn>
                  <ScaleIn delayMs={120}>
                    <View style={styles.chartBlock}>
                      <MutedText style={{ marginBottom: 8, fontWeight: '700' }}>Clics (parmi suivis)</MutedText>
                      {totalEmails > 0 ? (
                        <>
                          <DonutChart
                            size={132}
                            thickness={16}
                            slices={[
                              { value: totalClicks, color: t.colors.warning },
                              { value: Math.max(0, totalEmails - totalClicks), color: t.colors.border },
                            ]}
                          />
                          <MutedText style={{ marginTop: 8, textAlign: 'center' }}>
                            {totalClicks} clic · {Math.max(0, totalEmails - totalClicks)} sans clic
                          </MutedText>
                        </>
                      ) : (
                        <Muted>Pas encore d’envois suivis.</Muted>
                      )}
                    </View>
                  </ScaleIn>
                </View>

                {emails.length > 0 && segParts.length > 0 && (
                  <>
                    <MutedText style={{ marginTop: 16, fontWeight: '700' }}>Répartition des statuts d’envoi</MutedText>
                    <SegmentedBar
                      width={Math.min(340, 900)}
                      height={12}
                      parts={segParts.map(({ labelKey, ...p }) => p)}
                    />
                    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
                      {segParts.map((p) => (
                        <View key={p.labelKey} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                          <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: p.color }} />
                          <MutedText style={{ textTransform: 'capitalize' }}>
                            {p.labelKey} ({p.value})
                          </MutedText>
                        </View>
                      ))}
                    </View>
                  </>
                )}

                {dailyCounts.some((n) => n > 0) && (
                  <View style={{ marginTop: 20 }}>
                    <MutedText style={{ fontWeight: '700', marginBottom: 8 }}>Volume d’envois par jour (14 j.)</MutedText>
                    <Sparkline values={dailyCounts} width={Math.min(340, 900)} height={52} strokeWidth={2.5} />
                  </View>
                )}
              </Card>
            </FadeIn>

            <FadeIn delayMs={200}>
              <Card style={{ borderWidth: 1, borderColor: t.colors.border }}>
                <H2>Échantillon des envois</H2>
                <MutedText style={{ marginTop: 6 }}>
                  {emails.length ? `Affichage des ${Math.min(25, emails.length)} premiers` : 'Aucun email en base pour cette campagne.'}
                </MutedText>
                <View style={{ marginTop: 12, gap: 10 }}>
                  {emails.slice(0, 25).map((row, idx) => (
                    <ScaleIn key={String(row.id ?? idx)} delayMs={Math.min(idx * 28, 320)}>
                      <View
                        style={[
                          styles.emailRow,
                          {
                            borderColor: t.colors.border,
                            backgroundColor: t.isDark ? 'rgba(255,255,255,0.03)' : 'rgba(16,24,40,0.03)',
                          },
                        ]}
                      >
                        <View style={{ flex: 1 }}>
                          <Text style={{ color: t.colors.text, fontWeight: '700' }} numberOfLines={1}>
                            {String(row.email ?? '—')}
                          </Text>
                          <Text
                            numberOfLines={1}
                            style={{ marginTop: 4, color: t.colors.muted, fontSize: 13 }}
                          >
                            {String(row.entreprise_nom || row.entreprise || '')}
                          </Text>
                        </View>
                        <View style={{ alignItems: 'flex-end' }}>
                          <Text style={{ color: t.colors.muted, fontSize: 11, textTransform: 'uppercase' }}>
                            {String(row.statut ?? '')}
                          </Text>
                          <Text style={{ color: t.colors.primary, fontWeight: '800', marginTop: 4 }}>
                            ↗ {safeNum(row.opens)} · ⎆ {safeNum(row.clicks)}
                          </Text>
                        </View>
                      </View>
                    </ScaleIn>
                  ))}
                </View>
              </Card>
            </FadeIn>

            {!!campagne && Object.keys(campagne).length > 0 && (
              <FadeIn delayMs={240}>
                <Pressable
                  onPress={() => {
                    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
                    setRawOpen((o) => !o);
                  }}
                  style={({ pressed }) => [
                    styles.rawHeader,
                    {
                      borderColor: t.colors.border,
                      backgroundColor: t.colors.card,
                      opacity: pressed ? 0.9 : 1,
                    },
                  ]}
                >
                  <MaterialCommunityIcons name="code-json" size={22} color={t.colors.primary} />
                  <Text style={{ flex: 1, color: t.colors.text, fontWeight: '800' }}>Données brutes (API)</Text>
                  <Animated.View
                    style={{
                      transform: [
                        {
                          rotate: rawProgress.interpolate({
                            inputRange: [0, 1],
                            outputRange: ['0deg', '180deg'],
                          }),
                        },
                      ],
                    }}
                  >
                    <MaterialCommunityIcons name="chevron-down" size={24} color={t.colors.muted} />
                  </Animated.View>
                </Pressable>
                <Animated.View style={{ maxHeight: rawMaxH, overflow: 'hidden' }}>
                  <Card style={{ borderTopWidth: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
                    <Text
                      selectable
                      style={{
                        fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
                        fontSize: 11,
                        color: t.colors.muted,
                      }}
                    >
                      {JSON.stringify(
                        {
                          campagne,
                          stats: stats
                            ? { ...stats, emails: `[${Array.isArray(stats.emails) ? stats.emails.length : 0} entrées]` }
                            : null,
                        },
                        null,
                        2,
                      )}
                    </Text>
                  </Card>
                </Animated.View>
              </FadeIn>
            )}
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, paddingBottom: 40, gap: 14 },
  hero: {
    borderWidth: 1.5,
    borderRadius: 16,
    padding: 16,
  },
  statutPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
  },
  inlineIcon: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 8,
    marginLeft: 4,
  },
  kpiGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  kpi: {
    width: '47%',
    flexGrow: 1,
    minWidth: 148,
    borderWidth: 1,
    borderRadius: 14,
    padding: 12,
  },
  kpiLabel: { fontSize: 11, fontWeight: '700', flex: 1 },
  kpiValue: { fontSize: 22, fontWeight: '900', marginTop: 8 },
  chartRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-around',
    gap: 16,
  },
  chartBlock: { alignItems: 'center', minWidth: 140 },
  emailRow: {
    flexDirection: 'row',
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    gap: 10,
  },
  rawHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 14,
    borderWidth: 1,
    borderRadius: 14,
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
  },
});
