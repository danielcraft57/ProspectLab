import type { CarteVille } from './carteVillesTypes';
// Copie synchronisée avec scripts/google_maps_tools/presets_grand_est.json (bundle offline).
import raw from '../../data/cartePresetsGrandEst.json';

type PresetRow = {
  city?: string;
  lat?: number;
  lng?: number;
  region?: string;
  department?: string;
};

export function carteVillesFromBundledPresets(): CarteVille[] {
  const presets = (raw as { presets?: PresetRow[] }).presets ?? [];
  const out: CarteVille[] = [];
  for (const p of presets) {
    const label = (p.city ?? '').trim();
    if (!label || typeof p.lat !== 'number' || typeof p.lng !== 'number') continue;
    out.push({
      label,
      latitude: p.lat,
      longitude: p.lng,
      region: p.region,
      department: p.department,
    });
  }
  out.sort((a, b) => a.label.localeCompare(b.label, 'fr'));
  return out;
}
