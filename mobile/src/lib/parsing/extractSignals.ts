export type ExtractedSignals = {
  rawText: string;
  emails: string[];
  phones: string[];
  websites: string[];
};

function uniq(arr: string[]) {
  return Array.from(new Set(arr.map((s) => s.trim()).filter(Boolean)));
}

function normalizeEmail(raw: string) {
  return raw
    .trim()
    .replace(/\s+/g, '')
    .replace(/\(at\)|\[at\]|\sat\s/gi, '@')
    .replace(/\(dot\)|\[dot\]|\sdot\s/gi, '.')
    .toLowerCase();
}

function normalizeWebsite(raw: string) {
  const s = raw.trim().replace(/[)\],;]+$/g, '');
  if (!s) return '';
  if (s.startsWith('http://') || s.startsWith('https://')) return s;
  return `https://${s}`;
}

function normalizePhone(raw: string) {
  const d = raw.replace(/[^\d+]/g, '');
  return d;
}

/**
 * Extrait emails/telephones/websites depuis un texte OCR (tolerant).
 *
 * @param text Texte OCR brut
 * @returns Signaux extraits + normalises
 */
export function extractSignals(text: string): ExtractedSignals {
  const rawText = text ?? '';
  const safe = rawText.replace(/\r/g, '\n');

  const emailRegex = /[a-z0-9._%+-]+(?:\s*(?:@|\(at\)|\[at\]|\sat\s)\s*)[a-z0-9.-]+(?:\s*(?:\.|\(dot\)|\[dot\]|\sdot\s)\s*)[a-z]{2,}/gi;
  const phoneRegex = /(?:\+?\d[\d\s().-]{7,}\d)/g;
  const websiteRegex = /((https?:\/\/)?([a-z0-9-]+\.)+[a-z]{2,}(\/[^\s]*)?)/gi;

  const emails = uniq((safe.match(emailRegex) ?? []).map(normalizeEmail));
  const phones = uniq((safe.match(phoneRegex) ?? []).map(normalizePhone));
  const websites = uniq((safe.match(websiteRegex) ?? []).map(normalizeWebsite));

  return { rawText, emails, phones, websites };
}

