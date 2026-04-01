export const Config = {
  prospectLabBaseUrl: (() => {
    const raw = process.env.EXPO_PUBLIC_PROSPECTLAB_BASE_URL?.trim();
    if (!raw) return 'https://prospectlab.danielcraft.fr';
    if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
    return `https://${raw}`;
  })(),
  prospectLabPublicPrefix: process.env.EXPO_PUBLIC_PROSPECTLAB_API_PUBLIC_PREFIX ?? '/api/public',
} as const;

