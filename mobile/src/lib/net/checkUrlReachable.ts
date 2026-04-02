/**
 * Vérifie si une URL répond (GET, suivi des redirections). Utile pour filtrer le bruit OCR.
 */
export async function checkUrlReachable(
  url: string,
  timeoutMs = 12000,
): Promise<{ ok: boolean; status?: number; error?: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
      redirect: 'follow',
      headers: {
        Accept: 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
      },
    });
    return { ok: res.ok, status: res.status };
  } catch (e: unknown) {
    const name = e && typeof e === 'object' && 'name' in e ? String((e as { name: string }).name) : '';
    const msg = e instanceof Error ? e.message : String(e);
    if (name === 'AbortError') return { ok: false, error: 'Timeout' };
    return { ok: false, error: msg || 'Réseau' };
  } finally {
    clearTimeout(timer);
  }
}
