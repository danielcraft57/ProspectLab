import { extractSignals } from './extractSignals';

function stripTrailingJunk(s: string): string {
  return s.replace(/[)\].,;:!?]+$/g, '').trim();
}

/**
 * Normalise une URL pour l'API ProspectLab (https + hôte valide).
 */
export function normalizeWebsiteForApi(raw: string): string | null {
  let s = stripTrailingJunk(raw);
  if (!s) return null;
  if (/^\/\//.test(s)) s = `https:${s}`;
  if (!/^https?:\/\//i.test(s)) s = `https://${s}`;
  try {
    const u = new URL(s);
    const host = u.hostname.toLowerCase();
    if (!host || !host.includes('.') || host === 'localhost') return null;
    const path = u.pathname === '/' ? '' : u.pathname;
    return `${u.protocol}//${host}${u.port ? `:${u.port}` : ''}${path}${u.search || ''}`;
  } catch {
    return null;
  }
}

/**
 * Pour l'analyse : uniquement l'origine domaine (`https://hostname`), sans chemin ni query.
 * C'est ce qui est testé (joignabilité) puis envoyé au serveur.
 */
export function normalizeWebsiteDomainForAnalysis(raw: string): string | null {
  const base = normalizeWebsiteForApi(raw.trim());
  if (!base) return null;
  try {
    const u = new URL(base);
    let host = u.hostname.toLowerCase();
    if (!host || !host.includes('.') || host === 'localhost') return null;
    if (host.endsWith('.local')) return null;
    if (host.startsWith('www.')) host = host.slice(4);
    if (!host) return null;
    const port = u.port;
    const nonDefaultPort =
      port && port !== '80' && port !== '443' && port !== '' ? `:${port}` : '';
    return `https://${host}${nonDefaultPort}`;
  } catch {
    return null;
  }
}

const looseHost =
  /(?:https?:\/\/[^\s\b]+|www\.[^\s]+|(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}(?:\/[^\s]*)?)/gi;

function variantsForOcr(chunk: string): string[] {
  const s0 = chunk.trim();
  const s1 = s0.replace(/\s*\.\s*/g, '.');
  const s2 = s0.replace(/\s+/g, '');
  return Array.from(new Set([s0, s1, s2].filter(Boolean)));
}

/**
 * Détecte des URLs / domaines potentiels, y compris OCR bruité (espaces autour du point, etc.).
 */
export function extractWebsiteCandidates(raw: string): string[] {
  const text = (raw ?? '').replace(/\r/g, '\n');
  const out = new Set<string>();

  for (const w of extractSignals(text).websites) {
    const n = normalizeWebsiteForApi(w);
    if (n) out.add(n);
  }

  for (const line of text.split(/[\n\r]+/)) {
    for (const variant of variantsForOcr(line)) {
      let m: RegExpExecArray | null;
      const re = new RegExp(looseHost.source, looseHost.flags);
      while ((m = re.exec(variant)) !== null) {
        const n = normalizeWebsiteForApi(m[0]);
        if (n) out.add(n);
      }
    }
  }

  return [...out].sort((a, b) => a.length - b.length);
}
