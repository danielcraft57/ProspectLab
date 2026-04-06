import { useEffect, useState } from 'react';

/**
 * Fenêtre « nuit » locale : torche LED en continu pour scanner QR / OCR.
 * (Pas de capteur de luminosité : simple horloge, recalculée chaque minute.)
 */
function isLikelyNightLocal(d: Date): boolean {
  const h = d.getHours();
  return h >= 19 || h < 7;
}

export type CameraScanAssist = {
  /**
   * Expo Camera : `off` = mise au point réajustée automatiquement quand c’est nécessaire (mode continu).
   * `on` = une seule AF puis verrouillage (moins adapté au scan mobile).
   */
  autofocus: 'on' | 'off';
  /** Zoom numérique 0–1 (léger resserrement pour texte / QR). Plus fort la nuit avec torche. */
  zoom: number;
  enableTorch: boolean;
  /** Flash au déclenchement : auto le jour, off la nuit (torche déjà active). */
  flash: 'off' | 'on' | 'auto';
  isNight: boolean;
};

export function useCameraScanAssist(): CameraScanAssist {
  const [night, setNight] = useState(() => isLikelyNightLocal(new Date()));

  useEffect(() => {
    const tick = () => setNight(isLikelyNightLocal(new Date()));
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, []);

  if (night) {
    return {
      autofocus: 'off',
      zoom: 0.17,
      enableTorch: true,
      flash: 'off',
      isNight: true,
    };
  }

  return {
    autofocus: 'off',
    zoom: 0.11,
    enableTorch: false,
    flash: 'auto',
    isNight: false,
  };
}
