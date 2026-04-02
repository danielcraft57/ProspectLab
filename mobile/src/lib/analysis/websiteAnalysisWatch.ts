import { ProspectLabApi } from '../../features/prospectlab/prospectLabApi';
import { presentLocalNotification } from '../notifications/localNotify';
import { WEBSITE_ANALYSIS_READY_TYPE } from '../notifications/navigateFromAnalysisNotification';
import { HttpError } from '../http/httpClient';

function hostFromWebsite(website: string): string {
  try {
    return new URL(website).hostname;
  } catch {
    return website;
  }
}

function extractEntrepriseIdFromReport(report: unknown): number | null {
  if (!report || typeof report !== 'object') return null;
  const r = report as Record<string, unknown>;
  const top = r.entreprise_id;
  if (typeof top === 'number' && Number.isFinite(top)) return top;
  if (typeof top === 'string') {
    const n = parseInt(top, 10);
    return Number.isFinite(n) ? n : null;
  }
  const ent = r.entreprise;
  if (ent && typeof ent === 'object') {
    const id = (ent as Record<string, unknown>).id;
    if (typeof id === 'number' && Number.isFinite(id)) return id;
  }
  return null;
}

function isReportMeaningful(data: unknown): boolean {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  if (d.success === false) return false;
  const scraping = d.scraping as Record<string, unknown> | undefined;
  if (!scraping) return false;
  if (scraping.status === 'done') return true;
  if (scraping.latest != null) return true;
  return false;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Après un POST d'analyse, interroge le rapport jusqu'à ce qu'un scraping soit disponible (ou timeout).
 */
export async function watchWebsiteAnalysisReport(
  token: string,
  website: string,
  options?: { maxAttempts?: number; intervalMs?: number },
): Promise<void> {
  const max = options?.maxAttempts ?? 24;
  const intervalMs = options?.intervalMs ?? 20000;
  const host = hostFromWebsite(website);

  for (let i = 0; i < max; i++) {
    await sleep(intervalMs);
    try {
      const report = await ProspectLabApi.getWebsiteAnalysis(token, website, false, { skipCache: true });
      if (isReportMeaningful(report)) {
        const entrepriseId = extractEntrepriseIdFromReport(report);
        const payload: Record<string, string> = {
          type: WEBSITE_ANALYSIS_READY_TYPE,
          website,
        };
        if (entrepriseId != null) payload.entreprise_id = String(entrepriseId);
        await presentLocalNotification("Fin de l'analyse", 'Voir le rapport — appuie pour ouvrir la fiche.', payload);
        return;
      }
    } catch (e: unknown) {
      if (e instanceof HttpError && e.info.status === 404) continue;
    }
  }

  await presentLocalNotification(
    'Analyse en cours',
    `Le site ${host} est encore traité côté serveur. Consulte ProspectLab plus tard.`,
    { type: 'website_analysis_pending', website },
  );
}
