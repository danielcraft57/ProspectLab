import AsyncStorage from '@react-native-async-storage/async-storage';
import type { MapRegion } from '../../features/map/carteMapTypes';

const KEY = 'prospectlab_carte_viewport_v1';

function isValidRegion(r: unknown): r is MapRegion {
  if (!r || typeof r !== 'object') return false;
  const o = r as Record<string, unknown>;
  return (
    typeof o.latitude === 'number' &&
    Number.isFinite(o.latitude) &&
    typeof o.longitude === 'number' &&
    Number.isFinite(o.longitude) &&
    typeof o.latitudeDelta === 'number' &&
    o.latitudeDelta > 0 &&
    typeof o.longitudeDelta === 'number' &&
    o.longitudeDelta > 0
  );
}

export async function loadCarteViewport(): Promise<MapRegion | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as unknown;
    return isValidRegion(p) ? p : null;
  } catch {
    return null;
  }
}

export async function saveCarteViewport(region: MapRegion): Promise<void> {
  try {
    await AsyncStorage.setItem(
      KEY,
      JSON.stringify({
        latitude: region.latitude,
        longitude: region.longitude,
        latitudeDelta: region.latitudeDelta,
        longitudeDelta: region.longitudeDelta,
      }),
    );
  } catch {
    /* ignore */
  }
}
