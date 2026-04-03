import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import { ProspectLabApi, type StatisticsOverviewData } from '../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../src/features/prospectlab/useToken';
import {
  dashboardCacheIsStale,
  readDashboardOverviewCache,
  writeDashboardOverviewCache,
} from '../../src/lib/cache/repositories';
import { emitNetworkRefreshIntent } from '../../src/features/network/networkToastBus';
import { useAppNetwork } from '../../src/lib/net/useAppNetwork';
import { useOnBecameOnline } from '../../src/lib/net/useOnBecameOnline';
import { Card, FadeIn, H1, H2, MiniBarChart, Mono, Muted, MutedText, Screen } from '../../src/ui/components';
import { DonutChart, SegmentedBar, Sparkline } from '../../src/ui/charts';
import { useTheme } from '../../src/ui/theme';

export default function DashboardScreen() {
  const t = useTheme();
  const { width } = useWindowDimensions();
  const isCompact = width < 430;
  const { token, loading: tokenLoading } = useApiToken();
  const { usableForApi } = useAppNetwork();
  const [stats, setStats] = useState<StatisticsOverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(
    async (opts?: { skipCache?: boolean }) => {
      if (!token) return;
      const force = !!opts?.skipCache;
      let localCache: { stats: StatisticsOverviewData | null; updatedAt: number } | null = null;
      if (!force) {
        localCache = await readDashboardOverviewCache();
        if (localCache) setStats(localCache.stats);
      }

      if (!usableForApi) {
        if (!localCache) setError('Hors ligne — pas de stats en cache.');
        setLoading(false);
        return;
      }

      const blocking = force || !localCache || dashboardCacheIsStale(localCache.updatedAt);
      if (!blocking) {
        setError(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const res = await ProspectLabApi.getStatisticsOverview(token, { days: 7 }, { skipCache: true });
        const data = res?.data ?? null;
        setStats(data);
        await writeDashboardOverviewCache(data);
      } catch (e: any) {
        if (!localCache) setError(e?.message ?? 'Erreur');
      } finally {
        setLoading(false);
      }
    },
    [token, usableForApi],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useOnBecameOnline(
    useCallback(() => {
      void load({ skipCache: true });
    }, [load]),
    !!token,
  );

  const quick = stats ?? {};
  const totals = quick.total_entreprises;
  const totalAnalyses = quick.total_analyses;
  const totalCampagnes = quick.total_campagnes;
  const totalEmails = quick.total_emails;

  const kpiValues = [totals ?? 0, totalAnalyses ?? 0, totalCampagnes ?? 0, totalEmails ?? 0].map((x) => (typeof x === 'number' ? x : 0));
  const trendCounts = (quick.trend_entreprises ?? []).map((x) => (typeof x.count === 'number' ? x.count : 0));
  const sparklineValues =
    trendCounts.length >= 2
      ? trendCounts
      : trendCounts.length === 1
        ? [Math.max(0, trendCounts[0] - 1), trendCounts[0]]
        : [kpiValues[0] * 0.65, kpiValues[0] * 0.72, kpiValues[0] * 0.8, kpiValues[0] * 0.88, kpiValues[0]];
  const donut = [
    { value: kpiValues[0], color: t.colors.primary },
    { value: kpiValues[1], color: t.colors.success },
    { value: kpiValues[2], color: t.colors.warning },
    { value: kpiValues[3], color: t.colors.danger },
  ];

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
              <H2>Token requis</H2>
              <Muted>Va dans Reglages pour coller ton token API ProspectLab.</Muted>
            </Card>
          </FadeIn>
        )}

        {!!token && (
          <>
            <FadeIn>
              <Card>
                <H2>Vue d'ensemble</H2>
                <View style={styles.grid}>
                  <View style={[styles.kpi, { borderColor: t.colors.border }]}>
                    <View style={styles.kpiHead}>
                      <MaterialCommunityIcons name="office-building-outline" size={16} color={t.colors.primary} />
                      <Muted>Entreprises</Muted>
                    </View>
                    <H1>{typeof totals === 'number' ? String(totals) : '-'}</H1>
                  </View>
                  <View style={[styles.kpi, { borderColor: t.colors.border }]}>
                    <View style={styles.kpiHead}>
                      <MaterialCommunityIcons name="chart-line" size={16} color={t.colors.primary} />
                      <Muted>Analyses</Muted>
                    </View>
                    <H1>{typeof totalAnalyses === 'number' ? String(totalAnalyses) : '-'}</H1>
                  </View>
                  <View style={[styles.kpi, { borderColor: t.colors.border }]}>
                    <View style={styles.kpiHead}>
                      <MaterialCommunityIcons name="email-outline" size={16} color={t.colors.primary} />
                      <Muted>Campagnes</Muted>
                    </View>
                    <H1>{typeof totalCampagnes === 'number' ? String(totalCampagnes) : '-'}</H1>
                  </View>
                  <View style={[styles.kpi, { borderColor: t.colors.border }]}>
                    <View style={styles.kpiHead}>
                      <FontAwesome6 name="envelope" size={14} color={t.colors.primary} />
                      <Muted>Emails</Muted>
                    </View>
                    <H1>{typeof totalEmails === 'number' ? String(totalEmails) : '-'}</H1>
                  </View>
                </View>
                <MiniBarChart values={kpiValues} />
              </Card>
            </FadeIn>

            <FadeIn delayMs={60}>
              <Card>
                <H2>Insights</H2>
                <MutedText style={{ marginTop: 6 }}>Un apercu visuel a partir des totaux.</MutedText>

                <View style={styles.insightsCol}>
                  <View>
                    <Muted>Repartition</Muted>
                    <View style={{ marginTop: 10 }}>
                      <DonutChart slices={donut} size={isCompact ? 104 : 120} thickness={14} />
                    </View>
                    <View style={{ marginTop: 10, gap: 6 }}>
                      <View style={styles.legendRow}>
                        <View style={[styles.legendDot, { backgroundColor: t.colors.primary }]} />
                        <Muted>Entreprises: {kpiValues[0]}</Muted>
                      </View>
                      <View style={styles.legendRow}>
                        <View style={[styles.legendDot, { backgroundColor: t.colors.success }]} />
                        <Muted>Analyses: {kpiValues[1]}</Muted>
                      </View>
                      <View style={styles.legendRow}>
                        <View style={[styles.legendDot, { backgroundColor: t.colors.warning }]} />
                        <Muted>Campagnes: {kpiValues[2]}</Muted>
                      </View>
                      <View style={styles.legendRow}>
                        <View style={[styles.legendDot, { backgroundColor: t.colors.danger }]} />
                        <Muted>Emails: {kpiValues[3]}</Muted>
                      </View>
                    </View>
                  </View>

                  <View>
                    <Muted>Tendance (nouvelles entreprises, 7 j.)</Muted>
                    <View style={{ marginTop: 10 }}>
                      <Sparkline width={Math.max(180, width - 84)} values={sparklineValues} />
                    </View>
                  </View>

                  <View>
                    <Muted>Mix</Muted>
                    <View style={{ marginTop: 8 }}>
                      <SegmentedBar
                        width={Math.max(180, width - 84)}
                        parts={[
                          { value: kpiValues[0], color: t.colors.primary },
                          { value: kpiValues[1], color: t.colors.success },
                          { value: kpiValues[2], color: t.colors.warning },
                          { value: kpiValues[3], color: t.colors.danger },
                        ]}
                      />
                    </View>
                  </View>
                </View>

                {!!error && <Mono>{error}</Mono>}
              </Card>
            </FadeIn>
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 12 },
  kpi: { width: '48%', borderWidth: 1, borderRadius: 14, padding: 12 },
  kpiHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  insightsCol: { marginTop: 12, gap: 14 },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  legendDot: { width: 9, height: 9, borderRadius: 999 },
});

