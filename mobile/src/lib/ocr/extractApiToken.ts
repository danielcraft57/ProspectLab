/**
 * Heuristique pour retrouver un token API ProspectLab dans le texte OCR
 * (écran « Gestion des Tokens », alerte orange, chaîne alphanumérique + tirets).
 */
export function extractApiTokenFromOcrText(raw: string): string | null {
  if (!raw?.trim()) return null;

  const candidates = new Set<string>();

  /** OCR confond souvent O/0 sur les hex. */
  const fixHexOcr = (s: string) => s.replace(/[oO]/g, '0').replace(/[lI]/g, '1');

  const scan = (chunk: string) => {
    // Tokens "historiques" (alphanum + _ -)
    const re = /[A-Za-z0-9][A-Za-z0-9_-]{23,}/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(chunk)) !== null) {
      const c = m[0];
      if (c.includes('//') || c.includes('@')) continue;
      if (/^\d+$/.test(c)) continue;
      if (c.length > 128) continue;
      candidates.add(c);
    }

    // Tokens hex "propres" (sans caracteres speciaux), typiquement 64 chars
    const hex = /[a-f0-9]{48,128}/gi;
    while ((m = hex.exec(chunk)) !== null) {
      const c = m[0];
      if (c.length < 48 || c.length > 128) continue;
      candidates.add(c);
    }
  };

  // 1) version "normale"
  scan(raw.replace(/\s+/g, ' '));

    // 2) version "recollée": l'OCR insere parfois des espaces/retours au milieu du token
  scan(raw.replace(/\s+/g, ''));
  // 3) meme texte sans espaces + correction O/0, l/1 pour l'hex uniquement (evite de polluer les autres regex)
  {
    const compact = fixHexOcr(raw.replace(/\s+/g, ''));
    const hex = /[a-f0-9]{48,128}/gi;
    let m: RegExpExecArray | null;
    while ((m = hex.exec(compact)) !== null) {
      const c = m[0];
      if (c.length < 48 || c.length > 128) continue;
      candidates.add(c);
    }
  }

  for (const line of raw.split(/[\r\n]+/)) {
    scan(line.trim());
  }

  const list = [...candidates].sort((a, b) => b.length - a.length);
  if (!list.length) return null;

  // Priorites:
  // - un hex de 64 chars (ton cas actuel) est le meilleur signal
  const hex64 = list.find((c) => /^[a-f0-9]{64}$/i.test(c));
  if (hex64) return hex64;

  const inTypicalRange = list.filter((c) => c.length >= 28 && c.length <= 72);
  return (inTypicalRange[0] ?? list[0]) ?? null;
}
