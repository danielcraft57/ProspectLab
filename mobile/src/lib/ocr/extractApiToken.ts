/**
 * Heuristique pour retrouver un token API ProspectLab dans le texte OCR
 * (écran « Gestion des Tokens », alerte orange, chaîne alphanumérique + tirets).
 */
export function extractApiTokenFromOcrText(raw: string): string | null {
  if (!raw?.trim()) return null;

  const candidates = new Set<string>();

  const scan = (chunk: string) => {
    const re = /[A-Za-z0-9][A-Za-z0-9_-]{23,}/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(chunk)) !== null) {
      const c = m[0];
      if (c.includes('//') || c.includes('@')) continue;
      if (/^\d+$/.test(c)) continue;
      if (c.length > 128) continue;
      candidates.add(c);
    }
  };

  scan(raw.replace(/\s+/g, ' '));
  for (const line of raw.split(/[\r\n]+/)) {
    scan(line.trim());
  }

  const list = [...candidates].sort((a, b) => b.length - a.length);
  if (!list.length) return null;

  const inTypicalRange = list.filter((c) => c.length >= 28 && c.length <= 72);
  return (inTypicalRange[0] ?? list[0]) ?? null;
}
