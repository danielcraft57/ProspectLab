/** Types partagés carte (MapLibre natif / Leaflet web — pas d’import des libs carte ici). */
export type MapRegion = {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
};

export type CarteMapMarker = {
  id: number;
  latitude: number;
  longitude: number;
  title: string;
  description?: string;
  pinColor: string;
  /** MaterialCommunityIcons — marqueurs natifs */
  iconMaterial: string;
  /** Suffixe Font Awesome 6 solid (fa-solid fa-…) — marqueurs web */
  iconFaSolid: string;
  secteur?: string | null;
  statut?: string | null;
  opportunite?: string | null;
  score_securite?: number | null;
  note_google?: number | null;
  nb_avis_google?: number | null;
  website?: string | null;
};

export type CarteMapViewProps = {
  region: MapRegion;
  onRegionChangeComplete: (r: MapRegion) => void;
  markers: CarteMapMarker[];
  /** Clic sur un point (id entreprise). */
  onMarkerPress?: (entrepriseId: number) => void;
};
