import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Keyboard,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Location from 'expo-location';
import CarteMapView from '../../src/features/map/CarteMapView';
import { CarteEntrepriseSheet } from '../../src/features/map/CarteEntrepriseSheet';
import type { CarteMapMarker, MapRegion } from '../../src/features/map/carteMapTypes';
import { carteVillesFromBundledPresets } from '../../src/features/map/carteVillesFallback';
import type { CarteVille } from '../../src/features/map/carteVillesTypes';
import { categoryIconsFromSecteur } from '../../src/features/map/entrepriseCategoryIcons';
import { markerColorFromEntreprise, paletteLegendColors } from '../../src/features/map/markerPalette';
import { ProspectLabApi } from '../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../src/features/prospectlab/useToken';
import { emitNetworkRefreshIntent } from '../../src/features/network/networkToastBus';
import {
  buildMapNearbyCacheKey,
  mapNearbyCacheIsStale,
  readMapNearbyCache,
  writeMapNearbyCache,
} from '../../src/lib/cache/repositories';
import { useAppNetwork } from '../../src/lib/net/useAppNetwork';
import { useOnBecameOnline } from '../../src/lib/net/useOnBecameOnline';
import { loadCarteViewport, saveCarteViewport } from '../../src/lib/map/carteViewportStorage';
import { prefetchOsmTilesForMapRegion } from '../../src/lib/map/osmTileFileCache';
import { getWebGeolocationCoords } from '../../src/lib/map/webGeolocation';
import { Screen } from '../../src/ui/components';
import { useTheme } from '../../src/ui/theme';

type MapEntreprise = {
  id: number;
  nom: string;
  latitude: number;
  longitude: number;
  secteur?: string | null;
  opportunite?: string | null;
  score_securite?: number | null;
  statut?: string | null;
  website?: string | null;
  note_google?: number | null;
  nb_avis_google?: number | null;
};

function asNumber(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim()) {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function normalizeItems(raw: unknown[]): MapEntreprise[] {
  const out: MapEntreprise[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const it = item as Record<string, unknown>;
    const id = asNumber(it.id);
    const lat = asNumber(it.latitude);
    const lng = asNumber(it.longitude);
    if (id == null || lat == null || lng == null) continue;
    out.push({
      id,
      nom: String(it.nom ?? `Entreprise #${id}`),
      latitude: lat,
      longitude: lng,
      secteur: (it.secteur as string | null | undefined) ?? null,
      opportunite: (it.opportunite as string | null | undefined) ?? null,
      score_securite: asNumber(it.score_securite),
      statut: (it.statut as string | null | undefined) ?? null,
      website: (it.website as string | null | undefined) ?? null,
      note_google: asNumber(it.note_google),
      nb_avis_google: asNumber(it.nb_avis_google),
    });
  }
  return out;
}

const RADIUS_KM = 12;
const REGION_LOAD_DEBOUNCE_MS = 650;
const PERSIST_VIEWPORT_MS = 500;
const AUTO_REFRESH_MS = 75_000;
const VILLES_RAYON_COUNT_KM = 25;

const PALETTE_STRIP = paletteLegendColors().slice(0, 10);

export default function CarteScreen() {
  const t = useTheme();
  const insets = useSafeAreaInsets();
  const { token } = useApiToken();
  const { usableForApi } = useAppNetwork();
  const [viewportReady, setViewportReady] = useState(false);
  const savedViewportRef = useRef<MapRegion | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<MapEntreprise[]>([]);
  const [region, setRegion] = useState<MapRegion>({
    latitude: 48.8566,
    longitude: 2.3522,
    latitudeDelta: 0.12,
    longitudeDelta: 0.12,
  });
  const [villes, setVilles] = useState<CarteVille[]>(() => carteVillesFromBundledPresets());
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const prefetchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const regionLoadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const persistTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadNearbyRef = useRef<
    (opts?: { force?: boolean; coords?: { latitude: number; longitude: number } }) => Promise<void>
  >(() => Promise.resolve());

  const markers: CarteMapMarker[] = useMemo(
    () =>
      items.map((e) => {
        const cat = categoryIconsFromSecteur(e.secteur);
        return {
        id: e.id,
        latitude: e.latitude,
        longitude: e.longitude,
        title: e.nom,
        description: e.secteur ?? undefined,
        pinColor: markerColorFromEntreprise(e),
        iconMaterial: cat.material,
        iconFaSolid: cat.faSolid,
        secteur: e.secteur,
        statut: e.statut,
        opportunite: e.opportunite,
        score_securite: e.score_securite,
        note_google: e.note_google,
        nb_avis_google: e.nb_avis_google,
        website: e.website,
      };
      }),
    [items],
  );

  const selectedMarker = useMemo(
    () => (selectedId != null ? markers.find((m) => m.id === selectedId) ?? null : null),
    [markers, selectedId],
  );

  const queuePersistViewport = useCallback((r: MapRegion) => {
    if (persistTimerRef.current) clearTimeout(persistTimerRef.current);
    persistTimerRef.current = setTimeout(() => {
      void saveCarteViewport(r);
    }, PERSIST_VIEWPORT_MS);
  }, []);

  const loadNearby = useCallback(
    async (opts?: { force?: boolean; coords?: { latitude: number; longitude: number } }) => {
      if (!token) return;
      setLoading(true);
      setError(null);
      try {
        const lat = opts?.coords?.latitude ?? region.latitude;
        const lng = opts?.coords?.longitude ?? region.longitude;
        const cacheKey = buildMapNearbyCacheKey({
          latitude: lat,
          longitude: lng,
          radiusKm: RADIUS_KM,
        });
        const cached = await readMapNearbyCache(cacheKey);
        if (cached) {
          setItems(normalizeItems(cached.items));
          if (!usableForApi && !opts?.force) {
            setLoading(false);
            return;
          }
          if (!opts?.force && !mapNearbyCacheIsStale(cached.updatedAt)) {
            setLoading(false);
            return;
          }
        }

        if (!usableForApi) {
          emitNetworkRefreshIntent();
          setLoading(false);
          return;
        }

        const res = await ProspectLabApi.listNearbyEntreprises(
          token,
          { latitude: lat, longitude: lng, rayonKm: RADIUS_KM, limit: 150 },
          { skipCache: !!opts?.force },
        );
        const fresh = normalizeItems((res?.data as unknown[]) ?? []);
        setItems(fresh);
        await writeMapNearbyCache(cacheKey, fresh);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    [region.latitude, region.longitude, token, usableForApi],
  );

  loadNearbyRef.current = loadNearby;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const saved = await loadCarteViewport();
      if (cancelled) return;
      if (saved) {
        savedViewportRef.current = saved;
        setRegion(saved);
      }
      setViewportReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await ProspectLabApi.getReferenceCarteVilles(
          token,
          { rayonKm: VILLES_RAYON_COUNT_KM },
          { skipCache: false },
        );
        const rows = res?.data;
        if (cancelled || !Array.isArray(rows) || rows.length === 0) return;
        setVilles(
          rows.map((r) => ({
            label: r.label,
            latitude: r.latitude,
            longitude: r.longitude,
            count: typeof r.count === 'number' ? r.count : undefined,
            region: r.region,
            department: r.department,
          })),
        );
      } catch {
        if (!cancelled) setVilles(carteVillesFromBundledPresets());
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useOnBecameOnline(() => {
    void loadNearby({ force: true });
  }, !!token);

  const scheduleTilePrefetch = useCallback((r: MapRegion) => {
    if (Platform.OS === 'web') return;
    if (prefetchTimerRef.current) clearTimeout(prefetchTimerRef.current);
    prefetchTimerRef.current = setTimeout(() => {
      void prefetchOsmTilesForMapRegion({
        latitude: r.latitude,
        longitude: r.longitude,
        latitudeDelta: r.latitudeDelta,
        longitudeDelta: r.longitudeDelta,
      });
    }, 450);
  }, []);

  useEffect(
    () => () => {
      if (prefetchTimerRef.current) clearTimeout(prefetchTimerRef.current);
      if (regionLoadTimerRef.current) clearTimeout(regionLoadTimerRef.current);
      if (persistTimerRef.current) clearTimeout(persistTimerRef.current);
    },
    [],
  );

  /** Après restauration viewport : charge fiches ; sinon géoloc puis fallback. */
  useEffect(() => {
    if (!viewportReady || !token) return;
    let cancelled = false;

    (async () => {
      if (savedViewportRef.current) {
        const r = savedViewportRef.current;
        scheduleTilePrefetch(r);
        await loadNearbyRef.current({
          coords: { latitude: r.latitude, longitude: r.longitude },
          force: false,
        });
        return;
      }

      if (Platform.OS === 'web') {
        try {
          const c = await getWebGeolocationCoords();
          if (cancelled) return;
          const next: MapRegion = {
            latitude: c.latitude,
            longitude: c.longitude,
            latitudeDelta: 0.08,
            longitudeDelta: 0.08,
          };
          setRegion(next);
          queuePersistViewport(next);
          scheduleTilePrefetch(next);
          await loadNearbyRef.current({ coords: c, force: false });
        } catch {
          if (!cancelled) void loadNearbyRef.current();
        }
        return;
      }

      try {
        const perm = await Location.requestForegroundPermissionsAsync();
        if (cancelled) return;
        if (perm.status === 'granted') {
          const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
          if (cancelled) return;
          const next: MapRegion = {
            latitude: loc.coords.latitude,
            longitude: loc.coords.longitude,
            latitudeDelta: 0.08,
            longitudeDelta: 0.08,
          };
          setRegion(next);
          queuePersistViewport(next);
          scheduleTilePrefetch(next);
          await loadNearbyRef.current({ coords: loc.coords, force: false });
          return;
        }
      } catch {
        /* Paris */
      }
      if (cancelled) return;
      scheduleTilePrefetch(region);
      void loadNearbyRef.current();
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bootstrap viewport + token
  }, [viewportReady, token]);

  useEffect(() => {
    if (!token) return;
    const id = setInterval(() => {
      void loadNearbyRef.current({ force: false });
    }, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [token]);

  const filteredVilles = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const base = villes;
    if (!q) {
      return base.slice(0, 14);
    }
    return base
      .filter(
        (v) =>
          v.label.toLowerCase().includes(q) ||
          (v.department && v.department.toLowerCase().includes(q)) ||
          (v.region && v.region.toLowerCase().includes(q)),
      )
      .slice(0, 24);
  }, [villes, searchQuery]);

  const selectVille = useCallback(
    (v: CarteVille) => {
      Keyboard.dismiss();
      setSearchFocused(false);
      setSearchQuery('');
      const next: MapRegion = {
        latitude: v.latitude,
        longitude: v.longitude,
        latitudeDelta: 0.09,
        longitudeDelta: 0.09,
      };
      setRegion(next);
      queuePersistViewport(next);
      scheduleTilePrefetch(next);
      void loadNearby({
        force: true,
        coords: { latitude: v.latitude, longitude: v.longitude },
      });
    },
    [loadNearby, queuePersistViewport, scheduleTilePrefetch],
  );

  const onRegionChangeComplete = useCallback(
    (r: MapRegion) => {
      setRegion(r);
      queuePersistViewport(r);
      scheduleTilePrefetch(r);
      if (regionLoadTimerRef.current) clearTimeout(regionLoadTimerRef.current);
      regionLoadTimerRef.current = setTimeout(() => {
        void loadNearby({
          force: false,
          coords: { latitude: r.latitude, longitude: r.longitude },
        });
      }, REGION_LOAD_DEBOUNCE_MS);
    },
    [loadNearby, queuePersistViewport, scheduleTilePrefetch],
  );

  const onMarkerPress = useCallback((id: number) => {
    setSelectedId(id);
    setSheetOpen(true);
  }, []);

  const closeSheet = useCallback(() => {
    setSheetOpen(false);
    setSelectedId(null);
  }, []);

  return (
    <Screen>
      <View style={styles.column}>
        <View
          style={[
            styles.searchSection,
            {
              paddingLeft: Math.max(12, insets.left),
              paddingRight: Math.max(12, insets.right),
            },
          ]}
        >
          <TextInput
            value={searchQuery}
            onChangeText={setSearchQuery}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => {
              setTimeout(() => setSearchFocused(false), 200);
            }}
            placeholder="Rechercher une ville (Grand Est)…"
            placeholderTextColor={t.colors.muted}
            autoCorrect={false}
            autoCapitalize="words"
            returnKeyType="search"
            style={[
              styles.searchInput,
              {
                borderColor: t.colors.border,
                backgroundColor: t.colors.card,
                color: t.colors.text,
              },
            ]}
          />
          {searchFocused && filteredVilles.length > 0 && (
            <ScrollView
              keyboardShouldPersistTaps="handled"
              nestedScrollEnabled
              style={[styles.suggestions, { borderColor: t.colors.border, backgroundColor: t.colors.card }]}
            >
              {filteredVilles.map((v) => (
                <Pressable
                  key={`${v.label}-${v.latitude}-${v.longitude}`}
                  onPress={() => selectVille(v)}
                  style={({ pressed }) => [
                    styles.suggestionRow,
                    {
                      borderBottomColor: t.colors.border,
                      backgroundColor: pressed ? t.colors.bg : t.colors.card,
                    },
                  ]}
                >
                  <Text style={{ color: t.colors.text, flex: 1 }} numberOfLines={1}>
                    {v.label}
                    {v.department ? (
                      <Text style={{ color: t.colors.muted, fontSize: 12 }}>{`  · ${v.department}`}</Text>
                    ) : null}
                  </Text>
                  {typeof v.count === 'number' ? (
                    <Text style={{ color: t.colors.muted, fontSize: 12, marginLeft: 8 }}>{v.count} fiches</Text>
                  ) : null}
                </Pressable>
              ))}
            </ScrollView>
          )}
          {!!error && (
            <Text style={[styles.errorBanner, { color: t.colors.danger, backgroundColor: t.colors.card }]}>
              {error}
            </Text>
          )}
        </View>

        <View style={styles.mapSlot}>
          {loading ? (
            <View style={[styles.loadingPill, { backgroundColor: t.colors.card }]}>
              <ActivityIndicator color={t.colors.primary} size="small" />
            </View>
          ) : null}
          <CarteMapView
            region={region}
            onRegionChangeComplete={onRegionChangeComplete}
            markers={markers}
            onMarkerPress={onMarkerPress}
          />
          <View
            style={[
              styles.legendBar,
              {
                backgroundColor: t.isDark ? 'rgba(18,25,37,0.92)' : 'rgba(255,255,255,0.92)',
                paddingLeft: 10 + insets.left,
                paddingRight: 10 + insets.right,
              },
            ]}
            pointerEvents="none"
          >
            <Text style={{ color: t.colors.muted, fontSize: 10 }}>
              {`© OSM · ~${RADIUS_KM} km · ${items.length} fiche(s) · icône = activité · couleurs = secteur + statut + opportunité + score`}
            </Text>
            <View style={styles.paletteRow}>
              {PALETTE_STRIP.map((c) => (
                <View key={c} style={[styles.paletteDot, { backgroundColor: c }]} />
              ))}
            </View>
          </View>
        </View>
      </View>

      <CarteEntrepriseSheet visible={sheetOpen} marker={selectedMarker} token={token} onClose={closeSheet} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  column: {
    flex: 1,
    margin: 0,
    padding: 0,
  },
  searchSection: {
    paddingTop: 6,
    paddingBottom: 4,
    zIndex: 20,
    elevation: 20,
  },
  searchInput: {
    width: '100%',
    minHeight: 46,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === 'web' ? 11 : 9,
    fontSize: 16,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.08,
        shadowRadius: 3,
      },
      android: { elevation: 2 },
      default: {},
    }),
  },
  suggestions: {
    marginTop: 6,
    maxHeight: 200,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 12,
    overflow: 'hidden',
  },
  suggestionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 11,
    paddingHorizontal: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  errorBanner: {
    marginTop: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 13,
    fontWeight: '600',
    borderRadius: 10,
  },
  mapSlot: {
    flex: 1,
    minHeight: 0,
    margin: 0,
    padding: 0,
    position: 'relative',
  },
  loadingPill: {
    position: 'absolute',
    top: 10,
    right: 12,
    zIndex: 15,
    elevation: 14,
    paddingHorizontal: 11,
    paddingVertical: 8,
    borderRadius: 20,
  },
  legendBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    paddingVertical: 8,
    zIndex: 12,
    elevation: 12,
  },
  paletteRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
    marginTop: 6,
    alignItems: 'center',
  },
  paletteDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: 'rgba(0,0,0,0.12)',
  },
});
