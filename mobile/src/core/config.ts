export const Config = {
  prospectLabBaseUrl: (() => {
    const raw = process.env.EXPO_PUBLIC_PROSPECTLAB_BASE_URL?.trim();
    // Défaut orienté dev local ; en prod définir EXPO_PUBLIC_PROSPECTLAB_BASE_URL (HTTPS).
    if (!raw) return 'http://localhost:5000';
    if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
    return `https://${raw}`;
  })(),
  prospectLabPublicPrefix: process.env.EXPO_PUBLIC_PROSPECTLAB_API_PUBLIC_PREFIX ?? '/api/public',
} as const;

