import L from 'leaflet';
import { useCallback, useEffect, useRef } from 'react';
import { StyleSheet, View } from 'react-native';
import type { CarteMapMarker, CarteMapViewProps, MapRegion } from './carteMapTypes';

const FA_VERSION = '6.5.2';

function ensureLeafletCss() {
  if (typeof document === 'undefined') return;
  const id = 'leaflet-css-prospectlab';
  if (document.getElementById(id)) return;
  const link = document.createElement('link');
  link.id = id;
  link.rel = 'stylesheet';
  link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
  document.head.appendChild(link);
}

function ensureFontAwesomeForMap() {
  if (typeof document === 'undefined') return;
  const id = 'fa6-css-prospectlab-map';
  if (document.getElementById(id)) return;
  const link = document.createElement('link');
  link.id = id;
  link.rel = 'stylesheet';
  link.href = `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/${FA_VERSION}/css/all.min.css`;
  document.head.appendChild(link);
}

function ensureMapPinStyles() {
  if (typeof document === 'undefined') return;
  const id = 'pl-map-pin-css';
  if (document.getElementById(id)) return;
  const style = document.createElement('style');
  style.id = id;
  style.textContent = `
    .pl-map-pin {
      width: 32px;
      height: 32px;
      border-radius: 16px;
      border: 2px solid #ffffff;
      box-shadow: 0 2px 6px rgba(0,0,0,0.28);
      display: flex;
      align-items: center;
      justify-content: center;
      box-sizing: border-box;
    }
    .pl-map-pin i {
      color: #ffffff;
      font-size: 14px;
      line-height: 1;
    }
    .pl-map-pin-root.leaflet-marker-icon {
      margin-left: -16px !important;
      margin-top: -16px !important;
    }
  `;
  document.head.appendChild(style);
}

function regionToBounds(r: MapRegion): L.LatLngBoundsExpression {
  const halfLat = r.latitudeDelta / 2;
  const halfLng = r.longitudeDelta / 2;
  return [
    [r.latitude - halfLat, r.longitude - halfLng],
    [r.latitude + halfLat, r.longitude + halfLng],
  ];
}

function boundsToRegion(b: L.LatLngBounds): MapRegion {
  const sw = b.getSouthWest();
  const ne = b.getNorthEast();
  return {
    latitude: (sw.lat + ne.lat) / 2,
    longitude: (sw.lng + ne.lng) / 2,
    latitudeDelta: Math.max(1e-8, ne.lat - sw.lat),
    longitudeDelta: Math.max(1e-8, ne.lng - sw.lng),
  };
}

function safeFaSolidClass(name: string): string {
  return /^[a-z0-9-]+$/.test(name) ? name : 'building';
}

function markerDivHtml(m: CarteMapMarker): string {
  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const bg = esc(m.pinColor);
  const fa = safeFaSolidClass(m.iconFaSolid);
  return `<div class="pl-map-pin" style="background-color:${bg}" title="${esc(m.title)}"><i class="fa-solid fa-${fa}" aria-hidden="true"></i></div>`;
}

export default function CarteMapView({
  region,
  onRegionChangeComplete,
  markers,
  onMarkerPress,
}: CarteMapViewProps) {
  const hostRef = useRef<View | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const skipNextMoveEnd = useRef(false);
  const onRegionChangeRef = useRef(onRegionChangeComplete);
  onRegionChangeRef.current = onRegionChangeComplete;

  const onMarkerPressRef = useRef(onMarkerPress);
  onMarkerPressRef.current = onMarkerPress;

  const syncMarkers = useCallback((map: L.Map, mks: CarteMapMarker[]) => {
    if (!layerRef.current) {
      layerRef.current = L.layerGroup().addTo(map);
    }
    layerRef.current.clearLayers();
    for (const m of mks) {
      const icon = L.divIcon({
        className: 'pl-map-pin-root',
        html: markerDivHtml(m),
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });
      const marker = L.marker([m.latitude, m.longitude], { icon });
      marker.on('click', (ev) => {
        L.DomEvent.stopPropagation(ev);
        onMarkerPressRef.current?.(m.id);
      });
      marker.addTo(layerRef.current);
    }
  }, []);

  useEffect(() => {
    ensureLeafletCss();
    ensureFontAwesomeForMap();
    ensureMapPinStyles();
  }, []);

  useEffect(() => {
    const el = hostRef.current as unknown as HTMLDivElement | null;
    if (!el || mapRef.current) return;

    const map = L.map(el, {
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    map.fitBounds(regionToBounds(region), { animate: false });
    syncMarkers(map, markers);

    map.on('moveend', () => {
      if (skipNextMoveEnd.current) {
        skipNextMoveEnd.current = false;
        return;
      }
      onRegionChangeRef.current(boundsToRegion(map.getBounds()));
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- init unique
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    skipNextMoveEnd.current = true;
    map.fitBounds(regionToBounds(region), { animate: false });
  }, [region.latitude, region.longitude, region.latitudeDelta, region.longitudeDelta]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    syncMarkers(map, markers);
  }, [markers, syncMarkers]);

  return <View ref={hostRef} style={styles.map} />;
}

const styles = StyleSheet.create({
  map: StyleSheet.absoluteFillObject,
});
