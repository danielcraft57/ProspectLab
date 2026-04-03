import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  InteractionManager,
  Image,
  Pressable,
  RefreshControl,
  StyleSheet,
  TextInput,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from 'react-native';
import { useRouter } from 'expo-router';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import {
  ActiveFilterStrip,
  AdvancedListFilters,
  type EntrepriseListFilters,
} from '../../../src/features/entreprises/AdvancedListFilters';
import { ProspectLabApi } from '../../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../../src/features/prospectlab/useToken';
import { clearProspectLabApiCache } from '../../../src/lib/http/apiMemoryCache';
import { HttpError } from '../../../src/lib/http/httpClient';
import {
  buildEntreprisesListCacheKey,
  entreprisesListCacheIsStale,
  readEntreprisesListCache,
  writeEntreprisesListCache,
} from '../../../src/lib/cache/repositories';
import { emitNetworkRefreshIntent } from '../../../src/features/network/networkToastBus';
import { useAppNetwork } from '../../../src/lib/net/useAppNetwork';
import { useOnBecameOnline } from '../../../src/lib/net/useOnBecameOnline';
import { Card, FadeIn, H2, Mono, Muted, MutedText, PrimaryButton, Screen } from '../../../src/ui/components';
import { useTheme } from '../../../src/ui/theme';

const PAGE_SIZE = 50;

type EntrepriseItem = {
  id?: number;
  nom?: string;
  website?: string;
  secteur?: string;
  statut?: string;
  email_principal?: string;
  telephone?: string;
  image?: string;
};

function asEntreprise(raw: Record<string, unknown>): EntrepriseItem {
  const logo = typeof raw.logo === 'string' && raw.logo.trim() ? raw.logo.trim() : undefined;
  const ogImage = typeof raw.og_image === 'string' && raw.og_image.trim() ? raw.og_image.trim() : undefined;
  const favicon = typeof raw.favicon === 'string' && raw.favicon.trim() ? raw.favicon.trim() : undefined;
  const image = logo || ogImage || favicon;

  return {
    id: typeof raw.id === 'number' ? raw.id : undefined,
    nom: typeof raw.nom === 'string' ? raw.nom : typeof raw.name === 'string' ? raw.name : undefined,
    website: typeof raw.website === 'string' ? raw.website : undefined,
    secteur: typeof raw.secteur === 'string' ? raw.secteur : undefined,
    statut: typeof raw.statut === 'string' ? raw.statut : undefined,
    email_principal: typeof raw.email_principal === 'string' ? raw.email_principal : undefined,
    telephone: typeof raw.telephone === 'string' ? raw.telephone : undefined,
    image,
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
  const { usableForApi } = useAppNetwork();
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
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [canDeleteEntreprises, setCanDeleteEntreprises] = useState(false);
  const loadSeq = useRef(0);
  const scrollLoadLock = useRef(false);

  useEffect(() => {
    if (!token) {
      setCanDeleteEntreprises(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await ProspectLabApi.getTokenInfo(token, { skipCache: true });
        const data = (res as { data?: { permissions?: Record<string, boolean> } })?.data;
        const perms = data?.permissions;
        const ok = !!perms?.entreprises_delete;
        if (!cancelled) setCanDeleteEntreprises(ok);
      } catch {
        if (!cancelled) setCanDeleteEntreprises(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

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
      const cacheKey = buildEntreprisesListCacheKey(appliedSearch, {
        secteur: listFilters.secteur,
        statut: listFilters.statut,
        opportunite: listFilters.opportunite,
      });
      let sqlList: Awaited<ReturnType<typeof readEntreprisesListCache>> = null;
      if (!opts?.skipCache) {
        sqlList = await readEntreprisesListCache(cacheKey);
        if (sqlList) {
          setItems(sqlList.items as EntrepriseItem[]);
          setTotal(sqlList.total);
        }
      }

      if (!usableForApi) {
        if (seq !== loadSeq.current) return;
        setLoadingMore(false);
        setListExhausted(false);
        setLoading(false);
        if (!sqlList) {
          setError('Hors ligne — pas de liste en cache pour ces filtres.');
          setItems([]);
          setTotal(null);
        } else setError(null);
        return;
      }

      setLoadingMore(false);
      setListExhausted(false);
      const blocking = !!opts?.skipCache || !sqlList || entreprisesListCacheIsStale(sqlList.updatedAt);
      if (!blocking) {
        if (seq === loadSeq.current) {
          setError(null);
          setLoading(false);
        }
        return;
      }
      setLoading(true);
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
          { skipCache: true },
        );
        if (seq !== loadSeq.current) return;
        const mapped = (res.data || []).map((r) => asEntreprise(r));
        setItems(mapped);
        if (typeof res.total === 'number') setTotal(res.total);
        else setTotal(null);
        if (mapped.length < PAGE_SIZE) setListExhausted(true);
        await writeEntreprisesListCache(cacheKey, mapped, typeof res.total === 'number' ? res.total : null);
      } catch (e: any) {
        if (seq !== loadSeq.current) return;
        setError(e?.message ?? 'Erreur');
        if (!sqlList) {
          setItems([]);
          setTotal(null);
        }
      } finally {
        if (seq === loadSeq.current) setLoading(false);
      }
    },
    [token, appliedSearch, listFilters.secteur, listFilters.statut, listFilters.opportunite, usableForApi],
  );

  /** Liste : après le premier rendu / interactions, pour ne pas bloquer l’ouverture de l’onglet. */
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    InteractionManager.runAfterInteractions(() => {
      if (!cancelled) void loadFirstPage();
    });
    return () => {
      cancelled = true;
    };
  }, [token, appliedSearch, loadFirstPage]);

  const loadMore = useCallback(async () => {
    if (scrollLoadLock.current) return;
    if (!token || loading || loadingMore || listExhausted) return;
    const cap = total ?? Number.POSITIVE_INFINITY;
    if (items.length >= cap) return;
    const offset = items.length;
    if (offset === 0) return;
    scrollLoadLock.current = true;
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
      scrollLoadLock.current = false;
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

  const onRefresh = useCallback(() => {
    emitNetworkRefreshIntent();
    void loadFirstPage({ skipCache: true });
  }, [loadFirstPage]);

  useOnBecameOnline(
    useCallback(() => {
      if (!token) return;
      void loadFirstPage({ skipCache: true });
      void (async () => {
        setMetaLoading(true);
        try {
          const [ref, st] = await Promise.all([
            ProspectLabApi.getReferenceCiblage(token, { skipCache: true }),
            ProspectLabApi.getEntrepriseStatuses(token, { skipCache: true }),
          ]);
          const raw = (ref as any)?.data ?? ref;
          setSecteurOptions(Array.isArray(raw?.secteurs) ? raw.secteurs : []);
          setOpportuniteOptions(Array.isArray(raw?.opportunites) ? raw.opportunites : []);
          const statusList = (st as any)?.data ?? st;
          setStatutOptions(Array.isArray(statusList) ? statusList : []);
        } catch {
          setSecteurOptions([]);
          setOpportuniteOptions([]);
          setStatutOptions([]);
        } finally {
          setMetaLoading(false);
        }
      })();
    }, [token, loadFirstPage]),
    !!token,
  );

  const confirmDeleteEntreprise = useCallback(
    (e: EntrepriseItem) => {
      if (e.id == null || !token) return;
      const label = (e.nom?.trim() || e.website || `#${e.id}`).slice(0, 120);
      Alert.alert(
        'Supprimer cette entreprise ?',
        `« ${label} » sera définitivement retirée de la base (données liées incluses).`,
        [
          { text: 'Annuler', style: 'cancel' },
          {
            text: 'Supprimer',
            style: 'destructive',
            onPress: () => {
              void (async () => {
                try {
                  setDeletingId(e.id!);
                  const res = await ProspectLabApi.deleteEntreprise(token, e.id!);
                  if (!res.success) {
                    Alert.alert('Erreur', res.error ?? 'Suppression impossible.');
                    return;
                  }
                  clearProspectLabApiCache();
                  setItems((prev) => prev.filter((x) => x.id !== e.id));
                  setTotal((n) => (typeof n === 'number' ? Math.max(0, n - 1) : n));
                } catch (err: unknown) {
                  let msg = 'Suppression impossible.';
                  if (err instanceof HttpError && err.info.bodyText) {
                    try {
                      const j = JSON.parse(err.info.bodyText) as { error?: string };
                      if (j?.error) msg = String(j.error);
                    } catch {
                      /* ignore */
                    }
                  } else if (err instanceof Error) msg = err.message;
                  Alert.alert('Erreur', msg);
                } finally {
                  setDeletingId(null);
                }
              })();
            },
          },
        ],
      );
    },
    [token],
  );

  const onScrollMaybeLoadMore = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      if (scrollLoadLock.current) return;
      if (!token || loading || loadingMore || listExhausted) return;
      const cap = total ?? Number.POSITIVE_INFINITY;
      if (items.length >= cap) return;
      if (items.length === 0) return;
      const { contentOffset, layoutMeasurement, contentSize } = e.nativeEvent;
      const visibleH = layoutMeasurement.height;
      const contentH = contentSize.height;
      const scrollable = contentH - visibleH;
      if (scrollable <= 8) return;
      const ratio = contentOffset.y / scrollable;
      if (ratio >= 0.5) void loadMore();
    },
    [token, loading, loadingMore, listExhausted, total, items.length, loadMore],
  );

  const summaryLine = useMemo(() => {
    if (!token) return '';
    if (loading && items.length === 0 && total === null) return 'Chargement…';
    if (total != null && total >= 0) {
      const fmt = total.toLocaleString('fr-FR');
      return total === 0 ? 'Total entreprises : 0' : `Total entreprises : ${fmt}`;
    }
    if (items.length === 0 && !loading) return 'Aucun résultat';
    if (items.length > 0) return `${items.length.toLocaleString('fr-FR')} fiche(s) affichée(s)`;
    return '';
  }, [token, loading, items.length, total]);

  const listHeader = (
    <View style={{ gap: 12, marginBottom: 12 }}>
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
        onScroll={onScrollMaybeLoadMore}
        scrollEventThrottle={120}
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.35}
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
            <Card
              style={[
                styles.cardPressable,
                { borderLeftWidth: 3, borderLeftColor: t.colors.primary, position: 'relative' },
              ]}
            >
              {e.id != null && canDeleteEntreprises && (
                <Pressable
                  onPress={() => confirmDeleteEntreprise(e)}
                  disabled={deletingId !== null}
                  style={[styles.deleteCorner, deletingId === e.id && { opacity: 0.75 }]}
                  hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                  accessibilityRole="button"
                  accessibilityLabel="Supprimer l'entreprise"
                >
                  {deletingId === e.id ? (
                    <ActivityIndicator size="small" color={t.colors.danger} />
                  ) : (
                    <View
                      style={[
                        styles.deleteIconRing,
                        { borderColor: `${t.colors.danger}66`, backgroundColor: `${t.colors.danger}16` },
                      ]}
                    >
                      <MaterialCommunityIcons name="delete-forever-outline" size={18} color={t.colors.danger} />
                    </View>
                  )}
                </Pressable>
              )}
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
                  Alert.alert(
                    'Détails indisponibles',
                    "Cette entreprise n'a pas d'id ni de contact utilisable pour charger les détails.",
                  );
                }}
                style={({ pressed }) => [{ opacity: pressed ? 0.92 : 1, transform: [{ scale: pressed ? 0.99 : 1 }] }]}
              >
                <View style={{ paddingRight: e.id != null && canDeleteEntreprises ? 44 : 0 }}>
                  <View style={styles.header}>
                    {e.image ? (
                      <Image
                        source={{ uri: e.image }}
                        style={[styles.avatar, { borderColor: t.colors.border }]}
                      />
                    ) : (
                      <View style={[styles.iconWrap, { backgroundColor: t.colors.border }]}>
                        <MaterialCommunityIcons name="office-building-outline" size={18} color={t.colors.primary} />
                      </View>
                    )}
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
                </View>
              </Pressable>
            </Card>
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
  deleteCorner: {
    position: 'absolute',
    bottom: 8,
    right: 8,
    zIndex: 4,
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 32,
    minHeight: 32,
  },
  deleteIconRing: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  iconWrap: { width: 34, height: 34, borderRadius: 999, alignItems: 'center', justifyContent: 'center', borderWidth: 0.5 },
  avatar: { width: 38, height: 38, borderRadius: 12, borderWidth: 0.5, overflow: 'hidden' },
  websiteRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2 },
  chipsRow: { flexDirection: 'row', gap: 8, marginTop: 10, flexWrap: 'wrap' },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, borderWidth: 1, backgroundColor: 'transparent' },
  footerLoad: { paddingVertical: 20, alignItems: 'center' },
});
