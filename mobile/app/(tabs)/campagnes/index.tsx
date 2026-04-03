import { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import { ProspectLabApi } from '../../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../../src/features/prospectlab/useToken';
import { useOnBecameOnline } from '../../../src/lib/net/useOnBecameOnline';
import { Card, FadeIn, H2, Mono, Muted, MutedText, PrimaryButton, Screen } from '../../../src/ui/components';
import { useTheme } from '../../../src/ui/theme';

type CampagneItem = {
  id?: number;
  nom?: string;
  statut?: string;
  total_destinataires?: number;
  total_envoyes?: number;
  total_reussis?: number;
  date_creation?: string;
};

function asCampagne(raw: Record<string, unknown>): CampagneItem {
  return {
    id: typeof raw.id === 'number' ? raw.id : undefined,
    nom: typeof raw.nom === 'string' ? raw.nom : undefined,
    statut: typeof raw.statut === 'string' ? raw.statut : undefined,
    total_destinataires: typeof raw.total_destinataires === 'number' ? raw.total_destinataires : undefined,
    total_envoyes: typeof raw.total_envoyes === 'number' ? raw.total_envoyes : undefined,
    total_reussis: typeof raw.total_reussis === 'number' ? raw.total_reussis : undefined,
    date_creation: typeof raw.date_creation === 'string' ? raw.date_creation : undefined,
  };
}

function statutStyle(statut: string | undefined, t: ReturnType<typeof useTheme>) {
  const s = (statut || '').toLowerCase();
  if (s === 'completed') return { fg: t.colors.success, bg: t.colors.success + '22', label: 'Terminée' };
  if (s === 'running') return { fg: t.colors.primary, bg: t.colors.primary + '24', label: 'En cours' };
  if (s === 'scheduled') return { fg: t.colors.warning, bg: t.colors.warning + '30', label: 'Programmée' };
  if (s === 'failed') return { fg: t.colors.danger, bg: t.colors.danger + '22', label: 'Échec' };
  if (s === 'draft') return { fg: t.colors.muted, bg: t.colors.border, label: 'Brouillon' };
  return { fg: t.colors.text, bg: t.colors.border, label: statut ?? '—' };
}

export default function CampagnesScreen() {
  const t = useTheme();
  const router = useRouter();
  const { token, loading: tokenLoading } = useApiToken();
  const [items, setItems] = useState<CampagneItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(
    async (opts?: { skipCache?: boolean }) => {
      if (!token) return;
      setLoading(true);
      setError(null);
      try {
        const res = await ProspectLabApi.listCampagnes(token, { limit: 50, offset: 0 }, { skipCache: opts?.skipCache });
        setItems((res.data || []).map((r) => asCampagne(r)));
      } catch (e: any) {
        setError(e?.message ?? 'Erreur');
      } finally {
        setLoading(false);
      }
    },
    [token],
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

  const summaryLine = useMemo(() => {
    if (!token) return '';
    if (loading && items.length === 0) return 'Chargement…';
    if (items.length === 0) return 'Aucun résultat';
    return `Total campagnes : ${items.length.toLocaleString('fr-FR')}`;
  }, [token, loading, items.length]);

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.listHeader}>
          {!tokenLoading && !token && (
            <FadeIn>
              <Card>
                <Muted>Token manquant. Va dans Reglages.</Muted>
              </Card>
            </FadeIn>
          )}

          {!!token && (
            <>
              <FadeIn>
                <Card>
                  <H2>Actions</H2>
                  <MutedText style={{ marginTop: 6 }}>
                    Touchez une campagne pour le tableau de bord détaillé (graphiques, tracking, envois).
                  </MutedText>
                  <View style={{ marginTop: 10 }}>
                    <PrimaryButton
                      title={loading ? 'Chargement...' : 'Rafraichir'}
                      onPress={() => load({ skipCache: true })}
                      disabled={loading}
                    />
                  </View>
                  {!!error && <Mono>{error}</Mono>}
                </Card>
              </FadeIn>

              <FadeIn delayMs={120}>
                <MutedText style={{ paddingHorizontal: 2 }}>{summaryLine}</MutedText>
              </FadeIn>
            </>
          )}
        </View>

        {items.map((c, idx) => {
          const st = statutStyle(c.statut, t);
          return (
            <FadeIn key={`${c.id ?? idx}`} delayMs={40 + idx * 12}>
              <Pressable
                onPress={() => {
                  if (c.id == null) return;
                  router.push({
                    pathname: '/(tabs)/campagnes/details',
                    params: { id: String(c.id) },
                  });
                }}
                disabled={c.id == null}
                style={({ pressed }) => [{ opacity: pressed ? 0.92 : 1, transform: [{ scale: pressed ? 0.992 : 1 }] }]}
              >
                <Card
                  style={[
                    styles.cardPress,
                    {
                      borderLeftWidth: 4,
                      borderLeftColor: st.fg,
                      borderColor: t.colors.border,
                    },
                  ]}
                >
                  <View style={styles.rowTop}>
                    <View style={[styles.iconWrap, { backgroundColor: st.bg }]}>
                      <MaterialCommunityIcons name="email-newsletter" size={20} color={st.fg} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <H2>{c.nom ?? '(sans nom)'}</H2>
                      <View style={[styles.pill, { alignSelf: 'flex-start', marginTop: 8, backgroundColor: st.bg }]}>
                        <Text style={{ color: st.fg, fontWeight: '800', fontSize: 11 }}>{st.label}</Text>
                      </View>
                    </View>
                    <MaterialCommunityIcons name="chevron-right" size={22} color={t.colors.muted} />
                  </View>
                  <View style={[styles.row, { marginTop: 12 }]}>
                    <FontAwesome6 name="paper-plane" size={12} color={t.colors.primary} />
                    <Muted>
                      Envoyés: {c.total_envoyes ?? '?'} / {c.total_destinataires ?? '?'} — Réussis: {c.total_reussis ?? '?'}
                    </Muted>
                  </View>
                  {!!c.date_creation && (
                    <View style={[styles.row, { marginTop: 8 }]}>
                      <FontAwesome6 name="calendar" size={12} color={t.colors.primary} />
                      <Muted>Créée : {c.date_creation}</Muted>
                    </View>
                  )}
                </Card>
              </Pressable>
            </FadeIn>
          );
        })}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  listHeader: { gap: 12, marginBottom: 12 },
  cardPress: { padding: 14 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowTop: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
});
