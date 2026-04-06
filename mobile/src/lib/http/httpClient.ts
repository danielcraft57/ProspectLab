export type HttpErrorInfo = {
  status: number;
  bodyText?: string;
};

export class HttpError extends Error {
  info: HttpErrorInfo;

  constructor(message: string, info: HttpErrorInfo) {
    super(message);
    this.name = 'HttpError';
    this.info = info;
  }
}

export type JsonValue = null | boolean | number | string | JsonValue[] | { [k: string]: JsonValue };

export async function fetchJson<T>(
  url: string,
  options?: {
    method?: string;
    headers?: Record<string, string>;
    body?: unknown;
    timeoutMs?: number;
  },
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options?.timeoutMs ?? 15000);

  try {
    const res = await fetch(url, {
      method: options?.method ?? 'GET',
      headers: {
        Accept: 'application/json',
        ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options?.headers ?? {}),
      },
      body: options?.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    if (!res.ok) {
      const bodyText = await res.text().catch(() => undefined);
      throw new HttpError(`HTTP ${res.status}`, { status: res.status, bodyText });
    }

    return (await res.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}

