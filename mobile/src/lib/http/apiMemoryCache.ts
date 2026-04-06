export type CacheRequestOptions = {
  skipCache?: boolean;
};

type Entry = { exp: number; value: unknown };

const store = new Map<string, Entry>();
const MAX_ENTRIES = 256;

function tokenScope(token: string): string {
  let h = 0;
  for (let i = 0; i < token.length; i++) h = (h * 31 + token.charCodeAt(i)) | 0;
  return String(h);
}

export function prospectLabCacheKey(token: string, url: string): string {
  return `pl:${tokenScope(token)}:${url}`;
}

function prune(): void {
  const now = Date.now();
  for (const [k, v] of store) {
    if (v.exp <= now) store.delete(k);
  }
  while (store.size > MAX_ENTRIES) {
    const first = store.keys().next().value;
    if (first !== undefined) store.delete(first);
  }
}

export function clearProspectLabApiCache(): void {
  store.clear();
}

export async function fetchJsonCached<T>(
  key: string,
  ttlMs: number,
  fetcher: () => Promise<T>,
  options?: CacheRequestOptions,
): Promise<T> {
  if (!options?.skipCache) {
    const hit = store.get(key);
    if (hit && hit.exp > Date.now()) {
      return hit.value as T;
    }
    if (hit) store.delete(key);
  }
  const data = await fetcher();
  if (!options?.skipCache) {
    prune();
    store.set(key, { exp: Date.now() + ttlMs, value: data });
  }
  return data;
}
