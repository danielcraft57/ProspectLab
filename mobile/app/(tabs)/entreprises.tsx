import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import {
  ActiveFilterStrip,
  AdvancedListFilters,
  type EntrepriseListFilters,
} from '../../src/features/entreprises/AdvancedListFilters';
import { ProspectLabApi } from '../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../src/features/prospectlab/useToken';
import { Card, FadeIn, H1, H2, Mono, Muted, MutedText, PrimaryButton, Screen } from '../../src/ui/components';
import { useTheme } from '../../src/ui/theme';

const PAGE_SIZE = 50;

type EntrepriseItem = {
  id?: number;
  nom?: string;
  website?: string;
  secteur?: string;
  statut?: string;
  email_principal?: string;
  telephone?: string;
};

function asEntreprise(raw: Record<string, unknown>): EntrepriseItem {
  return {
    id: typeof raw.id === 'number' ? raw.id : undefined,
    nom: typeof raw.nom === 'string' ? raw.nom : typeof raw.name === 'string' ? raw.name : undefined,
    website: typeof raw.website === 'string' ? raw.website : undefined,
    secteur: typeof raw.secteur === 'string' ? raw.secteur : undefined,
    statut: typeof raw.statut === 'string' ? raw.statut : undefined,
    email_principal: typeof raw.email_principal === 'string' ? raw.email_principal : undefined,
    telephone: typeof raw.telephone === 'string' ? raw.telephone : undefined,
  };
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

export default function EntreprisesScreen() {
  const t = useTheme();
  const router = useRouter();
  const { token, loading: tokenLoading } = useApiToken();
  const [items, setItems] = useState<EntrepriseItem[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [listExhausted, setListExhausted] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const debouncedSearch = useDebouncedValue(searchInput.trim(), 450);
  const [appliedSearch, setAppliedSearch] = useState('');
  const [listFilters, setListFilters] = useState<EntrepriseListFilters>({});
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const [secteurOptions, setSecteurOptions] = useState<string[]>([]);
  const [opportuniteOptions, setOpportuniteOptions] = useState<string[]>([]);
  const [statutOptions, setStatutOptions] = useState<string[]>([]);
  const [metaLoading, setMetaLoading] = useState(false);
  const loadSeq = useRef(0);

  useEffect(() => {
    if (!token) {
      setSecteurOptions([]);
      setOpportuniteOptions([]);
      setStatutOptions([]);
      return;
    }
    let cancelled = false;
    setMetaLoading(true);
    (async () => {
      try {
        const [ref, st] = await Promise.all([
          ProspectLabApi.getReferenceCiblage(token),
          ProspectLabApi.getEntrepriseStatuses(token),
        ]);
        if (cancelled) return;
        const raw = (ref as any)?.data ?? ref;
        setSecteurOptions(Array.isArray(raw?.secteurs) ? raw.secteurs : []);
        setOpportuniteOptions(Array.isArray(raw?.opportunites) ? raw.opportunites : []);
        const statusList = (st as any)?.data ?? st;
        setStatutOptions(Array.isArray(statusList) ? statusList : []);
      } catch {
        if (!cancelled) {
          setSecteurOptions([]);
          setOpportuniteOptions([]);
          setStatutOptions([]);
        }
      } finally {
        if (!cancelled) setMetaLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  /** Applique la recherche (synchronisée avec le debounce ou le bouton). */
  useEffect(() => {
    setAppliedSearch(debouncedSearch);
  }, [debouncedSearch]);

  const loadFirstPage = useCallback(
    async (opts?: { skipCache?: boolean }) => {
      if (!token) return;
      const seq = ++loadSeq.current;
      setLoading(true);
      setLoadingMore(false);
      setListExhausted(false);
      setError(null);
      try {
        const res = await ProspectLabApi.listEntreprises(
          token,
          {
            limit: PAGE_SIZE,
            offset: 0,
            search: appliedSearch || undefined,
            secteur: listFilters.secteur,
            statut: listFilters.statut,
            opportunite: listFilters.opportunite,
          },
          { skipCache: opts?.skipCache },
        );
        if (seq !== loadSeq.current) return;
        const mapped = (res.data || []).map((r) => asEntreprise(r));
        setItems(mapped);
        if (typeof res.total === 'number') setTotal(res.total);
        else setTotal(null);
        if (mapped.length < PAGE_SIZE) setListExhausted(true);
      } catch (e: any) {
        if (seq !== loadSeq.current) return;
        setError(e?.message ?? 'Erreur');
        setItems([]);
        setTotal(null);
      } finally {
        if (seq === loadSeq.current) setLoading(false);
      }
    },
    [token, appliedSearch],
  );

  useEffect(() => {
    if (token) loadFirstPage();
  }, [token, appliedSearch, loadFirstPage]);

  const loadMore = useCallback(async () => {
    if (!token || loading || loadingMore || listExhausted) return;
    const cap = total ?? Number.POSITIVE_INFINITY;
    if (items.length >= cap) return;
    const offset = items.length;
    if (offset === 0) return;
    setLoadingMore(true);
    setError(null);
    try {
      const res = await ProspectLabApi.listEntreprises(token, {
        limit: PAGE_SIZE,
        offset,
        search: appliedSearch || undefined,
        secteur: listFilters.secteur,
        statut: listFilters.statut,
        opportunite: listFilters.opportunite,
      });
      const mapped = (res.data || []).map((r) => asEntreprise(r));
      if (mapped.length === 0) {
        setListExhausted(true);
        return;
      }
      if (mapped.length < PAGE_SIZE) setListExhausted(true);
      setItems((prev) => {
        const seen = new Set(prev.map((p) => p.id).filter((x): x is number => typeof x === 'number'));
        const merged = [...prev];
        for (const m of mapped) {
          if (m.id != null && seen.has(m.id)) continue;
          if (m.id != null) seen.add(m.id);
          merged.push(m);
        }
        return merged;
      });
      if (typeof res.total === 'number') setTotal(res.total);
    } catch (e: any) {
      setError(e?.message ?? 'Erreur');
    } finally {
      setLoadingMore(false);
    }
  }, [
    token,
    loading,
    loadingMore,
    listExhausted,
    items.length,
    total,
    appliedSearch,
    listFilters.secteur,
    listFilters.statut,
    listFilters.opportunite,
  ]);

  const onRefresh = useCallback(() => loadFirstPage({ skipCache: true }), [loadFirstPage]);

  const summaryLine = useMemo(() => {
    if (!token) return '';
    if (loading && items.length === 0) return 'Chargement…';
    const n = items.length;
    const t = total;
    if (t != null && t > 0) {
      return n < t ? `Affichage de ${n} sur ${t} entreprise(s)` : `${t} entreprise(s) — tout affiché`;
    }
    if (n === 0) return 'Aucun résultat';
    return `${n} sur cette page — faites défiler pour charger la suite`;
  }, [token, loading, items.length, total]);

  const listHeader = (
    <View style={{ gap: 12, marginBottom: 12 }}>
      <H1>Entreprises</H1>
      {!tokenLoading && !token && (
        <FadeIn>
          <Card>
            <Muted>Token manquant. Va dans Reglages.</Muted>
          </Card>
        </FadeIn>
      )}
      {!!token && (
        <FadeIn delayMs={40}>
          <AdvancedListFilters
            theme={t}
            expanded={filtersExpanded}
            onExpandedChange={setFiltersExpanded}
            secteurs={secteurOptions}
            opportunites={opportuniteOptions}
            statuts={statutOptions}
            value={listFilters}
            onChange={setListFilters}
            disabled={metaLoading}
          />
        </FadeIn>
      )}
      {!!token && (
        <FadeIn delayMs={90}>
          <ActiveFilterStrip value={listFilters} onChange={setListFilters} t={t} />
        </FadeIn>
      )}
      {!!token && (
        <FadeIn delayMs={120}>
          <Card>
            <H2>Recherche textuelle</H2>
            <Muted>
              Combine librement avec les filtres ci‑dessus. Pagination : environ {PAGE_SIZE} fiches par chargement, faites défiler pour la suite.
            </Muted>
            <TextInput
              value={searchInput}
              onChangeText={setSearchInput}
              placeholder="Nom, website, etc."
              placeholderTextColor={t.colors.muted}
              selectionColor={t.colors.primary}
              style={[
                styles.input,
                {
                  borderColor: t.colors.border,
                  color: t.colors.text,
                  backgroundColor: t.colors.bg,
                },
              ]}
              autoCapitalize="none"
              autoCorrect={false}
              returnKeyType="search"
              onSubmitEditing={() => setAppliedSearch(searchInput.trim())}
            />
            <View style={{ marginTop: 10 }}>
              <PrimaryButton
                title={loading ? 'Chargement...' : 'Rechercher maintenant'}
                onPress={() => {
                  const q = searchInput.trim();
                  if (q !== appliedSearch) setAppliedSearch(q);
                  else void loadFirstPage({ skipCache: true });
                }}
                disabled={loading}
              />
            </View>
            {!!error && (
              <View style={{ marginTop: 8 }}>
                <Mono>{error}</Mono>
              </View>
            )}
          </Card>
        </FadeIn>
      )}
      {!!token && (
        <FadeIn delayMs={160}>
          <MutedText style={{ paddingHorizontal: 2 }}>{summaryLine}</MutedText>
        </FadeIn>
      )}
      {!!token && loading && items.length === 0 && (
        <ActivityIndicator color={t.colors.primary} style={{ marginTop: 8 }} />
      )}
    </View>
  );

  return (
    <Screen>
      <FlatList
        data={items}
        keyExtractor={(e, idx) => (e.id != null ? `e-${e.id}` : `i-${e.website ?? idx}`)}
        ListHeaderComponent={listHeader}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={loading && items.length > 0} onRefresh={onRefresh} tintColor={t.colors.primary} />
        }
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        ListFooterComponent={
          loadingMore ? (
            <View style={styles.footerLoad}>
              <ActivityIndicator color={t.colors.primary} />
              <MutedText style={{ marginTop: 8 }}>Chargement…</MutedText>
            </View>
          ) : null
        }
        renderItem={({ item: e, index: idx }) => (
          <FadeIn delayMs={Math.min(40 + idx * 8, 400)}>
            <Pressable
              onPress={() => {
                if (e.id != null) {
                  router.push({
                    pathname: '/(tabs)/entreprises/details',
                    params: { kind: 'id', value: String(e.id) },
                  });
                  return;
                }
                const website = e.website?.trim();
                const email = e.email_principal?.trim();
                const phone = e.telephone?.trim();
                if (website) {
                  router.push({
                    pathname: '/(tabs)/entreprises/details',
                    params: { kind: 'website', value: encodeURIComponent(website) },
                  });
                  return;
                }
                if (email) {
                  router.push({
                    pathname: '/(tabs)/entreprises/details',
                    params: { kind: 'email', value: encodeURIComponent(email) },
                  });
                  return;
                }
                if (phone) {
                  router.push({
                    pathname: '/(tabs)/entreprises/details',
                    params: { kind: 'phone', value: encodeURIComponent(phone) },
                  });
                  return;
                }
                Alert.alert("Détails indisponibles", "Cette entreprise n'a pas d'id ni de contact utilisable pour charger les détails.");
              }}
              style={({ pressed }) => [{ opacity: pressed ? 0.92 : 1, transform: [{ scale: pressed ? 0.99 : 1 }] }]}
            >
              <Card style={[styles.cardPressable, { borderLeftWidth: 3, borderLeftColor: t.colors.primary }]}>
                <View style={styles.header}>
                  <View style={[styles.iconWrap, { backgroundColor: t.colors.border }]}>
                    <MaterialCommunityIcons name="office-building-outline" size={18} color={t.colors.primary} />
                  </View>
                  <View style={{ flex: 1, gap: 4 }}>
                    <H2>{e.nom ?? '(sans nom)'}</H2>
                    {!!e.website && (
                      <View style={styles.websiteRow}>
                        <FontAwesome6 name="globe" size={12} color={t.colors.primary} />
                        <Mono>{e.website}</Mono>
                      </View>
                    )}
                  </View>
                </View>

                <View style={styles.chipsRow}>
                  <View style={[styles.chip, { borderColor: t.colors.border }]}>
                    <Muted>{e.secteur ?? 'Secteur ?'}</Muted>
                  </View>
                  <View style={[styles.chip, { borderColor: t.colors.border }]}>
                    <Muted>{e.statut ?? 'Statut ?'}</Muted>
                  </View>
                </View>

                {!!e.email_principal && (
                  <View style={styles.row}>
                    <FontAwesome6 name="envelope" size={12} color={t.colors.primary} />
                    <Muted>Email: {e.email_principal}</Muted>
                  </View>
                )}
                {!!e.telephone && (
                  <View style={styles.row}>
                    <FontAwesome6 name="phone" size={12} color={t.colors.primary} />
                    <Muted>Tel: {e.telephone}</Muted>
                  </View>
                )}
              </Card>
            </Pressable>
          </FadeIn>
        )}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  listContent: { padding: 16, paddingBottom: 32 },
  input: { borderWidth: 1, borderColor: '#ddd', borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, marginTop: 10 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardPressable: { padding: 14, marginBottom: 12 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  iconWrap: { width: 34, height: 34, borderRadius: 999, alignItems: 'center', justifyContent: 'center', borderWidth: 0.5 },
  websiteRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2 },
  chipsRow: { flexDirection: 'row', gap: 8, marginTop: 10, flexWrap: 'wrap' },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, borderWidth: 1, backgroundColor: 'transparent' },
  footerLoad: { paddingVertical: 20, alignItems: 'center' },
});
