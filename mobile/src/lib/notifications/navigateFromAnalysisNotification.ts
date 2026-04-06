import type { Router } from 'expo-router';

/** Clé `data` commune aux notifs locales et push Expo (valeurs string côté FCM). */
export const WEBSITE_ANALYSIS_READY_TYPE = 'website_analysis_ready' as const;

function parseEntrepriseId(data: Record<string, unknown>): number | null {
  const raw = data.entreprise_id ?? data.entrepriseId;
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  if (typeof raw === 'string') {
    const n = parseInt(raw, 10);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/**
 * Ouvre l’écran détail entreprise depuis une notif (locale ou push) d’analyse site prête.
 */
export function navigateFromAnalysisNotificationData(router: Router, data: Record<string, unknown> | undefined): void {
  if (!data || typeof data !== 'object') return;
  if (data.type !== WEBSITE_ANALYSIS_READY_TYPE) return;

  const id = parseEntrepriseId(data);
  if (id != null) {
    router.push({
      pathname: '/(tabs)/entreprises/details',
      params: { kind: 'id', value: String(id) },
    });
    return;
  }

  const website = typeof data.website === 'string' ? data.website.trim() : '';
  if (website) {
    router.push({
      pathname: '/(tabs)/entreprises/details',
      params: { kind: 'website', value: encodeURIComponent(website) },
    });
  }
}
