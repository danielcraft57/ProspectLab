import { useIsFocused } from '@react-navigation/native';
import { useCallback, useEffect, useState } from 'react';

/**
 * Les écrans sous onglets restent souvent montés hors focus : la session caméra (et la torche)
 * continuait alors en arrière-plan. Démonter la `CameraView` quand `isFocused` est faux libère le capteur.
 */
export function useScanCameraFocused() {
  const isFocused = useIsFocused();
  const [sessionReady, setSessionReady] = useState(false);

  useEffect(() => {
    if (!isFocused) {
      setSessionReady(false);
    }
  }, [isFocused]);

  const onCameraReady = useCallback(() => {
    setSessionReady(true);
  }, []);

  return { isFocused, sessionReady, onCameraReady };
}
