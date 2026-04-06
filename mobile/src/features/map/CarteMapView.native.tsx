import {
  addCustomHeader,
  Camera,
  CircleLayer,
  MapView,
  RasterLayer,
  RasterSource,
  removeCustomHeader,
  ShapeSource,
  UserLocation,
  type RegionPayload,
} from '@maplibre/maplibre-react-native';
import { useCallback, useEffect, useMemo } from 'react';
import { StyleSheet } from 'react-native';
import type { CarteMapViewProps } from './carteMapTypes';
import { OSM_TILE_USER_AGENT, osmTileUrlTemplate } from '../../lib/map/osmTileFileCache';

/** Style minimal : pas de fond Mapbox/Google — uniquement OSM (RasterSource) + marqueurs. */
const OSM_BASE_MAP_STYLE = {
  version: 8,
  name: 'prospectlab-osm',
  sources: {},
  layers: [
    {
      id: 'pl-bg',
      type: 'background',
      paint: { 'background-color': '#e8e6e3' },
    },
  ],
} as const;

function visibleBoundsToRegion(ne: GeoJSON.Position, sw: GeoJSON.Position) {
  const latN = ne[1];
  const lngE = ne[0];
  const latS = sw[1];
  const lngW = sw[0];
  return {
    latitude: (latN + latS) / 2,
    longitude: (lngE + lngW) / 2,
    latitudeDelta: Math.max(1e-8, latN - latS),
    longitudeDelta: Math.max(1e-8, lngE - lngW),
  };
}

/**
 * Marqueurs : CircleLayer (ShapeSource) — fiable sur Android ; les icônes secteur sont sur la version web (Leaflet).
 */
export default function CarteMapView({
  region,
  onRegionChangeComplete,
  markers,
  onMarkerPress,
}: CarteMapViewProps) {
  useEffect(() => {
    addCustomHeader('User-Agent', OSM_TILE_USER_AGENT);
    return () => {
      removeCustomHeader('User-Agent');
    };
  }, []);

  const cameraBounds = useMemo(() => {
    const halfLat = region.latitudeDelta / 2;
    const halfLng = region.longitudeDelta / 2;
    return {
      ne: [region.longitude + halfLng, region.latitude + halfLat] as GeoJSON.Position,
      sw: [region.longitude - halfLng, region.latitude - halfLat] as GeoJSON.Position,
    };
  }, [region.latitude, region.longitude, region.latitudeDelta, region.longitudeDelta]);

  const shape = useMemo((): GeoJSON.FeatureCollection => {
    return {
      type: 'FeatureCollection',
      features: markers.map((m) => ({
        type: 'Feature',
        id: m.id,
        properties: { color: m.pinColor, pid: m.id },
        geometry: {
          type: 'Point',
          coordinates: [m.longitude, m.latitude],
        },
      })),
    };
  }, [markers]);

  const onShapePress = useCallback(
    (e: { features: GeoJSON.Feature[] }) => {
      if (!onMarkerPress) return;
      const f = e.features[0];
      const raw = f?.properties?.pid ?? f?.properties?.id;
      const id =
        typeof raw === 'number' && Number.isFinite(raw)
          ? raw
          : raw != null
            ? parseInt(String(raw), 10)
            : NaN;
      if (Number.isFinite(id)) onMarkerPress(id);
    },
    [onMarkerPress],
  );

  const onRegionDidChange = useCallback(
    (feature: GeoJSON.Feature<GeoJSON.Point, RegionPayload>) => {
      const p = feature.properties;
      if (!p?.isUserInteraction) return;
      const [ne, sw] = p.visibleBounds;
      onRegionChangeComplete(visibleBoundsToRegion(ne, sw));
    },
    [onRegionChangeComplete],
  );

  return (
    <MapView
      style={StyleSheet.absoluteFill}
      mapStyle={OSM_BASE_MAP_STYLE}
      logoEnabled={false}
      attributionEnabled
      compassEnabled
      onRegionDidChange={onRegionDidChange}
    >
      <Camera
        bounds={{ ne: cameraBounds.ne, sw: cameraBounds.sw }}
        animationDuration={0}
        animationMode="moveTo"
        minZoomLevel={2}
        maxZoomLevel={19}
      />
      <RasterSource
        id="pl-osm"
        tileUrlTemplates={[osmTileUrlTemplate()]}
        tileSize={256}
        minZoomLevel={0}
        maxZoomLevel={19}
        attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      >
        <RasterLayer id="pl-osm-layer" sourceID="pl-osm" />
      </RasterSource>
      <ShapeSource id="pl-entreprises" shape={shape} onPress={onShapePress} hitbox={{ width: 48, height: 48 }}>
        <CircleLayer
          id="pl-entreprises-circles"
          sourceID="pl-entreprises"
          style={{
            circleRadius: 9,
            circleColor: ['get', 'color'],
            circleStrokeWidth: 2,
            circleStrokeColor: '#ffffff',
          }}
        />
      </ShapeSource>
      <UserLocation visible renderMode="native" androidRenderMode="normal" />
    </MapView>
  );
}
