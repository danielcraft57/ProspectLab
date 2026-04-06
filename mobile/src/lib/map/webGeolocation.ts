/**
 * Géolocalisation navigateur (hors expo-location) : évite navigator.permissions.query
 * (souvent absent sur Safari / certains navigateurs) et déclenche correctement la demande utilisateur.
 */

export function webGeolocationSupported(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.geolocation?.getCurrentPosition === 'function';
}

export function webGeolocationRequiresSecureContext(): boolean {
  if (typeof window === 'undefined') return true;
  return window.isSecureContext !== true;
}

export type WebGeolocationFailure =
  | { kind: 'denied' }
  | { kind: 'unavailable' }
  | { kind: 'timeout' }
  | { kind: 'unsupported' }
  | { kind: 'insecure' };

export async function getWebGeolocationCoords(): Promise<{ latitude: number; longitude: number }> {
  if (webGeolocationRequiresSecureContext()) {
    return Promise.reject({ kind: 'insecure' } satisfies WebGeolocationFailure);
  }
  if (!webGeolocationSupported()) {
    return Promise.reject({ kind: 'unsupported' } satisfies WebGeolocationFailure);
  }

  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        });
      },
      (err: GeolocationPositionError) => {
        if (err.code === err.PERMISSION_DENIED) {
          reject({ kind: 'denied' } satisfies WebGeolocationFailure);
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          reject({ kind: 'unavailable' } satisfies WebGeolocationFailure);
        } else if (err.code === err.TIMEOUT) {
          reject({ kind: 'timeout' } satisfies WebGeolocationFailure);
        } else {
          reject({ kind: 'unavailable' } satisfies WebGeolocationFailure);
        }
      },
      {
        enableHighAccuracy: false,
        maximumAge: 60_000,
        timeout: 20_000,
      },
    );
  });
}

export function webGeolocationErrorMessage(f: WebGeolocationFailure): string {
  switch (f.kind) {
    case 'insecure':
      return 'La géolocalisation nécessite HTTPS (ou localhost). Ouvre l’app via une URL sécurisée.';
    case 'unsupported':
      return 'Ce navigateur ne prend pas en charge la géolocalisation.';
    case 'denied':
      return 'Localisation refusée : dans la barre d’adresse, autorise la localisation pour ce site (icône cadenas / i), puis réessaie.';
    case 'timeout':
      return 'Délai dépassé pour obtenir la position. Réessaie ou vérifie que la localisation est activée sur l’appareil.';
    case 'unavailable':
    default:
      return 'Position indisponible. Vérifie que la localisation est activée pour le navigateur.';
  }
}
