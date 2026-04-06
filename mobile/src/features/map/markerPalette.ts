/**
 * Palette étendue : couleur dérivée de plusieurs dimensions (secteur, statut, opportunité, score sécurité).
 */

const PALETTE = [
  '#ef4444',
  '#f97316',
  '#f59e0b',
  '#eab308',
  '#84cc16',
  '#22c55e',
  '#14b8a6',
  '#06b6d4',
  '#3b82f6',
  '#6366f1',
  '#8b5cf6',
  '#a855f7',
  '#d946ef',
  '#ec4899',
  '#f43f5e',
  '#78716c',
] as const;

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

export function scoreSecurityBucket(score: number | null | undefined): string {
  if (score == null || !Number.isFinite(score)) return 'na';
  if (score <= 39) return 'crit';
  if (score <= 69) return 'mid';
  return 'ok';
}

export function normalizeOpportunityLabel(raw: string | null | undefined): string {
  const s = (raw ?? '').trim().toLowerCase();
  if (!s) return '—';
  if (s.includes('élev') || s.includes('eleve') || s.includes('high')) return 'élevée';
  if (s.includes('moyen') || s.includes('medium')) return 'moyenne';
  if (s.includes('faible') || s.includes('low')) return 'faible';
  return s.slice(0, 24);
}

export type MarkerColorInput = {
  secteur?: string | null;
  statut?: string | null;
  opportunite?: string | null;
  score_securite?: number | null;
};

/** Couleur stable par fiche (plusieurs champs métiers → index dans la palette). */
export function markerColorFromEntreprise(e: MarkerColorInput): string {
  const key = [
    (e.secteur ?? '').trim().toLowerCase(),
    (e.statut ?? '').trim().toLowerCase(),
    normalizeOpportunityLabel(e.opportunite),
    scoreSecurityBucket(e.score_securite),
  ].join('|');
  if (key === '|||na' || key.replace(/\|/g, '') === '') {
    return PALETTE[PALETTE.length - 1];
  }
  return PALETTE[hashString(key) % PALETTE.length];
}

export function paletteLegendColors(): readonly string[] {
  return PALETTE;
}
